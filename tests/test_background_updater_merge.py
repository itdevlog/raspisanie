# tests/test_background_updater_merge.py
"""Регрессии: частичная загрузка сохраняет last-known-good; единый _on_data_replaced."""
from types import SimpleNamespace

from core.background_updater import BackgroundUpdater


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
