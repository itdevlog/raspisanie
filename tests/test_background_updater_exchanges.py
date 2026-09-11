# tests/test_background_updater_exchanges.py
"""Регрессия: детектор замен не пишет кэш на каждый вызов и не блокирует loop."""
from types import SimpleNamespace

import pytz

from core.background_updater import BackgroundUpdater


class _FakeDetector:
    def __init__(self):
        self.calls = 0
        self.saved = 0
        self.moscow_tz = pytz.timezone('Asia/Yekaterinburg')

    def detect_exchanges(self, school_id, school_data, date, persist=True):
        self.calls += 1
        assert persist is False, "цикл должен сохранять кэш один раз в конце"
        return []

    def save_cache(self):
        self.saved += 1


async def test_check_exchange_updates_flushes_once(monkeypatch):
    app = SimpleNamespace(bot_data={}, bot=None)
    updater = BackgroundUpdater(app)
    detector = _FakeDetector()
    app.bot_data['exchange_detector'] = detector
    app.bot_data['notification_service'] = SimpleNamespace()
    monkeypatch.setattr(updater, 'log_update_activity', lambda message: None)

    await updater._check_exchange_updates({}, {'school_133': {'CLASSES': {}}})

    # сегодня + завтра
    assert detector.calls == 2
    # один общий flush за цикл, а не запись на каждый вызов
    assert detector.saved == 1
