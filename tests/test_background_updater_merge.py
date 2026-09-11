# tests/test_background_updater_merge.py
"""Регрессии: частичная загрузка сохраняет last-known-good; единый _on_data_replaced."""
import asyncio
import logging
from types import SimpleNamespace

from core.background_updater import BackgroundUpdater


class _FakeLoader:
    def __init__(self, data):
        self._data = data

    def load_all_schools_data(self):
        return self._data


class _FakeNotif:
    def __init__(self):
        self.calls = 0

    def reset_user_class_index(self):
        self.calls += 1


class _FakeCache:
    def __init__(self):
        self.cleared = 0

    def clear(self):
        self.cleared += 1


def _bare_updater(bot_data):
    up = BackgroundUpdater.__new__(BackgroundUpdater)
    up.logger = logging.getLogger('test')
    up.application = SimpleNamespace(bot_data=bot_data, bot=None)
    up.notification_service = _FakeNotif()
    up.data_loader = None
    up._update_lock = asyncio.Lock()
    return up


def _make():
    app = SimpleNamespace(bot_data={}, bot=None)
    up = BackgroundUpdater(app)
    return up, app


def test_on_data_replaced_clears_cache_and_index():
    up, app = _make()
    calls = {'cleared': 0, 'reset': 0}

    class _Cache:
        def clear(self):
            calls['cleared'] += 1

    class _Notif:
        def reset_user_class_index(self):
            calls['reset'] += 1

    app.bot_data['cache_service'] = _Cache()
    app.bot_data['notification_service'] = _Notif()
    up._on_data_replaced()
    assert calls == {'cleared': 1, 'reset': 1}


def test_merge_keeps_failed_school():
    old = {'s1': {'v': 1}, 's2': {'v': 2}}
    new = {'s1': {'v': 99}}
    merged = BackgroundUpdater._merge_schools_data(old, new)
    assert merged['s1'] == {'v': 99}
    assert merged['s2'] == {'v': 2}  # last-known-good сохранён


async def test_perform_update_keeps_failed_school():
    # old has s1 and s2; fresh load only has s1 -> s2 (last-known-good) must survive
    notif = _FakeNotif()
    cache = _FakeCache()
    bot_data = {
        'schools_data': {'s1': {'v': 1}, 's2': {'v': 2}},
        'cache_service': cache,
        'notification_service': notif,
    }
    up = _bare_updater(bot_data)
    up.data_loader = _FakeLoader({'s1': {'v': 9}})

    async def _noop(*a, **k):
        return None
    up._check_exchange_updates = _noop
    up._get_admin_notification_settings = lambda: {'update_notifications': False}

    await up._perform_update()

    assert bot_data['schools_data']['s1'] == {'v': 9}
    assert bot_data['schools_data']['s2'] == {'v': 2}   # retained
    assert cache.cleared == 1                            # _on_data_replaced ran once


async def test_perform_update_skips_when_locked():
    notif = _FakeNotif()
    bot_data = {'schools_data': {'s1': {'v': 1}}, 'notification_service': notif, 'cache_service': _FakeCache()}
    up = _bare_updater(bot_data)
    up.data_loader = _FakeLoader({'s1': {'v': 9}})

    async def _noop(*a, **k):
        return None
    up._check_exchange_updates = _noop
    up._get_admin_notification_settings = lambda: {'update_notifications': False}

    async with up._update_lock:          # эмулируем идущее обновление
        await up._perform_update()       # должно сразу вернуться, не тронув данные

    assert bot_data['schools_data']['s1'] == {'v': 1}   # без изменений
