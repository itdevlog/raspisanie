# services/subscription_service.py
"""Подписки пользователей на преподавателей и кабинеты.

Хранилище: коллекция `subscriptions`, по одному документу на пару
`{user_id, school_id}` со списком `items: [{'kind', 'name'}]`. При таком
масштабе поиск подписчиков сканирует коллекцию — это приемлемо.
"""
import logging

VALID_KINDS = {'teacher', 'room'}


class SubscriptionService:
    def __init__(self, db):
        self.db = db
        self.collection = db.get_collection('subscriptions')
        self.logger = logging.getLogger(__name__)

    def _find_doc(self, user_id: int, school_id: str) -> dict | None:
        return self.collection.find_one({'user_id': user_id, 'school_id': school_id})

    def _has_item(self, doc: dict, kind: str, name: str) -> bool:
        return any(
            item.get('kind') == kind and item.get('name') == name
            for item in doc.get('items', [])
        )

    def subscribe(self, user_id: int, school_id: str, kind: str, name: str) -> bool:
        """Добавляет подписку. Идемпотентно. False — при неверном kind или ошибке записи."""
        if kind not in VALID_KINDS or not name:
            return False

        doc = self._find_doc(user_id, school_id)
        if doc:
            if self._has_item(doc, kind, name):
                return True
            items = list(doc.get('items', []))
            items.append({'kind': kind, 'name': name})
            return self.collection.update_one(
                {'user_id': user_id, 'school_id': school_id},
                {'items': items},
            )
        return self.collection.insert_one({
            'user_id': user_id,
            'school_id': school_id,
            'items': [{'kind': kind, 'name': name}],
        })

    def unsubscribe(self, user_id: int, school_id: str, kind: str, name: str) -> bool:
        """Удаляет подписку. False — если её не было, kind неверен или ошибка записи."""
        if kind not in VALID_KINDS:
            return False

        doc = self._find_doc(user_id, school_id)
        if not doc or not self._has_item(doc, kind, name):
            return False

        items = [
            item for item in doc.get('items', [])
            if not (item.get('kind') == kind and item.get('name') == name)
        ]
        return self.collection.update_one(
            {'user_id': user_id, 'school_id': school_id},
            {'items': items},
        )

    def get_subscriptions(self, user_id: int, school_id: str) -> list[tuple[str, str]]:
        """Возвращает список подписок пользователя: [(kind, name), ...]."""
        doc = self._find_doc(user_id, school_id)
        if not doc:
            return []
        return [
            (item.get('kind'), item.get('name'))
            for item in doc.get('items', [])
            if item.get('kind') and item.get('name')
        ]

    def is_subscribed(self, user_id: int, school_id: str, kind: str, name: str) -> bool:
        """Проверяет наличие подписки (для UI-переключателя)."""
        if kind not in VALID_KINDS:
            return False
        doc = self._find_doc(user_id, school_id)
        return bool(doc and self._has_item(doc, kind, name))

    def get_subscribers(self, school_id: str, kind: str, name: str) -> list[int]:
        """Все user_id, подписанные на сущность в школе."""
        if kind not in VALID_KINDS:
            return []
        subscribers = []
        for doc in self.collection.find({'school_id': school_id}):
            if self._has_item(doc, kind, name):
                user_id = doc.get('user_id')
                if user_id is not None:
                    subscribers.append(user_id)
        return subscribers
