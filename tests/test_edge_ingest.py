# tests/test_edge_ingest.py
"""Тесты ingest-эндпоинта edge `POST /internal/snapshot` (W9).

Покрываем контракт origin→edge целиком на реальном поведении: приём
подписанного тела (обычного и gzip), отказ по подписи/таймстампу/размеру/версии
с нужным статусом и без деталей, атомарную запись на диск, вызов
`store.apply` и то, что маршрут не попадает под rate-limit middleware `/api/`.
"""
import gzip
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.snapshot import (
    SNAPSHOT_VERSION,
    serialize_snapshot,
    sign_payload,
)
from services.snapshot_store import SnapshotStore
from web.api import create_app
from web.edge_ingest import create_ingest_router

_SECRET = 'test-ingest-secret'
_MAX_BYTES = 1024
_NOW = 1_000_000.0


def _payload(version: int = SNAPSHOT_VERSION) -> dict:
    return {
        'version': version,
        'generated_at': '2026-10-02T12:00:00+05:00',
        'schools': {'s1': {'SCHOOL_NAME': 'Школа'}},
        'schools_config': {'s1': {'name': 'Школа'}},
    }


def _headers(body: bytes, *, timestamp: float = _NOW, signature: str | None = None) -> dict:
    return {
        'X-Snapshot-Signature': signature if signature is not None else sign_payload(_SECRET, body),
        'X-Snapshot-Timestamp': str(int(timestamp)),
    }


def _app(store, *, max_bytes: int = _MAX_BYTES) -> FastAPI:
    app = FastAPI()
    router = create_ingest_router(
        store, secret=_SECRET, max_bytes=max_bytes, now_fn=lambda: _NOW
    )
    assert router is not None
    app.include_router(router)
    return app


class _SpyStore:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.applied: list[dict] = []

    def apply(self, payload: dict) -> bool:
        self.applied.append(payload)
        return self.result


