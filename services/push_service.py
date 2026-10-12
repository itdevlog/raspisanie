# services/push_service.py
"""Отправка Web Push-уведомлений об изменениях в расписании (W13).

Читает VAPID-пару из конфига (``Config.VAPID_PUBLIC_KEY`` /
``Config.VAPID_PRIVATE_KEY`` / ``Config.VAPID_SUBJECT``) и рассылает push
через ``pywebpush.webpush``.

Особенности:

- ``webpush`` — блокирующая библиотека: каждый вызов уходит в
  ``asyncio.to_thread``, чтобы не блокировать event loop.
- payload — ``{title, body, url}`` (компактный JSON).
- best-effort, как у ``SnapshotExporter``: ошибки отдельных подписок
  логируются, но не всплывают и не прерывают рассылку остальным.
- подписка удаляется как «мёртвая» (``PushSubscriptionStore.remove_dead``)
  только при ответе push-сервиса 404/410. Прочие ошибки (5xx, сеть) —
  временные, подписку сохраняем.
- если VAPID-ключи не заданы — отправка выключена (no-op).
- «не беспокоить ночью» (quiet hours): подписки с ``quiet=True`` не получают
  push в окне 22:00–07:00 (таймзона приложения). Пропущенный ночью push
  **не переотправляется**: сайт всё равно показывает замену, а Telegram-пользователи
  получают отложенное сообщение после окна. У подписок без поля ``quiet``
  (старые записи) поведение — как у ``quiet=True``.

``pywebpush`` импортируется лениво: модуль остаётся импортируемым даже там,
где библиотека не установлена (например, на edge), а тесты подменяют
``services.push_service.pywebpush``.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

try:  # pragma: no cover - тривиальная ветка ленивого импорта
    import pywebpush
except ImportError:  # pragma: no cover - библиотека ставится как зависимость
    pywebpush = None

from config.config import Config, get_timezone

logger = logging.getLogger(__name__)

# Статусы, означающие, что подписка недействительна и её нужно удалить
# (404 Not Found, 410 Gone). Все прочие ошибки считаем временными.
DEAD_SUBSCRIPTION_STATUSES = frozenset({404, 410})

# Таймаут одной отправки, секунд.
PUSH_TIMEOUT_SECONDS = 30.0

# Окно «не беспокоить ночью»: [22:00, 07:00), пересекает полночь.
QUIET_START_HOUR = 22
QUIET_END_HOUR = 7


class PushService:
    """Best-effort рассылка Web Push через ``pywebpush``."""

    def __init__(self, config: Any | None = None, store: Any | None = None) -> None:
        cfg = config if config is not None else Config()
        self.public_key: str = cfg.VAPID_PUBLIC_KEY
        self.private_key: str = cfg.VAPID_PRIVATE_KEY
        self.subject: str = cfg.VAPID_SUBJECT
        self.store = store
        self.logger = logging.getLogger(__name__)

    @property
    def enabled(self) -> bool:
        """Отправка включена, только если заданы оба VAPID-ключа."""
        return bool(self.public_key and self.private_key)

    @staticmethod
    def _in_quiet_window(now: datetime) -> bool:
        """Сейчас внутри ночного окна 22:00–07:00 (пересекает полночь)?"""
        return now.hour >= QUIET_START_HOUR or now.hour < QUIET_END_HOUR

    async def send_exchange_notifications(
        self,
        subscriptions: list[dict],
        title: str,
        body: str,
        url: str,
        now: datetime | None = None,
    ) -> int:
        """Рассылает push перечисленным подпискам. Возвращает число успешных.

        Никогда не бросает: сбой одной подписки логируется и не мешает
        остальным; подписки с ответом 404/410 удаляются как мёртвые.

        Подписки с ``quiet=True`` (и старые записи без поля ``quiet``)
        пропускаются внутри ночного окна 22:00–07:00 по таймзоне приложения.
        Пропущенный push не переотправляется — сайт покажет замену, а
        Telegram-пользователи получат отложенное сообщение. ``now`` можно
        передать в тестах; по умолчанию берётся текущее время.
        """
        if not self.enabled:
            self.logger.info(
                "Отправка push выключена: VAPID-ключи не заданы")
            return 0

        if not subscriptions:
            return 0

        moment = now if now is not None else datetime.now(get_timezone())
        quiet_now = self._in_quiet_window(moment)

        payload = json.dumps({'title': title, 'body': body, 'url': url})
        sent = 0
        skipped_quiet = 0
        dead_endpoints: list[str] = []

        for subscription in subscriptions:
            # Отсутствие `quiet` в старых записях трактуем как True.
            if quiet_now and subscription.get('quiet', True):
                skipped_quiet += 1
                continue
            try:
                await asyncio.to_thread(self._send_one, subscription, payload)
            except Exception as e:  # noqa: BLE001 - best-effort: наружу не выходит
                status = self._status_code(e)
                endpoint = subscription.get('endpoint')
                if status in DEAD_SUBSCRIPTION_STATUSES:
                    self.logger.info(
                        "Подписка мертва (HTTP %s), удаляем: %s", status, endpoint)
                    if endpoint:
                        dead_endpoints.append(endpoint)
                else:
                    self.logger.warning(
                        "Не удалось отправить push на %s: %s", endpoint, e)
                continue
            sent += 1

        if skipped_quiet:
            self.logger.info(
                "Пропущено %s push в тихие часы (не беспокоить ночью)", skipped_quiet)

        if dead_endpoints:
            self._remove_dead(dead_endpoints)

        return sent

    def _send_one(self, subscription: dict, payload: str) -> None:
        """Синхронная отправка одной подписки (вызывается через to_thread)."""
        pywebpush.webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=self.private_key,
            vapid_claims={'sub': self.subject},
            timeout=PUSH_TIMEOUT_SECONDS,
        )

    def _remove_dead(self, endpoints: list[str]) -> None:
        """Удаляет мёртвые подписки через store (если он передан)."""
        if self.store is None:
            return
        try:
            self.store.remove_dead(endpoints)
        except Exception as e:  # noqa: BLE001 - best-effort: удаление тоже не критично
            self.logger.warning("Не удалось удалить мёртвые подписки: %s", e)

    @staticmethod
    def _status_code(error: Exception) -> int | None:
        """Достаёт HTTP-статус из ``WebPushException.response`` (защищённо)."""
        response = getattr(error, 'response', None)
        return getattr(response, 'status_code', None)
