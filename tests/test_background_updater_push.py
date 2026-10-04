# tests/test_background_updater_push.py
"""W16: отправка Web Push при обнаружении замен.

Проверяем требования брифа:

- push шлётся только подпискам класса-источника замен
  (`find_matching(school_id, 'class', class_name)`), после Telegram-рассылки;
- entity-push (teacher/room) в MVP не рассылается;
- URL ведёт на share-страницу класса (`/s/{school}/class/{name}?date=...`);
- ошибка push не всплывает, не ломает Telegram-доставку и не меняет
  поведение baseline (коммит как обычно);
- выключенный push-сервис — no-op;
- блокирующий поиск подписок уходит в `asyncio.to_thread`.
"""
import threading
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from core.background_updater import BackgroundUpdater


class _FakeDetector:
    def __init__(self, new_exchanges=None):
        self.calls = 0
        self.saved = 0
        self.commits = 0
        self.moscow_tz = ZoneInfo('Asia/Yekaterinburg')
        self._new_exchanges = new_exchanges

    def detect_exchanges_deferred(self, school_id, school_data, date):
        self.calls += 1
        current = {'5а': {'1': {'lesson_num': '1'}}}
        # Замена относится к одной конкретной дате: отдаём её только на первом
        # вызове (сегодня), на «завтра» — пусто, иначе тест видит двойную
        # обработку одного события.
        new = self._new_exchanges if self.calls == 1 else []
        return (new or []), current

    def commit_exchanges(self, school_id, date, current_exchanges):
        self.commits += 1

    def save_cache(self):
        self.saved += 1


class _RecordingNotifier:
    """Telegram-заглушка: фиксирует вызовы рассылки по классам."""

    def __init__(self, result: bool = True):
        self.result = result
        self.calls: list[tuple[str, str]] = []

    async def notify_exchange_updates(self, context, school_id, class_name, exchanges):
        self.calls.append((school_id, class_name))
        return self.result


class _FakeStore:
    """Заглушка `PushSubscriptionStore`: пишет фильтр и поток вызова."""

    def __init__(self, subscriptions=None, error: Exception | None = None):
        self._subscriptions = list(subscriptions or [])
        self.error = error
        self.filters: list[tuple[str, str, str]] = []
        self.thread_idents: list[int] = []

    def find_matching(self, school_id: str, kind: str, name: str) -> list[dict]:
        self.filters.append((school_id, kind, name))
        self.thread_idents.append(threading.get_ident())
        if self.error is not None:
            raise self.error
        return list(self._subscriptions)


class _FakePushService:
    """Заглушка `PushService`: best-effort, как прод (никогда не бросает)."""

    def __init__(self, enabled: bool = True, error: Exception | None = None):
        self._enabled = enabled
        self.error = error
        self.calls: list[dict] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send_exchange_notifications(self, subscriptions, title, body, url):
        self.calls.append({
            'subscriptions': list(subscriptions),
            'title': title,
            'body': body,
            'url': url,
        })
        if self.error is not None:
            raise self.error
        return len(subscriptions)


def _exchange(class_name: str = '5а', **overrides) -> dict:
    data = {
        'class_name': class_name,
        'lesson_num': 1,
        'new_subject': 'Физика',
        'new_teacher': '',
        'new_room': '',
        'is_cancelled': False,
    }
    data.update(overrides)
    return data


def _make_updater(bot_data=None, new_exchanges=None):
    app = SimpleNamespace(bot_data=dict(bot_data or {}), bot=None)
    updater = BackgroundUpdater(app)
    detector = _FakeDetector(new_exchanges=new_exchanges)
    app.bot_data['exchange_detector'] = detector
    return updater, app, detector


def _sub(endpoint='https://push.example/abc') -> dict:
    return {'endpoint': endpoint, 'keys': {'p256dh': 'k', 'auth': 'a'}}