def test_valid_non_gzip_snapshot_accepted_and_written(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    payload = _payload()
    body = serialize_snapshot(payload)

    r = TestClient(_app(store)).post(
        '/internal/snapshot', content=body, headers=_headers(body)
    )

    assert r.status_code == 200
    assert r.json() == {'ok': True}
    assert store.schools_data == payload['schools']
    assert store.version == SNAPSHOT_VERSION
    # запись на диск действительно произошла (атомарно, через store.apply)
    with open(tmp_path / 'snapshot.json', encoding='utf-8') as f:
        assert json.load(f) == payload


def test_valid_gzip_snapshot_accepted(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    payload = _payload()
    plain = serialize_snapshot(payload)
    compressed = gzip.compress(plain)

    r = TestClient(_app(store)).post(
        '/internal/snapshot',
        content=compressed,
        headers={**_headers(plain), 'Content-Encoding': 'gzip'},
    )

    assert r.status_code == 200
    assert r.json() == {'ok': True}
    assert store.schools_data == payload['schools']


def test_wrong_signature_rejected_401_without_side_effects(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    body = serialize_snapshot(_payload())

    r = TestClient(_app(store)).post(
        '/internal/snapshot',
        content=body,
        headers=_headers(body, signature='0' * 64),
    )

    assert r.status_code == 401
    assert store.schools_data == {}
    assert not (tmp_path / 'snapshot.json').exists()


def test_missing_signature_rejected_401(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    body = serialize_snapshot(_payload())

    r = TestClient(_app(store)).post(
        '/internal/snapshot',
        content=body,
        headers={'X-Snapshot-Timestamp': str(int(_NOW))},
    )

    assert r.status_code == 401


def test_stale_timestamp_rejected_422(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    body = serialize_snapshot(_payload())

    r = TestClient(_app(store)).post(
        '/internal/snapshot',
        content=body,
        headers=_headers(body, timestamp=_NOW - 301),
    )

    assert r.status_code == 422
    assert store.schools_data == {}


def test_future_timestamp_rejected_422(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    body = serialize_snapshot(_payload())

    r = TestClient(_app(store)).post(
        '/internal/snapshot',
        content=body,
        headers=_headers(body, timestamp=_NOW + 301),
    )

    assert r.status_code == 422
    assert store.schools_data == {}


def test_timestamp_boundary_within_tolerance_accepted(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    body = serialize_snapshot(_payload())
    client = TestClient(_app(store))

    assert client.post(
        '/internal/snapshot', content=body, headers=_headers(body, timestamp=_NOW - 300)
    ).status_code == 200
    assert client.post(
        '/internal/snapshot', content=body, headers=_headers(body, timestamp=_NOW + 300)
    ).status_code == 200


def test_missing_timestamp_rejected_422(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    body = serialize_snapshot(_payload())

    r = TestClient(_app(store)).post(
        '/internal/snapshot',
        content=body,
        headers={'X-Snapshot-Signature': sign_payload(_SECRET, body)},
    )

    assert r.status_code == 422


def test_non_finite_timestamp_rejected_422(tmp_path):
    """NaN/inf не должны проходить сравнение `abs(now - ts) > 300`."""
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    body = serialize_snapshot(_payload())
    client = TestClient(_app(store))

    for bad in ('nan', 'inf', '-inf', 'not-a-number'):
        r = client.post(
            '/internal/snapshot',
            content=body,
            headers=_headers(body, signature=sign_payload(_SECRET, body))
            | {'X-Snapshot-Timestamp': bad},
        )
        assert r.status_code == 422, bad


def test_oversize_plain_body_rejected_413(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    body = b'x' * (_MAX_BYTES + 1)

    r = TestClient(_app(store)).post(
        '/internal/snapshot', content=body, headers=_headers(body)
    )

    assert r.status_code == 413
    assert store.schools_data == {}
    assert not (tmp_path / 'snapshot.json').exists()


def test_gzip_bomb_rejected_413_without_full_decompression(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    # ~1 МиБ нулей сжимается до килобайт — бомба должна упереться в лимит.
    plain = b'\x00' * (1024 * 1024)
    compressed = gzip.compress(plain)

    r = TestClient(_app(store)).post(
        '/internal/snapshot',
        content=compressed,
        headers={**_headers(plain), 'Content-Encoding': 'gzip'},
    )

    assert r.status_code == 413
    assert store.schools_data == {}


def test_bad_gzip_rejected_422(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    body = b'not-a-gzip-stream'

    r = TestClient(_app(store)).post(
        '/internal/snapshot',
        content=body,
        headers={**_headers(body), 'Content-Encoding': 'gzip'},
    )

    assert r.status_code == 422


def test_unsupported_version_rejected_409(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    payload = _payload(version=SNAPSHOT_VERSION + 1)
    body = serialize_snapshot(payload)

    r = TestClient(_app(store)).post(
        '/internal/snapshot', content=body, headers=_headers(body)
    )

    assert r.status_code == 409
    assert store.schools_data == {}
    assert not (tmp_path / 'snapshot.json').exists()


def test_invalid_json_rejected_422(tmp_path):
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    body = b'{not valid json!!'

    r = TestClient(_app(store)).post(
        '/internal/snapshot', content=body, headers=_headers(body)
    )

    assert r.status_code == 422
    assert store.schools_data == {}


def test_success_calls_store_apply_with_payload():
    store = _SpyStore()
    payload = _payload()
    body = serialize_snapshot(payload)

    r = TestClient(_app(store)).post(
        '/internal/snapshot', content=body, headers=_headers(body)
    )

    assert r.status_code == 200
    assert store.applied == [payload]


def test_apply_false_maps_to_409():
    store = _SpyStore(result=False)
    body = serialize_snapshot(_payload())

    r = TestClient(_app(store)).post(
        '/internal/snapshot', content=body, headers=_headers(body)
    )

    assert r.status_code == 409


def test_error_bodies_do_not_leak_details(tmp_path):
    """Любая ошибка отдаёт один и тот же безликий ответ."""
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    client = TestClient(_app(store))
    good = serialize_snapshot(_payload())

    cases = {
        401: client.post(
            '/internal/snapshot', content=good, headers=_headers(good, signature='bad')
        ),
        409: client.post(
            '/internal/snapshot',
            content=serialize_snapshot(_payload(version=99)),
            headers=_headers(serialize_snapshot(_payload(version=99))),
        ),
        413: client.post(
            '/internal/snapshot', content=b'x' * (_MAX_BYTES + 1),
            headers=_headers(b'x' * (_MAX_BYTES + 1)),
        ),
        422: client.post(
            '/internal/snapshot', content=good, headers=_headers(good, timestamp=_NOW - 9999)
        ),
    }

    for status, response in cases.items():
        assert response.status_code == status
        assert response.json() == {'detail': 'Snapshot rejected'}
        text = response.text.lower()
        for leak in ('signature', 'timestamp', 'version', 'gzip', 'size'):
            assert leak not in text


def test_route_not_subject_to_api_rate_limit(tmp_path):
    """`/internal/snapshot` не под middleware `/api/` — не лимитируется."""
    store = _SpyStore()
    # static_dir не существует → create_app не монтирует заглушку `/`, чтобы
    # проверять именно middleware, а не порядок статики (интеграция — W10).
    app = create_app(
        {'bot_data': {'schools_data': {}}},
        rate_limit=1,
        widget_rate_limit=1,
        window_seconds=60.0,
        static_dir=str(tmp_path / 'no-static'),
    )
    _ingest = create_ingest_router(
        store, secret=_SECRET, max_bytes=_MAX_BYTES, now_fn=lambda: _NOW
    )
    assert _ingest is not None
    app.include_router(_ingest)
    client = TestClient(app)
    payload = _payload()
    body = serialize_snapshot(payload)

    for _ in range(5):
        r = client.post('/internal/snapshot', content=body, headers=_headers(body))
        assert r.status_code == 200

    # контроль: публичный маршрут всё ещё под лимитом (сравнение с ingest)
    assert client.get('/api/schools').status_code == 200
    assert client.get('/api/schools').status_code == 429


# --- fail-closed при пустом EDGE_INGEST_SECRET ------------------------------


def test_empty_secret_returns_no_router():
    """Пустой секрет → ingest-роутер не создаётся (нечего сверять)."""
    assert create_ingest_router(_SpyStore(), secret='') is None


def test_empty_secret_does_not_accept_forged_signature(tmp_path):
    """С пустым секретом подпись, посчитанная от пустой строки, не принимается.

    Fail-closed: роутера нет, поэтому даже «правильная» с точки зрения
    пустого секрета подпись не открывает ingest.
    """
    store = SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)
    router = create_ingest_router(store, secret='', max_bytes=_MAX_BYTES)
    assert router is None

    # Контроль: попытка собрать приложение с пустым секретом не регистрирует
    # маршрут → запрос с подписью от пустого секрета получает 404, а данные
    # остаются нетронутыми.
    if router is None:
        app = FastAPI()
        body = serialize_snapshot(_payload())
        forged = sign_payload('', body)
        r = TestClient(app).post(
            '/internal/snapshot',
            content=body,
            headers={
                'X-Snapshot-Signature': forged,
                'X-Snapshot-Timestamp': str(int(_NOW)),
            },
        )
        assert r.status_code == 404
        assert store.schools_data == {}
        assert not (tmp_path / 'snapshot.json').exists()
