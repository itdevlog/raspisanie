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

``pywebpush`` импортируется лениво: модуль остаётся импортируемым даже там,
где библиотека не установлена (например, на edge), а тесты подменяют
``services.push_service.pywebpush``.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

try:  # pragma: no cover - тривиальная ветка ленивого импорта
    import pywebpush
except ImportError:  # pragma: no cover - библиотека ставится как зависимость
    pywebpush = None

from config.config import Config

logger = logging.getLogger(__name__)

# Статусы, означающие, что подписка недействительна и её нужно удалить
# (404 Not Found, 410 Gone). Все прочие ошибки считаем временными.
DEAD_SUBSCRIPTION_STATUSES = frozenset({404, 410})

# Таймаут одной отправки, секунд.
PUSH_TIMEOUT_SECONDS = 30.0


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

    async def send_exchange_notifications(
        self,
        subscriptions: list[dict],
        title: str,
        body: str,
        url: str,
    ) -> int:
        """Рассылает push перечисленным подпискам. Возвращает число успешных.

        Никогда не бросает: сбой одной подписки логируется и не мешает
        остальным; подписки с ответом 404/410 удаляются как мёртвые.
        """
        if not self.enabled:
            self.logger.info(
                "Отправка push выключена: VAPID-ключи не заданы")
            return 0

        if not subscriptions:
            return 0

        payload = json.dumps({'title': title, 'body': body, 'url': url})
        sent = 0
        dead_endpoints: list[str] = []

        for subscription in subscriptions:
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
