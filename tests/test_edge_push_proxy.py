# tests/test_edge_push_proxy.py
"""Тесты edge-прокси push-API (W17).

Публичный сайт живёт на edge; браузер никогда не ходит на origin напрямую.
Этот прокси:

- `GET /api/push/vapid-public-key` отдаёт публичный VAPID-ключ ЛОКАЛЬНО (не
  ходит на origin);
- `POST /api/push/subscribe|unsubscribe` пробрасывает тело на
  `{EDGE_ORIGIN_URL}/api/push/...` с заголовком `X-Edge-Auth`, возвращая
  клиенту upstream-статус и тело;
- ограничивает размер входящего тела (413) и таймаут upstream-вызова;
- best-effort: недоступный/отвалившийся по таймауту origin → 502 без raise;
- маршруты под `/api/`, значит покрыты общим rate-limit middleware (W8).

Сеть не поднимается: `httpx.MockTransport` перехватывает запросы и пишет их
в список, как в `test_snapshot_export.py`.
"""
import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from web.api import create_app
from web.edge_push import (
    PUSH_MAX_BYTES,
    PUSH_PROXY_TIMEOUT_SECONDS,
    create_edge_push_router,
)

_SECRET = 'edge-shared-secret'
_ORIGIN = 'https://origin.example.ru'
_VAPID_PUBLIC = 'BPublicVapidKey_0123456789'
_VAPID_PRIVATE = 'private-vapid-key'

_ENDPOINT = 'https://fcm.googleapis.com/fcm/send/abc123'
_KEYS = {'p256dh': 'public-key', 'auth': 'auth-secret'}


class _FakeConfig:
    """Config-заглушка для ingest: fail-closed эндпоинт требует непустой секрет."""

    EDGE_INGEST_SECRET = _SECRET
    SNAPSHOT_MAX_BYTES = 1024 * 1024


@pytest.fixture(autouse=True)
def _default_ingest_secret(monkeypatch):
    """create_edge_app собирает ingest fail-closed — даём непустой секрет."""
    monkeypatch.setattr('web.edge_ingest.Config', _FakeConfig)


def _sub() -> dict:
    return {
        'endpoint': _ENDPOINT,
        'keys': dict(_KEYS),
        'school_id': 'school_133',
        'kind': 'class',
        'name': '5А',
    }


def _app(client: httpx.Client, **overrides):
    """TestClient вокруг `create_app` с edge-push роутером.

    `client` — httpx.Client на MockTransport, переданный в фабрику.
    """
    router = create_edge_push_router(
        origin_url=overrides.pop('origin_url', _ORIGIN),
        edge_auth_secret=overrides.pop('edge_auth_secret', _SECRET),
        vapid_public_key=overrides.pop('vapid_public_key', _VAPID_PUBLIC),
        client=client,
        **overrides,
    )
    assert router is not None
    app = create_app(
        {'bot_data': {'schools_data': {}}},
        static_dir='/nonexistent-static-dir',
    )
    app.include_router(router)
    return TestClient(app)


class _Recorder:
    """MockTransport-хендлер: пишет запросы, отдаёт заданные ответы/ошибки."""

    def __init__(self, responses=None):
        # responses — список: int (статус) | httpx.Response | Exception.
        self.responses = list(responses or [200])
        self.calls: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = request.content
        self.calls.append({
            'method': request.method,
            'url': str(request.url),
            'headers': dict(request.headers),
            'content': body,
        })
        item = self.responses.pop(0) if self.responses else 200
        if isinstance(item, Exception):
            raise item
        if isinstance(item, httpx.Response):
            return item
        return httpx.Response(item, content=b'{"ok": true}',
                              headers={'content-type': 'application/json'})


def _client(recorder: _Recorder) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(recorder))


# --- vapid-public-key -------------------------------------------------------

def test_vapid_public_key_returned_locally():
    recorder = _Recorder([200])
    r = _app(_client(recorder)).get('/api/push/vapid-public-key')

    assert r.status_code == 200
    assert r.json() == {'key': _VAPID_PUBLIC}
    assert recorder.calls == []  # на origin не ходили — ключ локальный


def test_vapid_public_key_unconfigured_returns_404():
    recorder = _Recorder([200])
    r = _app(_client(recorder), vapid_public_key='').get('/api/push/vapid-public-key')

    assert r.status_code == 404
    assert recorder.calls == []


# --- proxy: subscribe -------------------------------------------------------

def test_subscribe_proxies_to_upstream_with_auth_header():
    recorder = _Recorder([200])
    body = _sub()
    r = _app(_client(recorder)).post('/api/push/subscribe', json=body)

    assert r.status_code == 200
    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call['method'] == 'POST'
    assert call['url'] == f'{_ORIGIN}/api/push/subscribe'
    assert call['headers']['x-edge-auth'] == _SECRET
    assert call['content']  # тело проброшено


