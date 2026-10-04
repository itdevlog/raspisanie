# services/push_store.py
"""Хранилище Web Push-подписок.

Коллекция FileDB `web_push_subscriptions`, по одному документу на уникальный
`endpoint`:

    {'endpoint': str, 'keys': {'p256dh': str, 'auth': str},
     'school_id': str, 'kind': str, 'name': str, 'created_at': iso8601}

`endpoint` — ключ уникальности: `upsert` пишет через
`update_one({'endpoint': ...}, ..., upsert=True)`, поэтому повторный вызов для
того же endpoint обновляет существующий документ, а не добавляет дубль.

MVP создаёт только `kind='class'` (фронтенд предлагает opt-in класса);
`kind`/`name` оставлены под будущие entity-подписки (`teacher`/`room`).
Отправка push здесь не выполняется — это слой хранения.
"""
import logging
from collections.abc import Iterable
from datetime import datetime

from config.config import get_timezone

VALID_KINDS = {'class', 'teacher', 'room'}

# Разумный предел длины endpoint: штатные URL push-сервисов (FCM/APNs/Mozilla)
# заметно короче; отсекаем мусор и попытки раздуть файл БД.
MAX_ENDPOINT_LENGTH = 2048


class PushSubscriptionStore:
    """Хранилище подписок поверх коллекции FileDB `web_push_subscriptions`."""

    def __init__(self, db):
        self.db = db
        self.collection = db.get_collection('web_push_subscriptions')
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _valid_endpoint(endpoint) -> bool:
        if not isinstance(endpoint, str):
            return False
        if not endpoint.startswith('https://'):
            return False
        return len(endpoint) <= MAX_ENDPOINT_LENGTH

    @staticmethod
    def _valid_keys(keys) -> bool:
        if not isinstance(keys, dict):
            return False
        p256dh = keys.get('p256dh')
        auth = keys.get('auth')
        return bool(
            isinstance(p256dh, str) and p256dh
            and isinstance(auth, str) and auth
        )

    def upsert(self, endpoint: str, keys: dict, school_id: str,
               kind: str, name: str) -> bool:
        """Создаёт или обновляет подписку по `endpoint`. False — при невалидных данных."""
        if not self._valid_endpoint(endpoint):
            return False
        if not self._valid_keys(keys):
            return False
        if kind not in VALID_KINDS:
            return False

        now = datetime.now(get_timezone()).isoformat()
        return self.collection.update_one(
            {'endpoint': endpoint},
            {
                'keys': dict(keys),
                'school_id': school_id,
                'kind': kind,
                'name': name,
                'created_at': now,
            },
            upsert=True,
        )

    def remove_by_endpoint(self, endpoint: str) -> bool:
        """Удаляет подписку по endpoint. False — если её не было или ошибка записи."""
        return self.collection.delete_one({'endpoint': endpoint})

    def find_matching(self, school_id: str, kind: str, name: str) -> list[dict]:
        """Подписки, совпадающие по всем трём полям (school_id, kind, name)."""
        return self.collection.find(
            {'school_id': school_id, 'kind': kind, 'name': name})

    def remove_dead(self, endpoints: Iterable[str]) -> int:
        """Удаляет подписки для перечисленных endpoints (404/410 при отправке).

        Возвращает число удалённых записей.
        """
        removed = 0
        for endpoint in endpoints:
            if self.collection.delete_one({'endpoint': endpoint}):
                removed += 1
        return removed

    def cleanup_stale(self, older_than: datetime) -> int:
        """Удаляет подписки, созданные раньше `older_than`.

        Сравнивает `created_at` (iso8601) с cutoff; записи с датой равной
        cutoff не считаются устаревшими. Возвращает число удалённых.
        """
        cutoff = older_than.isoformat()
        removed = 0
        for doc in self.collection.find():
            created_at = doc.get('created_at')
            if created_at is None or created_at < cutoff:
                if self.collection.delete_one({'endpoint': doc.get('endpoint')}):
                    removed += 1
        return removed
