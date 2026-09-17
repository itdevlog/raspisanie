"""Простые in-memory счётчики рассылок (T44b).

Только числа, без персональных данных. Агрегат выводится в лог в цикле
фонового обновления; внешний UI не требуется.
"""
from __future__ import annotations

import logging
import threading


class MetricsService:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    def incr(self, name: str, amount: int = 1) -> int:
        """Увеличивает счётчик и возвращает новое значение."""
        with self._lock:
            value = self._counters.get(name, 0) + amount
            self._counters[name] = value
            return value

    def get(self, name: str) -> int:
        """Текущее значение счётчика (0, если не задан)."""
        with self._lock:
            return self._counters.get(name, 0)

    def snapshot(self) -> dict[str, int]:
        """Копия всех счётчиков."""
        with self._lock:
            return dict(self._counters)

    def log_snapshot(self, prefix: str = "📊 Метрики рассылок") -> dict[str, int]:
        """Логирует агрегат одним сообщением и возвращает снимок."""
        snapshot = self.snapshot()
        if snapshot:
            parts = ", ".join(f"{key}={value}" for key, value in sorted(snapshot.items()))
            self.logger.info("%s: %s", prefix, parts)
        return snapshot
