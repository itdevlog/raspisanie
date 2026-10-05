# tests/test_push_api.py
"""Тесты публичного push-API origin (W15).

Origin принимает `POST /api/push/subscribe` и `POST /api/push/unsubscribe`
только от edge-прокси, аутентифицированного общим секретом `X-Edge-Auth`
(сверка `hmac.compare_digest`, несовпадение → 403). Подписка проходит
валидацию и ложится в реальный `FileDB` через `PushSubscriptionStore`.
Собственного rate-limit у origin нет: per-client лимит subscribe живёт на
edge (`/api/` middleware, W8/W17), потому что origin вызывается одним peer IP.

Маршруты регистрируются, только если заданы VAPID-ключи И `EDGE_AUTH_SECRET`;
иначе их в приложении нет вовсе.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.config import Config
from database.file_db import FileDB
from services.push_store import PushSubscriptionStore
from web.api import create_app
from web.push_api import create_push_router

_SECRET = 'edge-shared-secret'
_VAPID_PUBLIC = 'vapid-public'
_VAPID_PRIVATE = 'vapid-private'

_ENDPOINT = 'https://fcm.googleapis.com/fcm/send/abc123'
_ENDPOINT_2 = 'https://fcm.googleapis.com/fcm/send/def456'
_KEYS = {'p256dh': 'public-key', 'auth': 'auth-secret'}


def _store(tmp_path) -> PushSubscriptionStore:
    return PushSubscriptionStore(FileDB(str(tmp_path / 'push.json')))


def _sub(endpoint: str = _ENDPOINT, **overrides) -> dict:
    data = {
        'endpoint': endpoint,
        'keys': dict(_KEYS),
        'school_id': 'school_133',
        'kind': 'class',
        'name': '5А',
    }
    data.update(overrides)
    return data


def _app(
    store: PushSubscriptionStore,
    *,
    secret: str = _SECRET,
    vapid_public: str = _VAPID_PUBLIC,
    vapid_private: str = _VAPID_PRIVATE,
) -> FastAPI:
    app = FastAPI()
    router = create_push_router(
        store,
        edge_auth_secret=secret,
        vapid_public_key=vapid_public,
        vapid_private_key=vapid_private,
    )
    assert router is not None
    app.include_router(router)
    return app


def _auth() -> dict:
    return {'X-Edge-Auth': _SECRET}


# --- subscribe: happy path -------------------------------------------------

def test_subscribe_upserts_subscription(tmp_path):
    store = _store(tmp_path)
    r = TestClient(_app(store)).post(
        '/api/push/subscribe', json=_sub(), headers=_auth()
    )

    assert r.status_code == 200
    assert r.json() == {'ok': True}
    docs = store.collection.find()
    assert len(docs) == 1
    assert docs[0]['endpoint'] == _ENDPOINT
    assert docs[0]['keys'] == _KEYS
    assert docs[0]['school_id'] == 'school_133'
    assert docs[0]['kind'] == 'class'
    assert docs[0]['name'] == '5А'


def test_subscribe_same_endpoint_updates_without_duplicate(tmp_path):
    store = _store(tmp_path)
    client = TestClient(_app(store))

    assert client.post('/api/push/subscribe', json=_sub(name='5А'), headers=_auth()).status_code == 200
    assert client.post('/api/push/subscribe', json=_sub(name='6Б'), headers=_auth()).status_code == 200

    docs = store.collection.find()
    assert len(docs) == 1
    assert docs[0]['name'] == '6Б'


# --- auth ------------------------------------------------------------------

def test_missing_edge_auth_rejected_403_without_side_effects(tmp_path):
    store = _store(tmp_path)
    r = TestClient(_app(store)).post('/api/push/subscribe', json=_sub())

    assert r.status_code == 403
    assert store.collection.find() == []


def test_wrong_edge_auth_rejected_403(tmp_path):
    store = _store(tmp_path)
    r = TestClient(_app(store)).post(
        '/api/push/subscribe', json=_sub(), headers={'X-Edge-Auth': 'not-the-secret'}
    )

    assert r.status_code == 403
    assert store.collection.find() == []


def test_non_ascii_auth_header_rejected_403_not_500(tmp_path):
    """Сравнение константное и не падает на многобайтовом заголовке."""
    store = _store(tmp_path)
    r = TestClient(_app(store)).post(
        '/api/push/subscribe', json=_sub(), headers={'X-Edge-Auth': 'sécret-ünïcode'.encode()}
    )

    assert r.status_code == 403
    assert store.collection.find() == []


def test_unsubscribe_also_requires_edge_auth(tmp_path):
    store = _store(tmp_path)
    store.upsert(**_sub())
    r = TestClient(_app(store)).post(
        '/api/push/unsubscribe', json={'endpoint': _ENDPOINT}
    )

    assert r.status_code == 403
    assert len(store.collection.find()) == 1


def test_error_body_does_not_leak_secret(tmp_path):
    store = _store(tmp_path)
    r = TestClient(_app(store)).post(
        '/api/push/subscribe', json=_sub(), headers={'X-Edge-Auth': 'wrong'}
    )

    assert r.status_code == 403
    assert _SECRET not in r.text


# --- unsubscribe -----------------------------------------------------------

def test_unsubscribe_removes_by_endpoint(tmp_path):
    store = _store(tmp_path)
    store.upsert(**_sub(_ENDPOINT))
    store.upsert(**_sub(_ENDPOINT_2))
    client = TestClient(_app(store))

    r = client.post(
        '/api/push/unsubscribe', json={'endpoint': _ENDPOINT}, headers=_auth()
    )

    assert r.status_code == 200
    assert r.json() == {'ok': True}
    assert [d['endpoint'] for d in store.collection.find()] == [_ENDPOINT_2]


def test_unsubscribe_unknown_endpoint_is_ok(tmp_path):
    """Идемпотентно: удаление несуществующего endpoint не ошибка."""
    store = _store(tmp_path)
    r = TestClient(_app(store)).post(
        '/api/push/unsubscribe', json={'endpoint': _ENDPOINT}, headers=_auth()
    )

    assert r.status_code == 200
    assert r.json() == {'ok': True}


def test_unsubscribe_invalid_body_rejected_422(tmp_path):
    store = _store(tmp_path)
    client = TestClient(_app(store))

    for body in ({}, {'endpoint': ''}, {'endpoint': 42}):
        r = client.post('/api/push/unsubscribe', json=body, headers=_auth())
        assert r.status_code == 422, body


# --- validation delegates to store ----------------------------------------

def test_subscribe_rejects_invalid_subscription_422(tmp_path):
    store = _store(tmp_path)
    client = TestClient(_app(store))

    # store.upsert вернёт False для каждого из этих тел → 422, без записи.
    cases = [
        _sub(endpoint='http://insecure.example/x'),       # не https
        _sub(keys={'p256dh': 'x'}),                        # нет auth
        _sub(kind='bogus'),                                # неизвестный kind
        _sub(kind=['class']),                              # нестроковый kind (unhashable)
        _sub(kind=None),                                   # нет kind
        _sub(school_id=''),                                # нет school_id
        _sub(name=''),                                     # нет name
    ]
    for body in cases:
        r = client.post('/api/push/subscribe', json=body, headers=_auth())
        assert r.status_code == 422, body
    assert store.collection.find() == []


def test_subscribe_missing_fields_rejected_422(tmp_path):
    store = _store(tmp_path)
    client = TestClient(_app(store))

    for body in ({}, {'endpoint': _ENDPOINT}, {'keys': dict(_KEYS)},
                 {'endpoint': _ENDPOINT, 'keys': dict(_KEYS)}):
        r = client.post('/api/push/subscribe', json=body, headers=_auth())
        assert r.status_code == 422, body
    assert store.collection.find() == []


def test_subscribe_non_object_json_rejected_422(tmp_path):
    store = _store(tmp_path)
    r = TestClient(_app(store)).post(
        '/api/push/subscribe', json=['not', 'an', 'object'], headers=_auth()
    )

    assert r.status_code == 422
    assert store.collection.find() == []


# --- gating: enabled only with VAPID keys + EDGE_AUTH_SECRET ---------------

def test_factory_disabled_without_secret(tmp_path):
    assert create_push_router(
        _store(tmp_path), edge_auth_secret='',
        vapid_public_key=_VAPID_PUBLIC, vapid_private_key=_VAPID_PRIVATE,
    ) is None


def test_factory_disabled_without_vapid_public_key(tmp_path):
    assert create_push_router(
        _store(tmp_path), edge_auth_secret=_SECRET,
        vapid_public_key='', vapid_private_key=_VAPID_PRIVATE,
    ) is None


def test_factory_disabled_without_vapid_private_key(tmp_path):
    assert create_push_router(
        _store(tmp_path), edge_auth_secret=_SECRET,
        vapid_public_key=_VAPID_PUBLIC, vapid_private_key='',
    ) is None


def test_factory_enabled_when_configured(tmp_path):
    router = create_push_router(
        _store(tmp_path), edge_auth_secret=_SECRET,
        vapid_public_key=_VAPID_PUBLIC, vapid_private_key=_VAPID_PRIVATE,
    )
    assert router is not None
    assert {getattr(r, 'path', None) for r in router.routes} == {
        '/api/push/subscribe', '/api/push/unsubscribe',
    }


def test_create_app_does_not_register_push_without_config(tmp_path, monkeypatch):
    """Без VAPID/EDGE_AUTH_SECRET push-маршрутов в приложении нет."""
    monkeypatch.setattr(Config, 'EDGE_AUTH_SECRET', '')
    monkeypatch.setattr(Config, 'VAPID_PUBLIC_KEY', '')
    monkeypatch.setattr(Config, 'VAPID_PRIVATE_KEY', '')
    app = create_app(
        {'bot_data': {'schools_data': {}}},
        push_store=_store(tmp_path),
        static_dir=str(tmp_path / 'no-static'),
    )
    client = TestClient(app)

    assert client.post('/api/push/subscribe', json=_sub(), headers=_auth()).status_code == 404


def test_create_app_registers_push_when_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'EDGE_AUTH_SECRET', _SECRET)
    monkeypatch.setattr(Config, 'VAPID_PUBLIC_KEY', _VAPID_PUBLIC)
    monkeypatch.setattr(Config, 'VAPID_PRIVATE_KEY', _VAPID_PRIVATE)
    store = _store(tmp_path)
    app = create_app(
        {'bot_data': {'schools_data': {}}},
        push_store=store,
        static_dir=str(tmp_path / 'no-static'),
    )
    client = TestClient(app)

    r = client.post('/api/push/subscribe', json=_sub(), headers=_auth())

    assert r.status_code == 200
    assert len(store.collection.find()) == 1
