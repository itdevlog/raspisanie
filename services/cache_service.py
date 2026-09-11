import time
from typing import Any, Optional, Dict
import json

class CacheService:
    def __init__(self, ttl: int = 300):  # 5 минут по умолчанию
        self.cache: Dict[str, tuple] = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Получает значение из кэша"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                # Удаляем просроченный кэш
                del self.cache[key]
        return None
    
    def set(self, key: str, data: Any):
        """Устанавливает значение в кэш"""
        self.cache[key] = (data, time.time())

    def delete(self, key: str) -> bool:
        """Удаляет ключ из кэша. Возвращает True, если ключ существовал"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False

    def delete_prefix(self, prefix: str):
        """Удаляет все ключи с указанным префиксом"""
        keys_to_remove = [key for key in self.cache if key.startswith(prefix)]
        for key in keys_to_remove:
            del self.cache[key]
    
    def clear(self):
        """Очищает весь кэш"""
        self.cache.clear()
    
    def clear_expired(self):
        """Очищает только просроченные записи"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self.cache.items()
            if current_time - timestamp >= self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
    
    def get_stats(self) -> Dict:
        """Возвращает статистику кэша"""
        current_time = time.time()
        total_entries = len(self.cache)
        expired_entries = len([
            key for key, (_, timestamp) in self.cache.items()
            if current_time - timestamp >= self.ttl
        ])
        
        return {
            'total_entries': total_entries,
            'expired_entries': expired_entries,
            'active_entries': total_entries - expired_entries,
            'memory_usage': f"{sum(len(str(data)) for data, _ in self.cache.values())} chars"
        }