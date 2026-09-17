# services/user_repository.py
"""Слой доступа к данным пользователей.

Единая точка чтения пользователей и их настроек для сервисов и фоновых
задач. Прячет `.db` от потребителей: `NotificationService`,
`core/background_updater.py` и `handlers/common/settings.py` больше не
обращаются к `user_service.db` напрямую, а получают нужные срезы через
именованные методы репозитория.

Репозиторий не дублирует хранилище: чтение делегируется `UserService`, а
настройки — `UserPreferencesService`. Лёгкие duck-typed сервисы (например,
фейки в тестах), у которых есть только `db`, поддерживаются за счёт
фолбэка на чтение коллекции `users`.
"""
from __future__ import annotations

from typing import Any

from services.user_preferences import UserPreferencesService


class UserRepository:
    """Именованные срезы пользователей поверх `UserService`/`FileDB`."""

    def __init__(self, user_service: Any):
        self.user_service = user_service
        self.db = user_service.db
        self._preferences: UserPreferencesService | None = None

    @property
    def preferences(self) -> UserPreferencesService:
        """Сервис настроек пользователя (создаётся лениво, один раз)."""
        if self._preferences is None:
            self._preferences = UserPreferencesService(self.db)
        return self._preferences

    def get_preferences_service(self) -> UserPreferencesService:
        """Явный аксессор настроек — альтернатива свойству `preferences`."""
        return self.preferences

    def iter_users_with_classes(self) -> list[dict]:
        """Пользователи, у которых выбран хотя бы один класс.

        Для реального `UserService` делегирует его методу; для лёгких сервисов
        без него читает коллекцию `users` напрямую.
        """
        getter = getattr(self.user_service, 'get_users_with_classes', None)
        if callable(getter):
            return list(getter())
        collection = self.db.get_collection('users')
        return [user for user in collection.find() if user.get('school_classes')]

    def get_users_by_class(self, school_id: str, class_name: str) -> list[int]:
        """ID пользователей класса школы с включёнными для школы уведомлениями.

        Сравнение класса регистронезависимое; отсутствие настроек для школы
        трактуется как «включено» (`True`).
        """
        target = class_name.lower()
        result: list[int] = []
        for user in self.iter_users_with_classes():
            user_id = user.get('user_id')
            if not user_id:
                continue
            classes = user.get('school_classes') or {}
            if (classes.get(school_id) or '').lower() != target:
                continue
            settings = user.get('notification_settings') or {}
            if settings.get(school_id, True):
                result.append(user_id)
        return result

    def get_user_school(self, user_id: int) -> str:
        """Текущая школа пользователя (делегирует `UserService`)."""
        return self.user_service.get_user_school(user_id)

    def get_user_class(self, user_id: int, school_id: str | None = None) -> str | None:
        """Класс пользователя для школы (делегирует `UserService`)."""
        return self.user_service.get_user_class(user_id, school_id)

    def get_settings_map(self) -> dict[int, dict]:
        """Пакетно `{user_id: настройки}` одним проходом (делегирует настройкам)."""
        return self.preferences.get_settings_map()

    def get_notification_settings(self, user_id: int) -> dict:
        """Настройки уведомлений пользователя (делегирует настройкам)."""
        return self.preferences.get_notification_settings(user_id)
