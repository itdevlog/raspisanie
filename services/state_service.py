# services/state_service.py
from typing import Dict, List, Optional, Any
from services.cache_service import CacheService
import logging

class UserStateService:
    """
    Сервис для управления временным состоянием пользователей
    Заменяет глобальные переменные _teacher_lists, _room_lists и т.д.
    """
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.logger = logging.getLogger(__name__)
    
    def set_user_list(self, user_id: int, list_type: str, items: List[str]) -> None:
        """Сохраняет список элементов для пользователя"""
        key = f"user_{user_id}_{list_type}"
        self.cache_service.set(key, items)
        self.logger.debug(f"Saved {len(items)} items for user {user_id}, type: {list_type}")
    
    def get_user_list(self, user_id: int, list_type: str) -> Optional[List[str]]:
        """Получает сохраненный список элементов пользователя"""
        key = f"user_{user_id}_{list_type}"
        items = self.cache_service.get(key)
        if items:
            self.logger.debug(f"Retrieved {len(items)} items for user {user_id}, type: {list_type}")
        return items
    
    def set_user_page(self, user_id: int, list_type: str, page: int) -> None:
        """Сохраняет текущую страницу для пользователя"""
        key = f"user_{user_id}_{list_type}_page"
        self.cache_service.set(key, page)
    
    def get_user_page(self, user_id: int, list_type: str, default: int = 0) -> int:
        """Получает текущую страницу пользователя"""
        key = f"user_{user_id}_{list_type}_page"
        return self.cache_service.get(key) or default
    
    def clear_user_state(self, user_id: int, list_type: str = None) -> None:
        """Очищает состояние пользователя"""
        if list_type:
            # Очищаем только конкретный тип
            keys_to_remove = [
                f"user_{user_id}_{list_type}",
                f"user_{user_id}_{list_type}_page"
            ]
        else:
            # Очищаем все состояние пользователя (сложнее, нужно знать все ключи)
            # Пока просто очищаем известные типы
            known_types = ['teachers', 'rooms', 'search_teachers', 'search_rooms']
            keys_to_remove = []
            for ltype in known_types:
                keys_to_remove.extend([
                    f"user_{user_id}_{ltype}",
                    f"user_{user_id}_{ltype}_page"
                ])
        
        # В текущей реализации CacheService нет массового удаления,
        # поэтому просто устанавливаем значения в None
        for key in keys_to_remove:
            self.cache_service.set(key, None)
        
        self.logger.debug(f"Cleared state for user {user_id}, type: {list_type or 'all'}")
    
    def get_teacher_index(self, user_id: int, teacher_name: str) -> Optional[int]:
        """Получает индекс преподавателя в сохраненном списке"""
        teachers_list = self.get_user_list(user_id, 'teachers')
        if teachers_list and teacher_name in teachers_list:
            return teachers_list.index(teacher_name)
        return None
    
    def get_room_index(self, user_id: int, room_name: str) -> Optional[int]:
        """Получает индекс кабинета в сохраненном списке"""
        rooms_list = self.get_user_list(user_id, 'rooms')
        if rooms_list and room_name in rooms_list:
            return rooms_list.index(room_name)
        return None