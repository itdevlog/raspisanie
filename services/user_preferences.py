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

    def get_notification_settings(self, user_id: int) -> dict:
        """Получает настройки уведомлений пользователя"""
        preferences = self.preferences_collection.find_one({'user_id': user_id}) or {}
        return preferences.get('notifications', {
            'update_notifications': False,
            'lesson_reminders': False
        })

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
