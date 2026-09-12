# services/user_preferences.py
"""Настройки уведомлений разделены на два независимых хранилища.

- Замены (exchange) — настройки per-school: единственный источник
  `UserService.get_user_notification_settings` / `set_user_notification_settings`.
- Обновления (update_notifications) — администраторский флаг: единственный
  писатель и читатель здесь, в `UserPreferencesService`. UI (`settings.py`) и
  фоновый апдейтер (`core/background_updater.py`) читают его отсюда же.

Кросс-запись между хранилищами запрещена: exchange пишется только через
`UserService`, update — только через `UserPreferencesService`.
"""
from datetime import datetime


class UserPreferencesService:
    """Сервис для управления предпочтениями пользователей"""

    def __init__(self, db):
        self.db = db
        self.preferences_collection = db.get_collection('user_preferences')

    @staticmethod
    def _default_settings() -> dict:
        """Настройки уведомлений по умолчанию (единая точка)."""
        return {
            'update_notifications': False,
            'lesson_reminders': False,
            'daily_digest': False,
            'quiet_hours': {'enabled': False, 'start': 22, 'end': 7},
        }

    def get_notification_settings(self, user_id: int) -> dict:
        """Получает настройки уведомлений пользователя"""
        preferences = self.preferences_collection.find_one({'user_id': user_id}) or {}
        settings = preferences.get('notifications')
        if not settings:
            return self._default_settings()
        # Дополняем недостающие ключи (обратная совместимость со старыми записями)
        merged = self._default_settings()
        merged.update(settings)
        return merged

    def set_notification_settings(self, user_id: int, settings: dict) -> bool:
        """Устанавливает настройки уведомлений пользователя"""
        preferences = self.preferences_collection.find_one({'user_id': user_id}) or {}

        preferences['user_id'] = user_id
        preferences['notifications'] = settings
        preferences['updated_at'] = datetime.now().isoformat()

        if 'created_at' not in preferences:
            preferences['created_at'] = datetime.now().isoformat()

        self.preferences_collection.update_one(
            {'user_id': user_id},
            preferences,
            upsert=True
        )
        return True

    def disable_update_notifications(self, user_id: int) -> bool:
        """Отключает уведомления об обновлениях для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['update_notifications'] = False
        return self.set_notification_settings(user_id, settings)

    def enable_update_notifications(self, user_id: int) -> bool:
        """Включает уведомления об обновлениях для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['update_notifications'] = True
        return self.set_notification_settings(user_id, settings)

    def toggle_update_notifications(self, user_id: int) -> bool:
        """Переключает уведомления об обновлениях для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['update_notifications'] = not settings.get('update_notifications', False)
        return self.set_notification_settings(user_id, settings)

    def enable_lesson_reminders(self, user_id: int) -> bool:
        """Включает напоминания об уроках для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['lesson_reminders'] = True
        return self.set_notification_settings(user_id, settings)

    def disable_lesson_reminders(self, user_id: int) -> bool:
        """Отключает напоминания об уроках для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['lesson_reminders'] = False
        return self.set_notification_settings(user_id, settings)

    def toggle_lesson_reminders(self, user_id: int) -> bool:
        """Переключает напоминания об уроках для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['lesson_reminders'] = not settings.get('lesson_reminders', False)
        return self.set_notification_settings(user_id, settings)

    def enable_daily_digest(self, user_id: int) -> bool:
        """Включает дайджест дня для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['daily_digest'] = True
        return self.set_notification_settings(user_id, settings)

    def disable_daily_digest(self, user_id: int) -> bool:
        """Отключает дайджест дня для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['daily_digest'] = False
        return self.set_notification_settings(user_id, settings)

    def toggle_daily_digest(self, user_id: int) -> bool:
        """Переключает дайджест дня для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['daily_digest'] = not settings.get('daily_digest', False)
        return self.set_notification_settings(user_id, settings)

    def enable_quiet_hours(self, user_id: int, start: int = 22, end: int = 7) -> bool:
        """Включает тихие часы (интервал может пересекать полночь)."""
        settings = self.get_notification_settings(user_id)
        settings['quiet_hours'] = {'enabled': True, 'start': start, 'end': end}
        return self.set_notification_settings(user_id, settings)

    def disable_quiet_hours(self, user_id: int) -> bool:
        """Отключает тихие часы, сохраняя границы интервала."""
        settings = self.get_notification_settings(user_id)
        quiet = dict(settings.get('quiet_hours') or {})
        quiet['enabled'] = False
        quiet.setdefault('start', 22)
        quiet.setdefault('end', 7)
        settings['quiet_hours'] = quiet
        return self.set_notification_settings(user_id, settings)

    def toggle_quiet_hours(self, user_id: int) -> bool:
        """Переключает тихие часы для пользователя."""
        settings = self.get_notification_settings(user_id)
        if (settings.get('quiet_hours') or {}).get('enabled'):
            return self.disable_quiet_hours(user_id)
        return self.enable_quiet_hours(user_id)