def test_subscribe_passes_through_upstream_status_and_body():
    upstream_body = b'{"detail": "Invalid subscription"}'
    recorder = _Recorder([httpx.Response(
        422, content=upstream_body, headers={'content-type': 'application/json'}
    )])
    r = _app(_client(recorder)).post('/api/push/subscribe', json=_sub())

    assert r.status_code == 422
    assert r.content == upstream_body


def test_subscribe_preserves_json_bytes_and_content_type():
    recorder = _Recorder([200])
    body = _sub()
    _app(_client(recorder)).post('/api/push/subscribe', json=body)

    call = recorder.calls[0]
    assert call['headers']['content-type'].startswith('application/json')
    # тело байт-в-байт то, что отправил клиент
    assert json.loads(call['content']) == body


# --- proxy: unsubscribe -----------------------------------------------------

def test_unsubscribe_proxies_to_upstream():
    recorder = _Recorder([200])
    r = _app(_client(recorder)).post(
        '/api/push/unsubscribe', json={'endpoint': _ENDPOINT}
    )

    assert r.status_code == 200
    call = recorder.calls[0]
    assert call['url'] == f'{_ORIGIN}/api/push/unsubscribe'
    assert call['headers']['x-edge-auth'] == _SECRET


# --- size limit -------------------------------------------------------------

def test_oversize_body_rejected_413_without_upstream_call():
    recorder = _Recorder([200])
    payload = b'x' * (PUSH_MAX_BYTES + 1)
    r = _app(_client(recorder)).post(
        '/api/push/subscribe',
        content=payload,
        headers={'content-type': 'application/json'},
    )

    assert r.status_code == 413
    assert recorder.calls == []


def test_oversize_content_length_rejected_early_413():
    """Заведомо большой Content-Length отклоняется до чтения тела."""
    recorder = _Recorder([200])
    r = _app(_client(recorder)).post(
        '/api/push/subscribe',
        content=b'{}',
        headers={
            'content-type': 'application/json',
            'content-length': str(PUSH_MAX_BYTES + 1),
        },
    )

    assert r.status_code == 413
    assert recorder.calls == []


# --- upstream failures ------------------------------------------------------

def test_upstream_timeout_returns_502_without_raise():
    recorder = _Recorder([httpx.ConnectTimeout('too slow')])
    r = _app(_client(recorder)).post('/api/push/subscribe', json=_sub())

    assert r.status_code == 502


def test_upstream_unreachable_returns_502():
    recorder = _Recorder([httpx.ConnectError('refused')])
    r = _app(_client(recorder)).post('/api/push/subscribe', json=_sub())

    assert r.status_code == 502


def test_error_body_does_not_leak_secret():
    recorder = _Recorder([httpx.ConnectError('refused')])
    r = _app(_client(recorder)).post('/api/push/subscribe', json=_sub())

    assert _SECRET not in r.text


# --- gating -----------------------------------------------------------------

def test_factory_disabled_without_origin_url():
    assert create_edge_push_router(origin_url='', edge_auth_secret=_SECRET) is None


def test_factory_disabled_without_secret():
    assert create_edge_push_router(origin_url=_ORIGIN, edge_auth_secret='') is None


def test_factory_enabled_with_origin_and_secret_only():
    """VAPID-ключ не нужен, чтобы проксировать — нужен только origin+секрет."""
    router = create_edge_push_router(
        origin_url=_ORIGIN, edge_auth_secret=_SECRET,
        vapid_public_key='', client=_client(_Recorder([200])),
    )
    assert router is not None
    paths = {getattr(r, 'path', None) for r in router.routes}
    assert paths == {
        '/api/push/vapid-public-key',
        '/api/push/subscribe',
        '/api/push/unsubscribe',
    }


# --- rate limit coverage ----------------------------------------------------

def test_routes_are_under_api_rate_limit():
    """Прокси-маршруты под `/api/` — общий middleware отдаёт 429 после бюджета."""
    recorder = _Recorder([200])
    router = create_edge_push_router(
        origin_url=_ORIGIN, edge_auth_secret=_SECRET,
        vapid_public_key=_VAPID_PUBLIC, client=_client(recorder),
    )
    assert router is not None
    app = create_app(
        {'bot_data': {'schools_data': {}}},
        rate_limit=2,
        widget_rate_limit=2,
        window_seconds=60.0,
        static_dir='/nonexistent-static-dir',
    )
    app.include_router(router)
    client = TestClient(app)

    assert client.get('/api/push/vapid-public-key').status_code == 200
    assert client.get('/api/push/vapid-public-key').status_code == 200
    r = client.get('/api/push/vapid-public-key')
    assert r.status_code == 429
    assert r.json() == {'detail': 'Слишком много запросов'}


# --- non-blocking: sync call runs off the event loop ------------------------

