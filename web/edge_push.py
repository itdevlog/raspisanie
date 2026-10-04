# web/edge_push.py
"""Edge-прокси публичного push-API (W17).

Публичный сайт живёт на edge; браузер никогда не ходит на origin напрямую.
Этот роутер закрывает push-часть публичного контракта:

- `GET /api/push/vapid-public-key` — отдаёт `VAPID_PUBLIC_KEY` **локально**,
  с edge; на origin не ходит. Если ключ не задан, маршрута нет вовсе →
  `404` (фича Web Push на этом узле не сконфигурирована);
- `POST /api/push/subscribe` и `POST /api/push/unsubscribe` — проксируют
  **сырое** тело на `{EDGE_ORIGIN_URL}/api/push/...` с заголовком
  `X-Edge-Auth: EDGE_AUTH_SECRET` (origin, W15, сверяет его constant-time),
  возвращая клиенту upstream-статус и тело как есть;
- размер входящего тела ограничен `PUSH_MAX_BYTES` (`413`), upstream-вызов
  ограничен `PUSH_PROXY_TIMEOUT_SECONDS`;
- upstream недоступен/отвалился по таймауту → `502` без исключения (edge не
  должен падать из-за origin);
- маршруты начинаются с `/api/`, поэтому попадают под общий rate-limit
  middleware (`web/api.py`, W8) — своего лимитера здесь нет.

Роутер включается, только когда заданы **и** `EDGE_ORIGIN_URL`, **и**
`EDGE_AUTH_SECRET`; иначе `None` (как `create_push_router` в W15). Публичный
VAPID-ключ для прокси не нужен: без него прокси-mаршруты живут, а
`vapid-public-key` даёт `404`.

Синхронный `httpx.Client` вызывается через `starlette.concurrency.run_in_threadpool`
(эндпоинт async), поэтому блокирующий вызов не держит event loop и при этом
переиспользуется один клиент с пулом соединений (в отличие от async-клиента
на каждый запрос).
"""
from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from config.config import Config

logger = logging.getLogger(__name__)

# Максимальный размер принимаемого edge тела (защита от гигантов). Публичный
# push payload — endpoint + ключи + несколько строк, 64 КиБ с большим запасом.
PUSH_MAX_BYTES = 64 * 1024

# Таймаут одного upstream-вызова. Меньше, чем PUBLISH_TIMEOUT_SECONDS (30 с):
# клиент ждёт ответ синхронно, и лучше быстро вернуть 502, чем держать запрос.
PUSH_PROXY_TIMEOUT_SECONDS = 10.0

# Безликий ответ при недоступном origin — деталей сети наружу не отдаём.
_UPSTREAM_ERROR_BODY = {'detail': 'Origin unavailable'}
_OVERSIZE_BODY = {'detail': 'Payload too large'}
_NOT_CONFIGURED_BODY = {'detail': 'Not found'}


def create_edge_push_router(
    *,
    origin_url: str | None = None,
    edge_auth_secret: str | None = None,
    vapid_public_key: str | None = None,
    max_bytes: int | None = None,
    client: httpx.Client | None = None,
) -> APIRouter | None:
    """Собирает APIRouter edge-push или `None`, если прокси не сконфигурирован.

    `origin_url`/`edge_auth_secret`/`vapid_public_key` по умолчанию берутся из
    `Config`; явный пустой `''` означает «выключено» (не откат к Config).
    `client` инъектируется в тестах (сюда передаётся клиент на
    `httpx.MockTransport`); по умолчанию создаётся собственный `httpx.Client`.
    """
    cfg = Config()
    if origin_url is None:
        origin_url = cfg.EDGE_ORIGIN_URL
    if edge_auth_secret is None:
        edge_auth_secret = cfg.EDGE_AUTH_SECRET
    if vapid_public_key is None:
        vapid_public_key = cfg.VAPID_PUBLIC_KEY
    if max_bytes is None:
        max_bytes = PUSH_MAX_BYTES

    # «Включены, только если заданы EDGE_ORIGIN_URL и EDGE_AUTH_SECRET».
    # Без них проксировать некуда/нечем — маршрутов нет.
    if not (origin_url and edge_auth_secret):
        return None

    # Нормализуем базовый URL без хвостового слэша, чтобы не плодить '//'.
    base = origin_url.rstrip('/')
    # Один клиент на роутер с пулом соединений — переиспользуется между
    # запросами (в отличие от async-клиента на каждый вызов). В тестах
    # подменяется клиентом на MockTransport.
    http = client if client is not None else httpx.Client()
    router = APIRouter()

    @router.get('/api/push/vapid-public-key')
    async def vapid_public_key_route():
        # Ключ отдаётся локально; если не задан — маршрута в приложении нет
        # (роутер сконфигурирован не был для Web Push на этом узле).
        if not vapid_public_key:
            return JSONResponse(status_code=404, content=_NOT_CONFIGURED_BODY)
        return {'key': vapid_public_key}

    async def _proxy(request: Request) -> Response:
        # Ранний отказ по Content-Length: не тянем в память заведомо большой
        # запрос. Точная проверка ниже — заголовку не доверяем (может отсутствовать).
        declared = request.headers.get('Content-Length')
        if declared is not None:
            try:
                if int(declared) > max_bytes:
                    return JSONResponse(status_code=413, content=_OVERSIZE_BODY)
            except ValueError:
                return JSONResponse(status_code=413, content=_OVERSIZE_BODY)

        body = await request.body()
        if len(body) > max_bytes:
            return JSONResponse(status_code=413, content=_OVERSIZE_BODY)

        content_type = request.headers.get('Content-Type') or 'application/json'
        headers = {
            'X-Edge-Auth': edge_auth_secret,
            'Content-Type': content_type,
        }
        url = f'{base}{request.url.path}'

        try:
            # Тело и заголовки пробрасываются; статус/тело ответа — как есть.
            response = await run_in_threadpool(_send, http, url, body, headers)
        except Exception as e:  # noqa: BLE001 - best-effort: origin не должен ронять edge
            logger.warning("Push-прокси на origin не удался (%s): %s", url, e)
            return JSONResponse(status_code=502, content=_UPSTREAM_ERROR_BODY)

        return Response(
            content=response.content,
            status_code=response.status_code,
            headers=_passthrough_headers(response),
        )

    @router.post('/api/push/subscribe')
    async def push_subscribe(request: Request):
        return await _proxy(request)

    @router.post('/api/push/unsubscribe')
    async def push_unsubscribe(request: Request):
        return await _proxy(request)

    return router


def _send(client: httpx.Client, url: str, body: bytes, headers: dict[str, str]) -> httpx.Response:
    """Синхронный upstream-вызов с жёстким таймаутом.

    Выполняется в threadpool (`run_in_threadpool`), чтобы не блокировать event
    loop. Таймаут задаём явно, не полагаясь на значения по умолчанию клиента.
    """
    return client.post(url, content=body, headers=headers,
                       timeout=PUSH_PROXY_TIMEOUT_SECONDS)


def _passthrough_headers(response: httpx.Response) -> dict[str, str]:
    """Заголовки upstream, безопасные к пробросу (без hop-by-hop/длины)."""
    skipped = {'content-length', 'transfer-encoding', 'connection', 'content-encoding'}
    return {
        name: value
        for name, value in response.headers.items()
        if name.lower() not in skipped
    }
