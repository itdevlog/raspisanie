# tests/test_run_webapp_push_wiring.py
"""Интеграционная регрессия Fix 1: `run_webapp` проводит `push_store` в origin.

До фикса `web/server.py::run_webapp` вызывал `create_app(services)` без
`push_store`, поэтому origin в продакшене не регистрировал `/api/push/*`
(роутер включается только при `push_store is not None` плюс VAPID-ключи и
`EDGE_AUTH_SECRET`). Здесь собираем приложение ровно так, как это делает
`run_webapp` (через реальный `create_app`, перехватывая uvicorn), и проверяем,
что маршрут subscribe зарегистрирован и авторизованная подписка сохраняется.

Конфиг стабим через monkeypatch `Config` на уровне `web.push_api`
(origin-роутер читает VAPID/`EDGE_AUTH_SECRET` из `Config`).
"""
import asyncio
from typing import Any

from fastapi.testclient import TestClient

from config.config import Config
from database.file_db import FileDB
from services.push_store import PushSubscriptionStore
from web import server

_SECRET = 'edge-shared-secret'
_VAPID_PUBLIC = 'vapid-public'
_VAPID_PRIVATE = 'vapid-private'

_SUB = {
    'endpoint': 'https://fcm.googleapis.com/fcm/send/abc123',
    'keys': {'p256dh': 'public-key', 'auth': 'auth-secret'},
    'school_id': 'school_133',
    'kind': 'class',
    'name': '5А',
}


def _build_app_via_run_webapp(monkeypatch, tmp_path) -> Any:
    """Гоняет реальный `run_webapp`, перехватывая созданный FastAPI-инстанс."""
    monkeypatch.setattr(Config, 'EDGE_AUTH_SECRET', _SECRET)
    monkeypatch.setattr(Config, 'VAPID_PUBLIC_KEY', _VAPID_PUBLIC)
    monkeypatch.setattr(Config, 'VAPID_PRIVATE_KEY', _VAPID_PRIVATE)

    seen: dict[str, Any] = {}

    class FakeUvicornServer:
        def __init__(self, config):
            seen['app'] = config.app

        async def serve(self):
            seen['served'] = True

    class FakeUvicornConfig:
        def __init__(self, app, **kwargs):
            self.app = app
            self.kwargs = kwargs

    monkeypatch.setattr(server.uvicorn, 'Server', FakeUvicornServer)
    monkeypatch.setattr(server.uvicorn, 'Config', FakeUvicornConfig)

    store = PushSubscriptionStore(FileDB(str(tmp_path / 'push.json')))

    class FakeApplication:
        bot_data = {'schools_data': {}, 'push_store': store}

    class FakeConfig:
        WEBAPP_HOST = '127.0.0.1'
        WEBAPP_PORT = 8080
        # create_app создаёт статику из services; каталога нет — mount пропущен.
        WEBAPP_URL = ''

    asyncio.run(server.run_webapp(FakeApplication(), FakeConfig()))
    assert seen['served'] is True
    return seen['app'], store


def test_run_webapp_registers_push_subscribe_route(monkeypatch, tmp_path):
    """`POST /api/push/subscribe` реально обслуживается после проводки (не 404/405).

    Проверяем поведением, а не `app.routes`: в FastAPI 0.141/Starlette 1.6
    маршруты, добавленные через `include_router`, материализуются лениво
    (`_IncludedRouter`) и в `app.routes` не видны. Запрос с валидным
    `X-Edge-Auth` и телом должен вернуть `{'ok': True}` — так роут доказанно
    зарегистрирован; без регистрации был бы 404/405.
    """
    app, _ = _build_app_via_run_webapp(monkeypatch, tmp_path)
    client = TestClient(app)

    r = client.post(
        '/api/push/subscribe', json=_SUB, headers={'X-Edge-Auth': _SECRET}
    )

    assert r.status_code == 200, r.text
    assert r.json() == {'ok': True}


def test_run_webapp_authorized_subscribe_persists(monkeypatch, tmp_path):
    """Авторизованный edge-запрос через origin-роутер реально сохраняет подписку."""
    app, store = _build_app_via_run_webapp(monkeypatch, tmp_path)
    client = TestClient(app)

    r = client.post(
        '/api/push/subscribe', json=_SUB, headers={'X-Edge-Auth': _SECRET}
    )

    assert r.status_code == 200, r.text
    assert r.json() == {'ok': True}
    docs = store.collection.find()
    assert len(docs) == 1
    assert docs[0]['endpoint'] == _SUB['endpoint']


def test_run_webapp_subscribe_rejects_missing_edge_auth(monkeypatch, tmp_path):
    """Без `X-Edge-Auth` подписка отклоняется 403 и не сохраняется."""
    app, store = _build_app_via_run_webapp(monkeypatch, tmp_path)
    client = TestClient(app)

    r = client.post('/api/push/subscribe', json=_SUB)

    assert r.status_code == 403
    assert store.collection.find() == []
