# tests/test_push_service.py
"""Юнит-тесты сервиса отправки Web Push `PushService` (W13).

Никакой реальной сети: `pywebpush.webpush` подменяется фейком (monkeypatch),
как в `test_snapshot_export.py` подменяется httpx-клиент. Проверяются шесть
требований брифа:

- выключен (no-op) без VAPID-ключей;
- payload ровно `{title, body, url}`;
- `webpush` вызывается через `asyncio.to_thread` (loop не блокируется);
- ответ 404/410 удаляет подписку как мёртвую, остальные не трогает;
- 5xx/сетевой сбой подписку НЕ удаляет (только 404/410);
- один сбой не прерывает рассылку остальным, и метод не бросает.
"""
import asyncio
import json
import logging
import threading

from services.push_service import PushService


class _FakeStore:
    """Заглушка `PushSubscriptionStore`: пишет вызовы `remove_dead`."""

    def __init__(self):
        self.removed: list[list[str]] = []

    def remove_dead(self, endpoints):
        endpoints = list(endpoints)
        self.removed.append(endpoints)
        return len(endpoints)


def _config(**overrides):
    values = {
        'VAPID_PUBLIC_KEY': 'public-key',
        'VAPID_PRIVATE_KEY': 'private-key',
        'VAPID_SUBJECT': 'mailto:ops@example.ru',
    }
    values.update(overrides)
    return type('C', (), values)()


def _sub(endpoint: str, **overrides) -> dict:
    data = {
        'endpoint': endpoint,
        'keys': {'p256dh': 'p256dh-key', 'auth': 'auth-secret'},
    }
    data.update(overrides)
    return data


class _WebPushException(Exception):
    """Имитация `pywebpush.WebPushException` с HTTP-статусом в `.response`."""

    def __init__(self, status_code: int):
        super().__init__(f'status {status_code}')
        self.response = type('R', (), {'status_code': status_code})()


def _patch_webpush(monkeypatch, fake):
    """Подменяет `pywebpush.webpush` в модуле сервиса (ленивый импорт)."""
    module = type('FakePyWebPush', (), {'webpush': staticmethod(fake)})()
    monkeypatch.setattr('services.push_service.pywebpush', module)


def _service(store=None, **overrides) -> PushService:
    return PushService(config=_config(**overrides), store=store)


# --- enabled / disabled -----------------------------------------------------

def test_enabled_when_both_vapid_keys_present():
    assert _service().enabled is True


def test_disabled_when_public_key_empty():
    assert _service(VAPID_PUBLIC_KEY='').enabled is False


def test_disabled_when_private_key_empty():
    assert _service(VAPID_PRIVATE_KEY='').enabled is False


async def test_disabled_is_noop_without_send(monkeypatch, caplog):
    calls: list[dict] = []
    _patch_webpush(monkeypatch, lambda **kwargs: calls.append(kwargs))
    store = _FakeStore()
    service = _service(store=store, VAPID_PUBLIC_KEY='', VAPID_PRIVATE_KEY='')

    with caplog.at_level(logging.INFO, logger='services.push_service'):
        result = await service.send_exchange_notifications(
            [_sub('https://fcm.googleapis.com/fcm/send/a')], 't', 'b', '/x')

    assert result == 0
    assert calls == []
    assert store.removed == []
    assert 'выключена' in caplog.text


# --- payload shape ----------------------------------------------------------

async def test_payload_shape_and_vapid_claims(monkeypatch):
    calls: list[dict] = []
    _patch_webpush(monkeypatch, lambda **kwargs: calls.append(kwargs))
    service = _service(store=_FakeStore())
    sub = _sub('https://fcm.googleapis.com/fcm/send/a')

    await service.send_exchange_notifications([sub], 'Заголовок', 'Текст', '/schedule')

    assert len(calls) == 1
    call = calls[0]
    assert call['subscription_info'] is sub
    assert json.loads(call['data']) == {
        'title': 'Заголовок', 'body': 'Текст', 'url': '/schedule'}
    assert call['vapid_private_key'] == 'private-key'
    assert call['vapid_claims'] == {'sub': 'mailto:ops@example.ru'}


# --- runs in worker thread --------------------------------------------------

async def test_webpush_runs_in_worker_thread(monkeypatch):
    thread_idents: list[int] = []
    _patch_webpush(monkeypatch, lambda **kwargs: thread_idents.append(threading.get_ident()))
    service = _service(store=_FakeStore())

    main_ident = threading.get_ident()
    await service.send_exchange_notifications(
        [_sub('https://fcm.googleapis.com/fcm/send/a')], 't', 'b', '/x')

    assert thread_idents
    assert thread_idents[0] != main_ident  # asyncio.to_thread


