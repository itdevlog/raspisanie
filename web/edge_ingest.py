# web/edge_ingest.py
"""Ingest-эндпоинт edge `POST /internal/snapshot` (W9).

Origin публикует подписанный снапшот (W4/W5/W7) на edge; этот роутер
принимает его и подменяет состояние (`SnapshotStore.apply` — in-memory данные
плюс атомарная запись на диск через `write_snapshot_atomic`). Контракт
(спека, §3):

- тело — компактный UTF-8 JSON `serialize_snapshot`; может быть gzip
  (`Content-Encoding: gzip`), подпись при этом считается от **сырого
  распакованного** тела;
- `X-Snapshot-Signature` — HMAC-SHA256 сырого тела, hex; сверяется
  `hmac.compare_digest` (внутри `verify_signature`, устойчиво к таймингу);
- `X-Snapshot-Timestamp` — unix seconds, допуск ±300 с (защита от replay);
- размер ограничен `SNAPSHOT_MAX_BYTES`; лимит применяется и к
  распакованному телу, а распаковка ограничена сверху, чтобы gzip-бомба не
  съела память;
- `version` должен совпадать с `SNAPSHOT_VERSION`.

Любая ошибка аутентификации/валидации отдаёт один и тот же безликий ответ
(`401/409/413/422`) — наружу не уходит, что именно не так. Роутер
регистрируется отдельно и по префиксу `/internal/` не попадает под
rate-limit middleware (`web/api.py` лимитирует только `/api/`).
"""
from __future__ import annotations

import json
import math
import time
import zlib
from typing import Any, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config.config import Config
from services.snapshot import SNAPSHOT_VERSION, verify_signature

# Допуск расхождения часов origin/edge (секунды). Спека: ±300 с.
TIMESTAMP_TOLERANCE_SECONDS = 300

# Единый безликий ответ на любую ошибку — не раскрываем причину отказа.
_ERROR_BODY = {'detail': 'Snapshot rejected'}


class _Reject(Exception):
    """Внутренний сигнал «отклонить запрос» с итоговым HTTP-статусом."""

    def __init__(self, status_code: int) -> None:
        super().__init__(status_code)
        self.status_code = status_code


def create_ingest_router(
    store: Any,
    *,
    secret: str | None = None,
    max_bytes: int | None = None,
    now_fn: Callable[[], float] | None = None,
) -> APIRouter | None:
    """Собирает APIRouter с ingest-маршрутом или `None`, если секрет не задан.

    `store` — любой объект с `apply(payload) -> bool` (обычно `SnapshotStore`).
    `secret`/`max_bytes` по умолчанию берутся из `Config`
    (`EDGE_INGEST_SECRET`/`SNAPSHOT_MAX_BYTES`); `now_fn` инъектируется в тестах.

    Пустой `EDGE_INGEST_SECRET` — fail-closed: без секрета HMAC подпись
    тривиально подделывается (при reverse-proxy Caddy `/internal/snapshot`
    доступен из интернета), поэтому роутер не создаётся вовсе. `create_edge_app`
    трактует `None` как фатальную ошибку конфигурации и не поднимает сервер.
    """
    cfg = Config()
    if secret is None:
        secret = cfg.EDGE_INGEST_SECRET
    if max_bytes is None:
        max_bytes = cfg.SNAPSHOT_MAX_BYTES
    if now_fn is None:
        now_fn = time.time

    # Пустой секрет — нечего сверять: принять подпись, посчитанную от пустой
    # строки, означало бы открытый ingest. Не регистрируем маршрут.
    if not secret:
        return None

    router = APIRouter()

    @router.post('/internal/snapshot')
    async def ingest_snapshot(request: Request):
        try:
            payload = await _validate_request(request, secret, max_bytes, now_fn)
        except _Reject as reject:
            return JSONResponse(status_code=reject.status_code, content=_ERROR_BODY)
        if not store.apply(payload):
            return JSONResponse(status_code=409, content=_ERROR_BODY)
        return {'ok': True}

    return router


async def _validate_request(
    request: Request, secret: str, max_bytes: int, now_fn: Callable[[], float]
) -> dict[str, Any]:
    """Читает, распаковывает и проверяет запрос; возвращает payload или бросает _Reject."""
    raw = await request.body()
    body = _decompress_if_gzip(raw, request.headers.get('Content-Encoding'), max_bytes)
    # Лимит проверяется до дорогой криптографии/парсинга.
    if len(body) > max_bytes:
        raise _Reject(413)

    signature = request.headers.get('X-Snapshot-Signature') or ''
    if not verify_signature(secret, body, signature):
        raise _Reject(401)

    _check_timestamp(request.headers.get('X-Snapshot-Timestamp'), now_fn)

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise _Reject(422) from None
    if not isinstance(payload, dict) or payload.get('version') != SNAPSHOT_VERSION:
        raise _Reject(409)
    return payload


def _decompress_if_gzip(raw: bytes, encoding: str | None, max_bytes: int) -> bytes:
    """gzip-распаковка с жёстким лимитом вывода (защита от gzip-бомбы).

    Если декомпрессированный поток длиннее лимита — сразу `413`, не разворачивая
    его целиком. Битый/оборванный поток — `422`.
    """
    if (encoding or '').strip().lower() != 'gzip':
        return raw
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)  # gzip-обёртка
    try:
        out = decompressor.decompress(raw, max_bytes + 1)
    except zlib.error:
        raise _Reject(422) from None
    if len(out) > max_bytes:
        raise _Reject(413)
    if not decompressor.eof:
        # Поток не завершён (обрезан/повреждён) — не принимаем неполные данные.
        raise _Reject(422)
    return out


def _check_timestamp(header: str | None, now_fn: Callable[[], float]) -> None:
    """Отклоняет отсутствующий/нечисловой/вышедший за ±300 с timestamp."""
    try:
        timestamp = float(header)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise _Reject(422) from None
    if not math.isfinite(timestamp) or abs(now_fn() - timestamp) > TIMESTAMP_TOLERANCE_SECONDS:
        raise _Reject(422)