async def _run(updater, monkeypatch, new_exchanges=None):
    monkeypatch.setattr(updater, 'log_update_activity', lambda message: None)
    monkeypatch.setattr(updater, '_notify_entity_subscribers', _noop)
    await updater._check_exchange_updates({}, {'school_133': {'CLASSES': {}}})


async def _noop(*args, **kwargs):
    return None


# --- happy path -------------------------------------------------------------

async def test_class_exchange_sends_push_to_matching_subscriptions(monkeypatch):
    store = _FakeStore(subscriptions=[_sub('https://push.example/1'), _sub('https://push.example/2')])
    service = _FakePushService()
    notifier = _RecordingNotifier()
    updater, app, detector = _make_updater(
        {
            'notification_service': notifier,
            'push_store': store,
            'push_service': service,
            'webapp_url': 'https://rasp.example.ru',
        },
        new_exchanges=[_exchange()],
    )

    await _run(updater, monkeypatch)

    # Ищем именно подписки класса-источника замен.
    assert store.filters == [('school_133', 'class', '5а')]
    # push отправлен обоим подписчикам, после Telegram-рассылки.
    assert len(service.calls) == 1
    call = service.calls[0]
    assert len(call['subscriptions']) == 2
    # Telegram тоже отработал — push его не вытесняет.
    assert notifier.calls == [('school_133', '5а')]
    # URL ведёт на share-страницу класса.
    assert call['url'].startswith('https://rasp.example.ru/s/school_133/class/')
    assert '5' in call['url'] and 'date=' in call['url']


async def test_push_called_after_telegram_notification(monkeypatch):
    events: list[str] = []

    class _Ns(_RecordingNotifier):
        async def notify_exchange_updates(self, context, school_id, class_name, exchanges):
            events.append('telegram')
            return await super().notify_exchange_updates(context, school_id, class_name, exchanges)

    class _Svc(_FakePushService):
        async def send_exchange_notifications(self, subscriptions, title, body, url):
            events.append('push')
            return await super().send_exchange_notifications(subscriptions, title, body, url)

    store = _FakeStore(subscriptions=[_sub()])
    service = _Svc()
    updater, app, detector = _make_updater(
        {'notification_service': _Ns(), 'push_store': store, 'push_service': service,
         'webapp_url': 'https://rasp.example.ru'},
        new_exchanges=[_exchange()],
    )

    await _run(updater, monkeypatch)

    assert events == ['telegram', 'push']


async def test_no_entity_push_only_class(monkeypatch):
    """MVP: entity-подписки (teacher/room) push не получают."""
    store = _FakeStore(subscriptions=[_sub()])
    service = _FakePushService()
    updater, app, detector = _make_updater(
        {'notification_service': _RecordingNotifier(), 'push_store': store,
         'push_service': service, 'webapp_url': 'https://rasp.example.ru'},
        new_exchanges=[_exchange(new_teacher='Иванов', new_room='12')],
    )

    await _run(updater, monkeypatch)

    # Ровно один запрос к store — только по классу.
    assert store.filters == [('school_133', 'class', '5а')]
    assert len(service.calls) == 1


async def test_store_lookup_offloaded_to_thread(monkeypatch):
    store = _FakeStore(subscriptions=[_sub()])
    service = _FakePushService()
    updater, app, detector = _make_updater(
        {'notification_service': _RecordingNotifier(), 'push_store': store,
         'push_service': service, 'webapp_url': 'https://rasp.example.ru'},
        new_exchanges=[_exchange()],
    )

    await _run(updater, monkeypatch)

    assert store.thread_idents
    assert store.thread_idents[0] != threading.get_ident()


# --- error containment ------------------------------------------------------

