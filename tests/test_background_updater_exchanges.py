# tests/test_background_updater_exchanges.py
"""Регрессия: детектор замен не пишет кэш на каждый вызов и не блокирует loop.

Baseline коммитится только когда доставка уведомлений подтверждена — иначе
следующий цикл ретраит (per-user dedup не даёт дублей).
"""
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
        return (self._new_exchanges or []), current

    def commit_exchanges(self, school_id, date, current_exchanges):
        self.commits += 1

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
    # нет замен -> коммит baseline для обеих дат
    assert detector.commits == 2


async def test_commit_skipped_when_notification_pending(monkeypatch):
    app = SimpleNamespace(bot_data={}, bot=None)
    updater = BackgroundUpdater(app)
    detector = _FakeDetector(new_exchanges=[
        {'class_name': '5а', 'lesson_num': 1, 'new_subject': 'Физика',
         'new_teacher': '', 'new_room': '', 'is_cancelled': False},
    ])

    class _Ns:
        async def notify_exchange_updates(self, context, school_id, class_name, exchanges):
            return False  # доставка не подтверждена -> ретрай

    app.bot_data['exchange_detector'] = detector
    app.bot_data['notification_service'] = _Ns()
    monkeypatch.setattr(updater, 'log_update_activity', lambda message: None)
    monkeypatch.setattr(updater, '_notify_entity_subscribers', _noop)

    await updater._check_exchange_updates({}, {'school_133': {'CLASSES': {}}})

    # pending -> baseline не коммитится, следующий цикл повторит
    assert detector.calls == 2
    assert detector.commits == 0
    assert detector.saved == 1


async def test_commit_done_when_all_classes_handled(monkeypatch):
    app = SimpleNamespace(bot_data={}, bot=None)
    updater = BackgroundUpdater(app)
    detector = _FakeDetector(new_exchanges=[
        {'class_name': '5а', 'lesson_num': 1, 'new_subject': 'Физика',
         'new_teacher': '', 'new_room': '', 'is_cancelled': False},
    ])

    class _Ns:
        async def notify_exchange_updates(self, context, school_id, class_name, exchanges):
            return True

    app.bot_data['exchange_detector'] = detector
    app.bot_data['notification_service'] = _Ns()
    monkeypatch.setattr(updater, 'log_update_activity', lambda message: None)
    monkeypatch.setattr(updater, '_notify_entity_subscribers', _noop)

    await updater._check_exchange_updates({}, {'school_133': {'CLASSES': {}}})

    assert detector.commits == 2
    assert detector.saved == 1


async def _noop(*args, **kwargs):
    return None
