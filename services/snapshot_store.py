# services/snapshot_store.py
"""Хранилище текущего снапшота на edge (W3).

Держит снапшот расписания в памяти: FastAPI-потоки читают, ingest-эндпоинт
пишет. Всё обращение к общему состоянию — под `threading.RLock` (как в
`database/file_db.py`). При старте состояние загружается с диска
(`read_snapshot`); `apply(payload)` принимает только снапшот формата
`SNAPSHOT_VERSION` — несовпадающая версия не должна вытеснять хорошие данные.

Устаревание считается от `generated_at`: данные старше `max_age` секунд
(или отсутствующие вовсе) считаются устаревшими — этим пользуется healthz (W11).
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from config.config import get_timezone
from services.snapshot import (
    SNAPSHOT_VERSION,
    read_snapshot,
    write_snapshot_atomic,
)

logger = logging.getLogger(__name__)


class SnapshotStore:
    """Потокобезопасный in-memory держатель снапшота с загрузкой/записью на диск."""

    def __init__(self, path: str, max_age: int):
        self.path = path
        self.max_age = max_age
        self._lock = threading.RLock()
        self._schools_data: dict[str, Any] = {}
        self._schools_config: dict[str, Any] = {}
        self._generated_at: datetime | None = None
        self._version: int | None = None
        self.load()

    def load(self) -> None:
        """Загружает снапшот с диска. Отсутствие/битый файл оставляет хранилище пустым."""
        snapshot = read_snapshot(self.path)
        with self._lock:
            if snapshot is None:
                self._schools_data = {}
                self._schools_config = {}
                self._generated_at = None
                self._version = None
                return
            self._set(snapshot)

    def apply(self, payload: dict[str, Any]) -> bool:
        """Применяет присланный снапшот и сохраняет его на диск.

        Принимает только `payload['version'] == SNAPSHOT_VERSION`. Иначе
        логирует и возвращает `False`, не трогая текущие данные (защита от
        подмены/несовместимого формата). Возвращает `True`, если применил.
        """
        with self._lock:
            if payload.get('version') != SNAPSHOT_VERSION:
                logger.warning(
                    "Отклонён снапшот версии %r (ожидается %d)",
                    payload.get('version'), SNAPSHOT_VERSION,
                )
                return False
            self._set(payload)
            write_snapshot_atomic(self.path, dict(payload))
            return True

    def _set(self, snapshot: dict[str, Any]) -> None:
        """Разбирает снапшот в поля. Вызывается только под `_lock`."""
        self._schools_data = snapshot.get('schools') or {}
        self._schools_config = snapshot.get('schools_config') or {}
        self._version = snapshot.get('version')
        raw = snapshot.get('generated_at')
        try:
            self._generated_at = datetime.fromisoformat(raw) if raw else None
        except (TypeError, ValueError):
            logger.warning("Некорректный generated_at в снапшоте: %r", raw)
            self._generated_at = None

    @property
    def schools_data(self) -> dict[str, Any]:
        with self._lock:
            return self._schools_data

    @property
    def schools_config(self) -> dict[str, Any]:
        with self._lock:
            return self._schools_config

    @property
    def generated_at(self) -> str | None:
        """`generated_at` снапшота в ISO-8601 (как в контракте) или `None`."""
        with self._lock:
            return self._generated_at.isoformat() if self._generated_at else None

    @property
    def version(self) -> int | None:
        with self._lock:
            return self._version

    def age_seconds(self, now: datetime | None = None) -> float | None:
        """Возраст снапшота в секундах или `None`, если данных нет.

        `now` — для тестируемости; по умолчанию текущее время в часовом поясе
        приложения. `generated_at` tz-aware, поэтому сравнение корректно.
        """
        with self._lock:
            generated = self._generated_at
        if generated is None:
            return None
        if now is None:
            now = datetime.now(get_timezone())
        return (now - generated).total_seconds()

    @property
    def is_stale(self) -> bool:
        """`True`, если данных нет или их возраст превышает `max_age` секунд."""
        age = self.age_seconds()
        if age is None:
            return True
        return age > self.max_age