def test_upstream_call_does_not_block_event_loop():
    """Синхронный httpx-вызов уходит в threadpool — loop остаётся отзывчивым.

    Доказательство честное: heartbeat-корутина тикает, пока upstream-хендлер
    ещё ВЫПОЛНЯЕТСЯ. Хендлер блокирует свой поток `time.sleep` и перед
    возвратом фиксирует, сколько тиков успело накопиться. При корректном
    `run_in_threadpool` event loop свободен и heartbeat тикает во время сна;
    при блокирующем вызове прямо в эндпоинте loop замерзает — до возврата
    хендлера не набирается ни одного тика.
    """
    import time

    HEARTBEAT_INTERVAL = 0.005
    UPSTREAM_SLEEP = 0.15  # ~30 потенциальных тиков heartbeat

    ticks = {'n': 0}
    ticks_at_handler_time = {'n': -1}

    def slow_handler(request: httpx.Request) -> httpx.Response:
        # Блокируем именно ЭТОТ (воркерный) поток, не event loop.
        time.sleep(UPSTREAM_SLEEP)
        # Фиксируем прогресс heartbeat ЗА ВРЕМЯ запроса, до возврата.
        ticks_at_handler_time['n'] = ticks['n']
        return httpx.Response(200, content=b'{"ok": true}')

    async def main():
        sync_client = httpx.Client(transport=httpx.MockTransport(slow_handler))
        router = create_edge_push_router(
            origin_url=_ORIGIN, edge_auth_secret=_SECRET,
            vapid_public_key=_VAPID_PUBLIC, client=sync_client,
        )
        assert router is not None
        app = create_app(
            {'bot_data': {'schools_data': {}}},
            static_dir='/nonexistent-static-dir',
        )
        app.include_router(router)

        from httpx import ASGITransport

        asgi = httpx.AsyncClient(transport=ASGITransport(app=app),
                                 base_url='http://test')

        async def heartbeat():
            while True:
                ticks['n'] += 1
                await asyncio.sleep(HEARTBEAT_INTERVAL)

        hb_task = asyncio.create_task(heartbeat())
        r = await asgi.post('/api/push/subscribe', json=_sub())
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass
        await asgi.aclose()
        sync_client.close()
        return r

    r = asyncio.run(main())
    assert r.status_code == 200
    # Хендлер успел отработать только если loop был свободен во время запроса.
    assert ticks_at_handler_time['n'] >= 0, "handler never ran"
    # За ~0.15 с сна при интервале 0.005 с ожидается ~30 тиков; требуем скромный
    # минимум, недостижимый при заблокированном loop (там было бы 0).
    assert ticks_at_handler_time['n'] >= 5, (
        f"event loop was blocked during upstream call "
        f"(ticks while in flight: {ticks_at_handler_time['n']})"
    )


def test_timeout_constant_is_bounded():
    assert 0 < PUSH_PROXY_TIMEOUT_SECONDS <= 30.0


@pytest.mark.parametrize('path', ['/api/push/subscribe', '/api/push/unsubscribe'])
def test_proxy_forwards_to_origin_base_without_trailing_slash(path):
    recorder = _Recorder([200])
    _app(_client(recorder), origin_url=_ORIGIN + '/').post(path, json=_sub())

    assert recorder.calls[0]['url'] == f'{_ORIGIN}{path}'


# --- edge_server wiring -----------------------------------------------------

def test_create_edge_app_registers_push_routes_when_configured(tmp_path, monkeypatch):
    """`create_edge_app` включает push-прокси при заданных origin+секрете."""
    from services.snapshot_store import SnapshotStore
    from web import edge_push
    from web.edge_server import create_edge_app

    # Патчим Config в module-е, который реально читает фабрика (config.config
    # может быть перезагружен тестами валидации — см. test_config_validation).
    monkeypatch.setattr(edge_push.Config, 'EDGE_ORIGIN_URL', _ORIGIN)
    monkeypatch.setattr(edge_push.Config, 'EDGE_AUTH_SECRET', _SECRET)
    monkeypatch.setattr(edge_push.Config, 'VAPID_PUBLIC_KEY', _VAPID_PUBLIC)

    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    client = TestClient(create_edge_app(store, static_dir=str(tmp_path / 'no-static')))

    # vapid-ключ отдаётся локально
    r = client.get('/api/push/vapid-public-key')
    assert r.status_code == 200
    assert r.json() == {'key': _VAPID_PUBLIC}


def test_create_edge_app_omits_push_routes_when_unconfigured(tmp_path, monkeypatch):
    """Без EDGE_ORIGIN_URL/секрета push-маршрутов в edge-приложении нет."""
    from services.snapshot_store import SnapshotStore
    from web import edge_push
    from web.edge_server import create_edge_app

    monkeypatch.setattr(edge_push.Config, 'EDGE_ORIGIN_URL', '')
    monkeypatch.setattr(edge_push.Config, 'EDGE_AUTH_SECRET', '')
    monkeypatch.setattr(edge_push.Config, 'VAPID_PUBLIC_KEY', _VAPID_PUBLIC)

    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    client = TestClient(create_edge_app(store, static_dir=str(tmp_path / 'no-static')))

    assert client.get('/api/push/vapid-public-key').status_code == 404
    assert client.post('/api/push/subscribe', json=_sub()).status_code == 404