async def test_push_service_error_does_not_raise_or_affect_telegram(monkeypatch):
    service = _FakePushService(error=RuntimeError('push backend down'))
    notifier = _RecordingNotifier()
    updater, app, detector = _make_updater(
        {'notification_service': notifier, 'push_store': _FakeStore(subscriptions=[_sub()]),
         'push_service': service, 'webapp_url': 'https://rasp.example.ru'},
        new_exchanges=[_exchange()],
    )

    # Не всплывает наружу.
    await _run(updater, monkeypatch)

    assert notifier.calls == [('school_133', '5а')]
    assert len(service.calls) == 1


async def test_store_error_does_not_raise_or_affect_telegram(monkeypatch):
    store = _FakeStore(error=RuntimeError('db down'))
    service = _FakePushService()
    notifier = _RecordingNotifier()
    updater, app, detector = _make_updater(
        {'notification_service': notifier, 'push_store': store,
         'push_service': service, 'webapp_url': 'https://rasp.example.ru'},
        new_exchanges=[_exchange()],
    )

    await _run(updater, monkeypatch)

    assert notifier.calls == [('school_133', '5а')]
    assert service.calls == []


async def test_push_error_does_not_change_baseline_commit(monkeypatch):
    """Telegram доставлен -> baseline коммитится так же, как без push."""
    service = _FakePushService(error=RuntimeError('push down'))
    updater, app, detector = _make_updater(
        {'notification_service': _RecordingNotifier(result=True),
         'push_store': _FakeStore(subscriptions=[_sub()]),
         'push_service': service, 'webapp_url': 'https://rasp.example.ru'},
        new_exchanges=[_exchange()],
    )

    await _run(updater, monkeypatch)

    # сегодня + завтра, доставка подтверждена -> две коммита baseline.
    assert detector.commits == 2


async def test_push_does_not_commit_baseline_when_telegram_pending(monkeypatch):
    """Push не «спасает» baseline, если Telegram-доставка не подтверждена."""
    service = _FakePushService()
    updater, app, detector = _make_updater(
        {'notification_service': _RecordingNotifier(result=False),
         'push_store': _FakeStore(subscriptions=[_sub()]),
         'push_service': service, 'webapp_url': 'https://rasp.example.ru'},
        new_exchanges=[_exchange()],
    )

    await _run(updater, monkeypatch)

    # Дата с заменами не закоммичена (TG pending); коммит только у «завтра»
    # без замен. Push-ошибки/успех на это не влияют.
    assert detector.commits == 1
    # push всё равно попытались отправить (best-effort, независимо от TG).
    assert len(service.calls) == 1


# --- disabled / absent ------------------------------------------------------

async def test_disabled_push_service_is_noop(monkeypatch):
    service = _FakePushService(enabled=False)
    store = _FakeStore(subscriptions=[_sub()])
    updater, app, detector = _make_updater(
        {'notification_service': _RecordingNotifier(), 'push_store': store,
         'push_service': service, 'webapp_url': 'https://rasp.example.ru'},
        new_exchanges=[_exchange()],
    )

    await _run(updater, monkeypatch)

    assert service.calls == []
    # Выключенный сервис не должен даже ходить в store.
    assert store.filters == []


async def test_absent_push_service_is_noop(monkeypatch):
    updater, app, detector = _make_updater(
        {'notification_service': _RecordingNotifier(),
         'webapp_url': 'https://rasp.example.ru'},
        new_exchanges=[_exchange()],
    )

    # Без store/service в bot_data цикл работает как раньше.
    await _run(updater, monkeypatch)

    assert detector.commits == 2


async def test_no_subscriptions_no_push_send(monkeypatch):
    store = _FakeStore(subscriptions=[])
    service = _FakePushService()
    updater, app, detector = _make_updater(
        {'notification_service': _RecordingNotifier(), 'push_store': store,
         'push_service': service, 'webapp_url': 'https://rasp.example.ru'},
        new_exchanges=[_exchange()],
    )

    await _run(updater, monkeypatch)

    assert store.filters == [('school_133', 'class', '5а')]
    assert service.calls == []
