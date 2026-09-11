import time
import threading
from typing import Any, Optional, Dict

class CacheService:
    def __init__(self, ttl: int = 300, max_entries: Optional[int] = 10_000):
        self.cache: Dict[str, tuple] = {}
        self.ttl = ttl
        self.max_entries = max_entries
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Получает значение из кэша"""
        with self._lock:
            entry = self.cache.get(key)
            if entry is not None:
                data, timestamp = entry
                if time.time() - timestamp < self.ttl:
                    return data
                # Просроченный кэш
                del self.cache[key]
        return None

    def set(self, key: str, data: Any):
        """Устанавливает значение в кэш, ограничивая размер."""
        with self._lock:
            self.cache[key] = (data, time.time())
            if self.max_entries and len(self.cache) > self.max_entries:
                self._evict()

    def _evict(self):
        """Вытесняет просроченные, затем самые старые записи до max_entries."""
        now = time.time()
        # 1) просроченные
        for k in [k for k, (_, ts) in self.cache.items() if now - ts >= self.ttl]:
            del self.cache[k]
        # 2) если всё ещё превышаем лимит — самые старые
        while self.cache and self.max_entries and len(self.cache) > self.max_entries:
            oldest = min(self.cache.items(), key=lambda kv: kv[1][1])[0]
            del self.cache[oldest]

    def delete(self, key: str) -> bool:
        """Удаляет ключ. Возвращает True, если ключ существовал"""
        with self._lock:
            if key in self.cache:
                del self.cache[key]
                return True
        return False

    def delete_prefix(self, prefix: str):
        """Удаляет все ключи с указанным префиксом"""
        with self._lock:
            for key in [k for k in self.cache if k.startswith(prefix)]:
                del self.cache[key]

    def clear(self):
        """Очищает весь кэш"""
        with self._lock:
            self.cache.clear()

    def clear_expired(self):
        """Очищает только просроченные записи"""
        now = time.time()
        with self._lock:
            for key in [k for k, (_, ts) in self.cache.items() if now - ts >= self.ttl]:
                del self.cache[key]

    def get_stats(self) -> Dict:
        """Возвращает статистику кэша (O(n), без сериализации данных)."""
        now = time.time()
        with self._lock:
            total = len(self.cache)
            expired = sum(1 for _, ts in self.cache.values() if now - ts >= self.ttl)
            # оценка памяти: примерная суммарная длина строковых значений
            approx = sum(len(k) for k in self.cache)
            for _, (data, _ts) in self.cache.items():
                if isinstance(data, str):
                    approx += len(data)
        return {
            'total_entries': total,
            'expired_entries': expired,
            'active_entries': total - expired,
            'memory_approx_chars': approx,
        }
