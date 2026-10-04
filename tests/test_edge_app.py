# tests/test_edge_app.py
"""Тесты edge-приложения (W10): сборка `create_edge_app` и раннер.

Покрываем реальное поведение: ingest-роутер зарегистрирован ДО статики `/`
(иначе `POST /internal/snapshot` вернул бы 405), telegram-маршруты выключены,
`GET /api/schools` берёт активные школы из `schools_config` снапшота и
показывает ЖИВЫЕ данные после `store.apply` (не снимок на старте), а
`python -m web.edge_server` собирает uvicorn на `EDGE_HOST:EDGE_PORT`.
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.config import get_timezone
from services.snapshot import (
    SNAPSHOT_VERSION,
    build_snapshot,
    serialize_snapshot,
    sign_payload,
)
from services.snapshot_store import SnapshotStore
from web import edge_server
from web.edge_server import create_edge_app

_SECRET = 'edge-test-secret'


def _store(tmp_path) -> SnapshotStore:
    return SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)


def _snapshot(
    schools: dict | None = None,
    schools_config: dict | None = None,
) -> dict[str, Any]:
    return build_snapshot(
        schools if schools is not None else {'s1': {'SCHOOL_NAME': 'Школа 1'}},
        schools_config if schools_config is not None else {'s1': {'name': 'Школа 1'}},
    )


def _client(store, **kwargs) -> TestClient:
    return TestClient(create_edge_app(store, **kwargs))


def test_create_edge_app_returns_testable_app(tmp_path):
    client = _client(_store(tmp_path))
    # Базовый маршрут работает без telegram-конфигурации.
    assert client.get('/api/schools').status_code == 200


def test_ingest_route_registered_before_static_mount(tmp_path, monkeypatch):
    """`POST /internal/snapshot` доходит до ingest, а не до статики `/` (405)."""
    monkeypatch.setattr('web.edge_ingest.Config', _FakeConfig)
    static = tmp_path / 'dist'
    static.mkdir()
    (static / 'index.html').write_text('<html>edge</html>', encoding='utf-8')

    store = _store(tmp_path)
    client = _client(store, static_dir=str(static))

    # Статика обслуживается.
    assert client.get('/').status_code == 200

    payload = _snapshot()
    body = serialize_snapshot(payload)
    r = client.post(
        '/internal/snapshot',
        content=body,
        headers={
            'X-Snapshot-Signature': sign_payload(_SECRET, body),
            'X-Snapshot-Timestamp': str(int(time.time())),
        },
    )

    assert r.status_code == 200, r.text
    assert r.json() == {'ok': True}
    # Снапшот реально применился (ingest → store), а не отдан статикой.
    assert store.schools_config == payload['schools_config']


def test_telegram_routes_disabled(tmp_path):
    """На edge нет `/api/me` и `/api/widget`."""
    client = _client(_store(tmp_path))
    assert client.get('/api/me').status_code == 404
    assert client.get('/api/widget/1').status_code == 404


def test_schools_from_snapshot_config(tmp_path):
    store = _store(tmp_path)
    store.apply(_snapshot(
        schools={'s1': {'SCHOOL_NAME': 'Школа 1'}},
        schools_config={
            's1': {'name': 'Школа 1', 'active': True},
            's2': {'name': 'Скрытая', 'active': False},
        },
    ))

    body = _client(store).get('/api/schools').json()

    assert body['schools'] == [{'id': 's1', 'name': 'Школа 1', 'loaded': True}]


def test_schools_reflect_new_snapshot_after_apply(tmp_path):
    """`/api/schools` читает ТЕКУЩИЙ store, а не снимок на старте."""
    store = _store(tmp_path)
    store.apply(_snapshot(
        schools={'s1': {'SCHOOL_NAME': 'Старая'}},
        schools_config={'s1': {'name': 'Старая школа', 'active': True}},
    ))
    client = _client(store)
    assert client.get('/api/schools').json()['schools'] == [
        {'id': 's1', 'name': 'Старая школа', 'loaded': True}
    ]

    # Новый снапшот: другая школа и другое имя/набор активных.
    store.apply(_snapshot(
        schools={'s9': {'SCHOOL_NAME': 'Новая'}},
        schools_config={'s9': {'name': 'Новая школа', 'active': True}},
    ))

    assert client.get('/api/schools').json()['schools'] == [
        {'id': 's9', 'name': 'Новая школа', 'loaded': True}
    ]


def test_schools_loaded_flag_uses_live_schools_data(tmp_path):
    """Флаг `loaded` берётся из живого `schools_data`, а не из стартового."""
    store = _store(tmp_path)
    client = _client(store)
    assert client.get('/api/schools').json()['schools'] == []

    # Конфиг есть, но данных ещё нет → loaded=False.
    store.apply(_snapshot(schools={}, schools_config={'s1': {'name': 'Школа', 'active': True}}))
    assert client.get('/api/schools').json()['schools'] == [
        {'id': 's1', 'name': 'Школа', 'loaded': False}
    ]

    store.apply(_snapshot(
        schools={'s1': {'SCHOOL_NAME': 'Школа'}},
        schools_config={'s1': {'name': 'Школа', 'active': True}},
    ))
    assert client.get('/api/schools').json()['schools'] == [
        {'id': 's1', 'name': 'Школа', 'loaded': True}
    ]


def test_schools_config_is_taken_from_store_not_module_default(tmp_path):
    """Активные школы edge — ровно из снапшота, а не из модульного SCHOOLS_CONFIG."""
    store = _store(tmp_path)
    store.apply(_snapshot(
        schools={'s1': {'SCHOOL_NAME': 'Школа'}},
        schools_config={'s1': {'name': 'Из снапшота', 'active': True}},
    ))
    ids = {s['id'] for s in _client(store).get('/api/schools').json()['schools']}
    assert ids == {'s1'}


def test_default_trusted_proxies_is_literal_loopback(tmp_path, monkeypatch):
    """`create_edge_app` доверяет ровно 127.0.0.1 (Caddy), не XFF-цепочке."""
    captured: dict = {}

    def fake_create_app(services, **kwargs):
        captured['services'] = services
        captured['kwargs'] = kwargs
        return FastAPI()

    monkeypatch.setattr('web.edge_server.create_app', fake_create_app)
    create_edge_app(_store(tmp_path))

    assert captured['kwargs']['trusted_proxies'] == ('127.0.0.1',)
    assert captured['kwargs']['enable_telegram_routes'] is False


def test_trusted_proxies_param_is_honored_by_rate_limit(tmp_path, monkeypatch):
    """Переданный trusted_proxies реально влияет на bucket-ы лимита (XFF)."""
    from web.api import create_app

    captured: dict = {}

    def fake_create_app(services, **kwargs):
        captured['services'] = services
        captured['kwargs'] = kwargs
        return FastAPI()

    monkeypatch.setattr('web.edge_server.create_app', fake_create_app)
    create_edge_app(_store(tmp_path))
    edge_kwargs = captured['kwargs']
    services = captured['services']

    def build(**overrides):
        kwargs = {**edge_kwargs, **overrides}
        return TestClient(create_app(services, rate_limit=1, widget_rate_limit=1,
                                     window_seconds=60.0, **kwargs))

    # Без доверия: XFF игнорируется, два «разных» клиента делят один bucket.
    untrusted = build(trusted_proxies=())
    assert untrusted.get('/api/schools', headers={'X-Forwarded-For': '203.0.113.5'}).status_code == 200
    assert untrusted.get('/api/schools', headers={'X-Forwarded-For': '198.51.100.7'}).status_code == 429

    # С доверием TestClient (peer = 'testclient'): клиенты получают свои bucket-ы.
    trusted = build(trusted_proxies=('testclient',))
    assert trusted.get('/api/schools', headers={'X-Forwarded-For': '203.0.113.5'}).status_code == 200
    assert trusted.get('/api/schools', headers={'X-Forwarded-For': '198.51.100.7'}).status_code == 200


def test_static_dir_defaults_to_built_frontend(tmp_path, monkeypatch):
    """По умолчанию статика — собранный `frontend/dist`."""
    captured: dict = {}

    def fake_create_app(services, **kwargs):
        captured['kwargs'] = kwargs
        return FastAPI()

    monkeypatch.setattr('web.edge_server.create_app', fake_create_app)
    create_edge_app(_store(tmp_path))

    assert captured['kwargs']['static_dir'] == edge_server._built_frontend_dir()
    assert captured['kwargs']['static_dir'].endswith('dist')


def test_static_dir_override_is_served(tmp_path):
    static = tmp_path / 'custom-dist'
    static.mkdir()
    (static / 'index.html').write_text('<html>custom</html>', encoding='utf-8')
    r = _client(_store(tmp_path), static_dir=str(static)).get('/')
    assert r.status_code == 200
    assert 'custom' in r.text


def test_python_module_runner_wires_uvicorn(tmp_path, monkeypatch):
    """`python -m web.edge_server` поднимает uvicorn на EDGE_HOST:EDGE_PORT."""
    seen: dict = {}

    class FakeUvicornServer:
        def __init__(self, config):
            seen['config'] = config

        async def serve(self):
            seen['served'] = True

    class FakeUvicornConfig:
        def __init__(self, app, **kwargs):
            self.app = app
            self.kwargs = kwargs

    class FakeStore:
        def __init__(self, path, max_age):
            seen['store'] = (path, max_age)

    class FakeConfig:
        EDGE_HOST = '127.0.0.1'
        EDGE_PORT = 8090
        SNAPSHOT_PATH = str(tmp_path / 'snap.json')
        SNAPSHOT_MAX_AGE = 7200

    monkeypatch.setattr(edge_server.uvicorn, 'Server', FakeUvicornServer)
    monkeypatch.setattr(edge_server.uvicorn, 'Config', FakeUvicornConfig)
    monkeypatch.setattr(edge_server, 'SnapshotStore', FakeStore)

    asyncio.run(edge_server.run_edge_server(FakeConfig()))

    assert seen['served'] is True
    assert seen['store'] == (FakeConfig.SNAPSHOT_PATH, FakeConfig.SNAPSHOT_MAX_AGE)
    assert seen['config'].kwargs['host'] == '127.0.0.1'
    assert seen['config'].kwargs['port'] == 8090


def test_module_is_importable():
    assert callable(edge_server.create_edge_app)
    assert callable(edge_server.main)


# --- W11: /healthz с возрастом снапшота -----------------------------------


def _aged_store(tmp_path, *, age_seconds: float, max_age: int = 7200) -> SnapshotStore:
    """Store с `generated_at` ровно `age_seconds` назад (без ожидания)."""
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=max_age)
    now = datetime.now(get_timezone())
    snapshot = _snapshot(
        schools={'s1': {'SCHOOL_NAME': 'Школа 1'}, 's2': {'SCHOOL_NAME': 'Школа 2'}},
    )
    # build_snapshot проставляет `now`; переписываем generated_at на нужный возраст.
    snapshot['generated_at'] = (now - timedelta(seconds=age_seconds)).isoformat()
    store.apply(snapshot)
    return store


def test_healthz_fresh_snapshot(tmp_path):
    """Свежий снапшот → `ok` со всеми полями, schools_count из schools_data."""
    store = _aged_store(tmp_path, age_seconds=1.0, max_age=7200)
    body = _client(store).get('/healthz').json()

    assert body['status'] == 'ok'
    assert body['version'] == SNAPSHOT_VERSION
    assert body['schools_count'] == 2
    assert body['generated_at'] == store.generated_at
    assert body['snapshot_age_seconds'] >= 1.0
    assert set(body) == {
        'status', 'snapshot_age_seconds', 'generated_at', 'version', 'schools_count',
    }


def test_healthz_stale_snapshot(tmp_path):
    """Возраст > SNAPSHOT_MAX_AGE → `stale`, но поля отдаются."""
    store = _aged_store(tmp_path, age_seconds=100.0, max_age=50)
    body = _client(store).get('/healthz').json()

    assert body['status'] == 'stale'
    assert body['snapshot_age_seconds'] >= 100.0
    assert body['schools_count'] == 2


def test_healthz_no_snapshot_is_stale(tmp_path):
    """Пустой store (снапшот не получен) → `stale` с null/0 полями."""
    store = _store(tmp_path)
    body = _client(store).get('/healthz').json()

    assert body == {
        'status': 'stale',
        'snapshot_age_seconds': None,
        'generated_at': None,
        'version': None,
        'schools_count': 0,
    }


def test_healthz_reflects_live_update_after_apply(tmp_path):
    """Порог/поля считаются по ТЕКУЩЕМУ store, а не на старте."""
    store = _store(tmp_path)
    client = _client(store)
    assert client.get('/healthz').json()['status'] == 'stale'

    store.apply(_snapshot(
        schools={'s1': {'SCHOOL_NAME': 'Школа'}},
        schools_config={'s1': {'name': 'Школа', 'active': True}},
    ))

    body = client.get('/healthz').json()
    assert body['status'] == 'ok'
    assert body['version'] == SNAPSHOT_VERSION
    assert body['schools_count'] == 1
    assert body['generated_at'] == store.generated_at


def test_healthz_max_age_threshold_is_store_value(tmp_path):
    """Граница ok/stale берётся из max_age конкретного store (не константы)."""
    fresh = _aged_store(tmp_path / 'fresh', age_seconds=10.0, max_age=100)
    assert _client(fresh).get('/healthz').json()['status'] == 'ok'

    stale = _aged_store(tmp_path / 'stale', age_seconds=10.0, max_age=5)
    assert _client(stale).get('/healthz').json()['status'] == 'stale'


def test_origin_healthz_unchanged(tmp_path):
    """Origin (create_app без health_provider) отдаёт ровно `{status: ok}`."""
    from web.api import create_app

    app = create_app({'bot_data': {'schools_data': {}}})
    assert TestClient(app).get('/healthz').json() == {'status': 'ok'}


class _FakeConfig:
    EDGE_INGEST_SECRET = _SECRET
    SNAPSHOT_MAX_BYTES = 1024 * 1024
