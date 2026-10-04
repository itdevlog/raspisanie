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
- subscribe дополнительно ограничен собственным `RateLimiter` по реальному
  IP клиента, чтобы публичный edge не мог завалить FileDB мусором;
  unsubscribe не лимитируется (её задача — чистка);

Роутер возвращается только когда заданы **и** VAPID-ключи, **и**
`EDGE_AUTH_SECRET`; иначе `None`, и маршруты в приложение не попадают.
`/api/push/vapid-public-key` на origin не нужен — публичный ключ отдаёт edge.
"""
from __future__ import annotations

import hmac
from collections.abc import Callable, Iterable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config.config import Config
from web.rate_limit import RateLimiter

# Безликие ответы: причина отказа наружу не раскрывается.
_FORBIDDEN_BODY = {'detail': 'Forbidden'}
_TOO_MANY_BODY = {'detail': 'Слишком много запросов'}


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
    subscribe_rate_limit: int = 30,
    window_seconds: float = 60.0,
    trusted_proxies: Iterable[str] = (),
    client_ip_fn: Callable[[Request], str] | None = None,
) -> APIRouter | None:
    """Собирает APIRouter push-API или `None`, если фича не сконфигурирована.

    `store` — любой объект с `upsert(...)`/`remove_by_endpoint(...)` (обычно
    `PushSubscriptionStore`). Секрет и VAPID-ключи по умолчанию берутся из
    `Config`; явный пустой `''` означает «выключено» (не откат к Config).
    `client_ip_fn(request) -> str` инъектируется в тестах; по умолчанию
    используется тот же резолвер IP, что и в `web/api.py` (W8).
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

    if client_ip_fn is None:
        from web.api import _client_ip

        trusted = set(trusted_proxies)

        def client_ip_fn(request: Request) -> str:
            return _client_ip(request, trusted)

    limiter = RateLimiter(max_requests=subscribe_rate_limit, window_seconds=window_seconds)
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
        # Аутентификация ДО rate-limit: запрос без секрета не тратит бюджет
        # реального edge и не может вытеснить его из окна.
        if not _authorized(request):
            return JSONResponse(status_code=403, content=_FORBIDDEN_BODY)
        if not limiter.allow(f'push-subscribe:{client_ip_fn(request)}'):
            return JSONResponse(status_code=429, content=_TOO_MANY_BODY)

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
