# services/user_preferences.py
from typing import Dict, Optional
from datetime import datetime

class UserPreferencesService:
    """Сервис для управления предпочтениями пользователей"""
    
    def __init__(self, db):
        self.db = db
        self.preferences_collection = db.get_collection('user_preferences')
    
    def get_notification_settings(self, user_id: int) -> Dict:
        """Получает настройки уведомлений пользователя"""
        preferences = self.preferences_collection.find_one({'user_id': user_id}) or {}
        return preferences.get('notifications', {
            'exchange_notifications': True,  # По умолчанию включены
            'update_notifications': False,
            'lesson_reminders': False
        })
    
    def set_notification_settings(self, user_id: int, settings: Dict) -> bool:
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
    
    def disable_exchange_notifications(self, user_id: int) -> bool:
        """Отключает уведомления о заменах для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['exchange_notifications'] = False
        return self.set_notification_settings(user_id, settings)
    
    def enable_exchange_notifications(self, user_id: int) -> bool:
        """Включает уведомления о заменах для пользователя"""
        settings = self.get_notification_settings(user_id)
        settings['exchange_notifications'] = True
        return self.set_notification_settings(user_id, settings)
    
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