# --- dead subscription removal ----------------------------------------------

async def test_404_removes_only_that_endpoint(monkeypatch):
    dead = 'https://fcm.googleapis.com/fcm/send/dead'
    alive = 'https://fcm.googleapis.com/fcm/send/alive'

    def fake_webpush(**kwargs):
        if kwargs['subscription_info']['endpoint'] == dead:
            raise _WebPushException(404)

    _patch_webpush(monkeypatch, fake_webpush)
    store = _FakeStore()
    service = _service(store=store)

    sent = await service.send_exchange_notifications(
        [_sub(dead), _sub(alive)], 't', 'b', '/x')

    assert sent == 1
    assert store.removed == [[dead]]


async def test_410_removes_endpoint(monkeypatch):
    dead = 'https://fcm.googleapis.com/fcm/send/gone'

    def fake_webpush(**kwargs):
        raise _WebPushException(410)

    _patch_webpush(monkeypatch, fake_webpush)
    store = _FakeStore()
    service = _service(store=store)

    await service.send_exchange_notifications([_sub(dead)], 't', 'b', '/x')

    assert store.removed == [[dead]]


async def test_5xx_does_not_remove(monkeypatch):
    endpoint = 'https://fcm.googleapis.com/fcm/send/err'

    def fake_webpush(**kwargs):
        raise _WebPushException(500)

    _patch_webpush(monkeypatch, fake_webpush)
    store = _FakeStore()
    service = _service(store=store)

    sent = await service.send_exchange_notifications([_sub(endpoint)], 't', 'b', '/x')

    assert sent == 0
    assert store.removed == []


async def test_network_error_does_not_remove(monkeypatch):
    endpoint = 'https://fcm.googleapis.com/fcm/send/net'

    def fake_webpush(**kwargs):
        raise ConnectionError('no route to host')

    _patch_webpush(monkeypatch, fake_webpush)
    store = _FakeStore()
    service = _service(store=store)

    sent = await service.send_exchange_notifications([_sub(endpoint)], 't', 'b', '/x')

    assert sent == 0
    assert store.removed == []


async def test_one_failure_does_not_abort_rest(monkeypatch):
    endpoints = [
        'https://fcm.googleapis.com/fcm/send/ok1',
        'https://fcm.googleapis.com/fcm/send/dead',
        'https://fcm.googleapis.com/fcm/send/ok2',
    ]

    def fake_webpush(**kwargs):
        if kwargs['subscription_info']['endpoint'].endswith('/dead'):
            raise _WebPushException(410)

    _patch_webpush(monkeypatch, fake_webpush)
    store = _FakeStore()
    service = _service(store=store)

    sent = await service.send_exchange_notifications(
        [_sub(e) for e in endpoints], 't', 'b', '/x')

    assert sent == 2
    assert store.removed == [[endpoints[1]]]


async def test_never_raises_on_unexpected_send_error(monkeypatch):
    def fake_webpush(**kwargs):
        raise RuntimeError('totally unexpected')

    _patch_webpush(monkeypatch, fake_webpush)
    store = _FakeStore()
    service = _service(store=store)

    sent = await service.send_exchange_notifications(
        [_sub('https://fcm.googleapis.com/fcm/send/a')], 't', 'b', '/x')

    assert sent == 0
    assert store.removed == []


async def test_empty_subscriptions_is_noop(monkeypatch):
    calls: list[dict] = []
    _patch_webpush(monkeypatch, lambda **kwargs: calls.append(kwargs))
    store = _FakeStore()
    service = _service(store=store)

    sent = await service.send_exchange_notifications([], 't', 'b', '/x')

    assert sent == 0
    assert calls == []
    assert store.removed == []


async def test_to_thread_is_used_not_direct_call(monkeypatch):
    """Явная проверка: отправка идёт через `asyncio.to_thread`."""
    seen: list[dict] = []
    real_to_thread = asyncio.to_thread

    async def spy_to_thread(func, *args, **kwargs):
        seen.append({'func': func})
        return await real_to_thread(func, *args, **kwargs)

    monkeypatch.setattr('services.push_service.asyncio.to_thread', spy_to_thread)
    _patch_webpush(monkeypatch, lambda **kwargs: None)
    service = _service(store=_FakeStore())

    await service.send_exchange_notifications(
        [_sub('https://fcm.googleapis.com/fcm/send/a')], 't', 'b', '/x')

    assert len(seen) == 1
