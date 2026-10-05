# web/push_api.py
"""Публичное push-API origin (W15).

Публичный сайт живёт на edge; браузер никогда не ходит на origin напрямую.
Edge проксирует subscribe/unsubscribe на origin, аутентифицируясь общим
секретом `X-Edge-Auth` (спека, §3). Этот роутер:

- принимает `POST /api/push/subscribe` и `POST /api/push/unsubscribe`;
- сверяет `X-Edge-Auth` с `EDGE_AUTH_SECRET` через `hmac.compare_digest`;
  несовпадение/отсутствие → `403` (наружу не уходит, какой именно секрет
  ожидался, — тело безликое);
- subscribe валидирует тело и кладёт подписку в `PushSubscriptionStore`
  (`upsert` сам проверяет endpoint/keys/kind; здесь — форма тела и
  school_id/name), unsubscribe удаляет по endpoint;
- собственного rate-limit здесь НЕТ: origin вызывается только edge-сервером
  (один peer IP), поэтому локальный лимитер выродился бы в один глобальный
  bucket на весь сайт. Единственный per-client лимитер subscribe — общий
  `/api/` middleware edge (`web/api.py`, W8), который применяется и к
  `/api/push/*` (W17); edge аутентифицируется `X-Edge-Auth`.

Роутер возвращается только когда заданы **и** VAPID-ключи, **и**
`EDGE_AUTH_SECRET`; иначе `None`, и маршруты в приложение не попадают.
`/api/push/vapid-public-key` на origin не нужен — публичный ключ отдаёт edge.
"""
from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config.config import Config

# Безликий ответ: причина отказа наружу не раскрывается.
_FORBIDDEN_BODY = {'detail': 'Forbidden'}


def _constant_time_equal(provided: str | None, expected: str) -> bool:
    """Сверка секретов без утечки тайминга; кириллица/юникод не роняет запрос."""
    left = (provided or '').encode('utf-8', 'surrogatepass')
    right = expected.encode('utf-8', 'surrogatepass')
    return hmac.compare_digest(left, right)


def _as_nonempty_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def create_push_router(
    store: Any,
    *,
    edge_auth_secret: str | None = None,
    vapid_public_key: str | None = None,
    vapid_private_key: str | None = None,
) -> APIRouter | None:
    """Собирает APIRouter push-API или `None`, если фича не сконфигурирована.

    `store` — любой объект с `upsert(...)`/`remove_by_endpoint(...)` (обычно
    `PushSubscriptionStore`). Секрет и VAPID-ключи по умолчанию берутся из
    `Config`; явный пустой `''` означает «выключено» (не откат к Config).
    """
    cfg = Config()
    if edge_auth_secret is None:
        edge_auth_secret = cfg.EDGE_AUTH_SECRET
    if vapid_public_key is None:
        vapid_public_key = cfg.VAPID_PUBLIC_KEY
    if vapid_private_key is None:
        vapid_private_key = cfg.VAPID_PRIVATE_KEY

    # «Включены, только если заданы VAPID-ключи и EDGE_AUTH_SECRET».
    if not (edge_auth_secret and vapid_public_key and vapid_private_key):
        return None

    router = APIRouter()

    def _authorized(request: Request) -> bool:
        return _constant_time_equal(request.headers.get('X-Edge-Auth'), edge_auth_secret)

    async def _json_object(request: Request) -> dict[str, Any] | None:
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            return None
        return body if isinstance(body, dict) else None

    @router.post('/api/push/subscribe')
    async def push_subscribe(request: Request):
        if not _authorized(request):
            return JSONResponse(status_code=403, content=_FORBIDDEN_BODY)

        body = await _json_object(request)
        if body is None:
            return JSONResponse(status_code=422, content={'detail': 'Invalid subscription'})
        endpoint = _as_nonempty_str(body.get('endpoint'))
        school_id = _as_nonempty_str(body.get('school_id'))
        name = _as_nonempty_str(body.get('name'))
        kind = _as_nonempty_str(body.get('kind'))
        keys = body.get('keys')
        if (endpoint is None or school_id is None or name is None
                or kind is None or not isinstance(keys, dict)):
            return JSONResponse(status_code=422, content={'detail': 'Invalid subscription'})
        if not store.upsert(endpoint, keys, school_id, kind, name):
            return JSONResponse(status_code=422, content={'detail': 'Invalid subscription'})
        return {'ok': True}

    @router.post('/api/push/unsubscribe')
    async def push_unsubscribe(request: Request):
        if not _authorized(request):
            return JSONResponse(status_code=403, content=_FORBIDDEN_BODY)
        body = await _json_object(request)
        if body is None:
            return JSONResponse(status_code=422, content={'detail': 'Invalid subscription'})
        endpoint = _as_nonempty_str(body.get('endpoint'))
        if endpoint is None:
            return JSONResponse(status_code=422, content={'detail': 'Invalid subscription'})
        store.remove_by_endpoint(endpoint)
        return {'ok': True}

    return router
