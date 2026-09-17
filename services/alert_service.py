"""Алертинг админам при повторяющихся ошибках (T44a).

Небольшой in-memory сервис без внешних зависимостей: агрегирует ошибки по
ключу (источник + тип + краткое сообщение) в скользящем окне и решает, когда
пора один раз уведомить администраторов, чтобы повторяющиеся сбои не спамили
на каждом цикле.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

ErrorKey = str


class AlertService:
    def __init__(
        self,
        threshold: int = 3,
        window_seconds: float = 300.0,
        max_keys: int = 1000,
        max_events_per_key: int = 100,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.threshold = threshold
        self.window_seconds = float(window_seconds)
        self.max_keys = max_keys
        self.max_events_per_key = max_events_per_key
        self._now_func = now
        self._events: dict[ErrorKey, list[float]] = {}
        self._last_alert: dict[ErrorKey, float] = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

    def _now(self) -> float:
        """Текущее время в секундах (точка подмены в тестах)."""
        if self._now_func is not None:
            return float(self._now_func())
        return time.monotonic()

    @staticmethod
    def error_key(error: BaseException | None, source: str) -> ErrorKey:
        """Стабильный ключ агрегации: источник + тип + первая строка сообщения.

        Сообщение обрезается — ключ не растёт без предела и не хранит больших
        данных. Наружу (в текст алерта) сообщение не попадает.
        """
        error_type = type(error).__name__ if error is not None else 'UnknownError'
        message = str(error) if error is not None else ''
        first_line = message.strip().splitlines()[0].strip() if message.strip() else ''
        if len(first_line) > 80:
            first_line = first_line[:80]
        return f"{source}:{error_type}:{first_line}"

    def record(self, error: BaseException | None, source: str) -> int:
        """Регистрирует ошибку и возвращает число повторов за текущее окно."""
        now = self._now()
        key = self.error_key(error, source)
        with self._lock:
            events = self._events.setdefault(key, [])
            cutoff = now - self.window_seconds
            events[:] = [ts for ts in events if ts > cutoff]
            events.append(now)
            if self.max_events_per_key and len(events) > self.max_events_per_key:
                del events[:-self.max_events_per_key]
            self._evict_stale(now)
            return len(events)

    def should_alert(
        self,
        key: ErrorKey,
        threshold: int | None = None,
        window_seconds: float | None = None,
    ) -> bool:
        """True, если повторов >= порога и по ключу ещё не алертили в окне.

        Успешная проверка помечает ключ как «алерт отправлен», поэтому повторный
        вызов в том же окне вернёт False (антиспам).
        """
        now = self._now()
        effective_threshold = self.threshold if threshold is None else threshold
        window = self.window_seconds if window_seconds is None else float(window_seconds)
        with self._lock:
            events = self._events.get(key)
            if not events:
                return False
            count = sum(1 for ts in events if now - ts <= window)
            if count < effective_threshold:
                return False
            last = self._last_alert.get(key)
            if last is not None and now - last < window:
                return False
            self._last_alert[key] = now
            self.logger.warning(
                "Повторяющаяся ошибка: %s (%d раз за %.0fс)", key, count, window
            )
            return True

    def active_keys(self) -> list[ErrorKey]:
        """Ключи, по которым есть события в памяти (для диагностики/тестов)."""
        with self._lock:
            return list(self._events)

    def _evict_stale(self, now: float) -> None:
        """Чистит ключи без свежих событий и ограничивает их общее число."""
        cutoff = now - self.window_seconds
        stale = [
            key for key, events in self._events.items()
            if not any(ts > cutoff for ts in events)
        ]
        for key in stale:
            del self._events[key]
            self._last_alert.pop(key, None)
        if self.max_keys and len(self._events) > self.max_keys:
            ordered = sorted(self._events, key=lambda k: self._events[k][-1])
            for key in ordered[: len(self._events) - self.max_keys]:
                del self._events[key]
                self._last_alert.pop(key, None)
