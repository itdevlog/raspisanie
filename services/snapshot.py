# services/snapshot.py
"""Формат v1 публичного снапшота расписания (origin → edge).

Снапшот — самодостаточный JSON-словарь `{version, generated_at, schools,
schools_config}`, который origin публикует на edge. Здесь собрана только
«механика» контракта: сборка, компактная сериализация, HMAC-подпись и
атомарная запись/чтение файла. Публикация (W4) и хранилище edge (W3)
потребляют эти функции и не дублируют формат.

Атомарная запись повторяет подход `database/file_db.py`: временный файл в
той же директории, `fsync` данных, `os.replace`, затем `fsync` директории —
на диске всегда либо целая старая, либо целая новая версия.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Any

from config.config import get_timezone

logger = logging.getLogger(__name__)

# Версия формата снапшота. Edge принимает только совпадающую (W3/W9).
SNAPSHOT_VERSION = 1


def build_snapshot(
    schools_data: dict[str, Any],
    schools_config: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Собирает снапшот формата v1, проставляя версию и `generated_at`.

    `now` — для тестируемости; по умолчанию текущее время в часовом поясе
    приложения (осознанно tz-aware ISO-8601, как в контракте).
    """
    if now is None:
        now = datetime.now(get_timezone())
    return {
        'version': SNAPSHOT_VERSION,
        'generated_at': now.isoformat(),
        'schools': schools_data,
        'schools_config': schools_config,
    }


def serialize_snapshot(snapshot: dict[str, Any]) -> bytes:
    """Сериализует снапшот в компактный UTF-8 JSON и логирует размер.

    `ensure_ascii=False` — кириллица в UTF-8; `separators=(',', ':')` — без
    пробелов, чтобы мегабайтные выгрузки не раздувались. Возвращает `bytes`:
    подпись (W4) считается от сырого тела.
    """
    body = json.dumps(
        snapshot, ensure_ascii=False, separators=(',', ':')
    ).encode('utf-8')
    logger.info("Снапшот сериализован: %d байт", len(body))
    return body


def sign_payload(secret: str, body: bytes) -> str:
    """HMAC-SHA256 сырого тела, hex — значение заголовка `X-Snapshot-Signature`."""
    return hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, sig: str) -> bool:
    """Проверяет подпись через `hmac.compare_digest` (устойчиво к таймингу)."""
    expected = sign_payload(secret, body)
    return hmac.compare_digest(expected, sig)


def write_snapshot_atomic(path: str, snapshot: dict[str, Any]) -> None:
    """Атомарно и долговечно записывает снапшот по пути `path`.

    Пишем во временный файл в той же директории, сбрасываем на диск, делаем
    `os.replace` и `fsync` директории — при сбое питания файл остаётся целым
    (старым или новым). Ошибка не глотается: временный файл удаляется, а
    исключение уходит вызывающему.
    """
    dir_name = os.path.dirname(path) or '.'
    os.makedirs(dir_name, exist_ok=True)
    fd = -1
    temp_path = ''
    try:
        fd, temp_path = tempfile.mkstemp(
            dir=dir_name, prefix='.snapshot_tmp_', suffix='.json'
        )
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            fd = -1  # fdopen закрывает дескриптор
            f.write(serialize_snapshot(snapshot).decode('utf-8'))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
        temp_path = ''
        _fsync_dir(dir_name)
    finally:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def read_snapshot(path: str) -> dict[str, Any] | None:
    """Читает снапшот; при отсутствии или битом JSON возвращает `None`."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Не удалось прочитать снапшот %s: %s", path, e)
        return None


def _fsync_dir(dir_name: str) -> None:
    """Сбрасывает запись директории на диск, чтобы rename пережил сбой питания."""
    try:
        dir_fd = os.open(dir_name, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)
