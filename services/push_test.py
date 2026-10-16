# services/push_test.py
"""Операторский CLI для диагностики Web Push (test-push utility).

Сегодня доказать доставку push end-to-end нечем: ``/check_exchanges`` шлёт
только в Telegram. Этот модуль даёт оператору две команды:

* ``--list`` — показать все сохранённые подписки: endpoint (обрезан), к какой
  сущности привязана подписка (``school_id``/``kind``/``name``) и служебные
  метки времени. Главный диагностический ответ на вопрос «на какой класс
  подписан мой телефон».

* ``--send`` — отправить ОДИН тестовый push в каждую подходящую подписку через
  тот же код отправки, что и штатные уведомления
  (``PushService.send_one``: VAPID-подпись и payload ровно ``{title, body,
  url}`` — то, что читает обработчик ``push`` в service-worker). Селектор:
  ``--all`` либо ``--school <id> [--kind class|teacher|room] [--name <имя>]``.

Запуск::

    python -m services.push_test --list
    python -m services.push_test --send --all
    python -m services.push_test --send --school school_133 --kind class --name 5А

Отдельный диагностический сценарий — отсутствие VAPID-ключей: без
``VAPID_PUBLIC_KEY``/``VAPID_PRIVATE_KEY`` отправка невозможна, и CLI завершается
понятной ошибкой (это и есть нужный оператору сигнал).

Код ``main`` возвращает 0 при успехе и 1/2 при ошибке (для ``sys.exit``).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime

from config.config import Config, get_timezone
from database.file_db import FileDB
from services.push_service import DEAD_SUBSCRIPTION_STATUSES, PushService
from services.push_store import VALID_KINDS, PushSubscriptionStore

# Заголовок тестового push — короткий и узнаваемый, с эмодзи как у штатных.
TEST_TITLE = '🔔 Тестовое уведомление'

# Сколько символов endpoint показывать в списке (остальное — «…»).
ENDPOINT_DISPLAY_LIMIT = 72


def truncate_endpoint(endpoint, limit: int = ENDPOINT_DISPLAY_LIMIT) -> str:
    """Обрезает длинный endpoint для читаемого вывода (сам URL не меняется)."""
    endpoint = endpoint or ''
    if len(endpoint) <= limit:
        return endpoint
    return endpoint[:limit] + '…'


def select_subscriptions(
    store,
    *,
    all_: bool = False,
    school_id: str | None = None,
    kind: str | None = None,
    name: str | None = None,
) -> list[dict]:
    """Подписки из хранилища под селектор CLI.

    ``all_=True`` — вернуть все. Иначе фильтр по заданным (school_id, kind,
    name); незаданные поля не ограничивают выборку. Пустой список — ничего не
    совпало.
    """
    subscriptions = list(store.list_all())
    if all_:
        return subscriptions

    def matches(sub: dict) -> bool:
        if school_id is not None and sub.get('school_id') != school_id:
            return False
        if kind is not None and sub.get('kind') != kind:
            return False
        if name is not None and sub.get('name') != name:
            return False
        return True

    return [sub for sub in subscriptions if matches(sub)]


def _load_store() -> PushSubscriptionStore:
    """Хранилище подписок над штатным FileDB (``Config.DB_PATH``)."""
    return PushSubscriptionStore(FileDB(Config.DB_PATH))


def _entity_url(sub: dict) -> str:
    """Ссылка для тестового push: share-страница класса либо корень сайта.

    Переиспользует штатный билдер share-ссылки (``build_class_share_url``),
    чтобы тестовый push открывал то же место, что и настоящий. Для
    teacher/room (MVP их не создаёт) — просто корень публичного сайта.
    """
    base = (Config.WEBAPP_URL or '').rstrip('/')
    if not base:
        return '/'
    kind = sub.get('kind')
    name = sub.get('name')
    if kind == 'class' and name:
        from core.background_updater import build_class_share_url

        url = build_class_share_url(
            base, str(sub.get('school_id', '')), str(name), datetime.now(get_timezone()))
        if url:
            return url
    # Запасной вариант — корень публичного сайта.
    return base + '/'


def _reason(result) -> str:
    """Человекочитаемая причина для оператора по результату отправки."""
    status = result.status_code
    if status in DEAD_SUBSCRIPTION_STATUSES:
        return f'HTTP {status}: подписка мертва (будет удалена)'
    if status in (401, 403):
        return f'HTTP {status}: проблема VAPID/аутентификации push-сервиса'
    if status is not None:
        return f'HTTP {status}: {result.error}'
    return f'ошибка отправки: {result.error}'


def _cmd_list(store) -> int:
    """Печатает все подписки; 0 — всегда (диагностический вывод)."""
    subscriptions = store.list_all()
    if not subscriptions:
        print('Подписок не найдено.')
        return 0
    print(f'Подписок в хранилище: {len(subscriptions)}')
    for i, sub in enumerate(subscriptions, 1):
        print(f'  {i}. {truncate_endpoint(sub.get("endpoint"))}')
        print(
            f'     школа: {sub.get("school_id")}  '
            f'вид: {sub.get("kind")}  имя: {sub.get("name")}'
        )
        quiet = sub.get('quiet', True)
        print(
            f'     создана: {sub.get("created_at", "—")}  '
            f'тихие часы: {"да" if quiet else "нет"}'
        )
    return 0


async def _send(store, service: PushService, subscriptions: list[dict]) -> int:
    """Шлёт по одному тестовому push на подписку. 0 — все успешны, иначе 1."""
    total = len(subscriptions)
    ok = 0
    fail = 0
    dead_endpoints: list[str] = []

    for i, sub in enumerate(subscriptions, 1):
        endpoint = sub.get('endpoint', '')
        print(
            f'[{i}/{total}] {truncate_endpoint(endpoint)} '
            f'({sub.get("school_id")}, {sub.get("kind")}, {sub.get("name")})'
        )
        name = sub.get('name') or '—'
        body = f'{name} — тестовое уведомление. Если вы это видите, push работает.'
        result = await service.send_one(sub, TEST_TITLE, body, _entity_url(sub))
        if result.success:
            ok += 1
            print('    [OK] доставлено')
        else:
            fail += 1
            print(f'    [ОШИБКА] {_reason(result)}')
            if result.dead and endpoint:
                dead_endpoints.append(endpoint)

    removed = 0
    if dead_endpoints:
        removed = store.remove_dead(dead_endpoints)
        print(f'Удалено мёртвых подписок: {removed} (HTTP 404/410).')

    print(f'Итог: успешно {ok}, ошибок {fail}, подписок {total}.')
    return 0 if fail == 0 else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python -m services.push_test',
        description='Диагностика Web Push: список подписок и тестовая отправка.',
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        '--list', dest='list_', action='store_true',
        help='показать все сохранённые подписки',
    )
    mode.add_argument(
        '--send', dest='send', action='store_true',
        help='отправить тестовый push в подходящие подписки',
    )
    parser.add_argument(
        '--all', dest='all_', action='store_true',
        help='(для --send) все подписки',
    )
    parser.add_argument(
        '--school', dest='school_id', metavar='ID',
        help='(для --send) id школы, например school_133',
    )
    parser.add_argument(
        '--kind', choices=sorted(VALID_KINDS),
        help='(для --send) вид сущности: class|teacher|room',
    )
    parser.add_argument(
        '--name', help='(для --send) имя класса/учителя/кабинета',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI. Возвращает код выхода (0 — успех, 1/2 — ошибка)."""
    args = _build_parser().parse_args(argv)

    if args.list_:
        return _cmd_list(_load_store())

    # --send: сначала проверяем конфиг (и падаем громко), затем идём в хранилище.
    if not args.all_ and not args.school_id:
        print(
            'Укажите селектор: --all или --school <id> '
            '[--kind class|teacher|room] [--name <имя>].',
            file=sys.stderr,
        )
        return 2
    if (args.kind or args.name) and not args.school_id:
        print(
            '--kind/--name допустимы только вместе с --school <id> '
            '(либо используйте --all).',
            file=sys.stderr,
        )
        return 2

    service = PushService()
    if not service.enabled:
        print(
            'Отправка невозможна: не заданы VAPID-ключи '
            'VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY. Впишите их в .env '
            '(сгенерировать: ./manage.sh vapid).',
            file=sys.stderr,
        )
        return 1

    store = _load_store()
    subscriptions = select_subscriptions(
        store,
        all_=args.all_,
        school_id=args.school_id,
        kind=args.kind,
        name=args.name,
    )
    if not subscriptions:
        print(
            'По заданному селектору подписок не найдено — некому отправлять. '
            'Проверьте список: python -m services.push_test --list',
            file=sys.stderr,
        )
        return 1

    print(f'Совпало подписок: {len(subscriptions)}')
    return asyncio.run(_send(store, service, subscriptions))


if __name__ == '__main__':
    sys.exit(main())
