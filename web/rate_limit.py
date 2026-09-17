# web/rate_limit.py
"""In-memory rate limiter на stdlib (скользящее окно)."""
import time
from collections import deque


class RateLimiter:
    """Скользящее окно по ключу (IP/токен).

    ``max_requests <= 0`` отключает лимит.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        if self.max_requests <= 0:
            return True
        if now is None:
            now = time.monotonic()
        threshold = now - self.window_seconds
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= threshold:
            hits.popleft()
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def cleanup(self, now: float | None = None) -> None:
        if now is None:
            now = time.monotonic()
        threshold = now - self.window_seconds
        for key in list(self._hits):
            hits = self._hits[key]
            while hits and hits[0] <= threshold:
                hits.popleft()
            if not hits:
                del self._hits[key]
