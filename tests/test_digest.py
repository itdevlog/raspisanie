# tests/test_digest.py
"""Утренний дайджест: привязка к первому уроку, дедуп, отправка."""
import asyncio
import logging
from datetime import datetime
from types import SimpleNamespace

from core.background_updater import BackgroundUpdater
from services.digest_service import DigestService
from services.user_preferences import UserPreferencesService
from services.user_service import UserService


def _school_data(first_lesson_start='08:00'):
    return {
        'CLASSES': {'c1': '5а'},
        'LESSON_TIMES': {'1': [first_lesson_start, '08:45'], '2': ['09:00', '09:45']},
        'CLASS_SCHEDULE': {'p1': {'c1': {
            '501': {'s': ['1'], 't': [], 'r': []},
            '502': {'s': ['1'], 't': [], 'r': []},
        }}},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'SUBJECTS': {'1': 'Математика'},
        'TEACHERS': {}, 'ROOMS': {}, 'DAY_NAMES': [],
    }


def test_digest_fires_at_offset_before_first_lesson(tz):
    now = datetime(2026, 9, 11, 7, 0, tzinfo=tz)  # за 60 мин до 08:00
    out = DigestService().get_due_digests(
        {'school_133': _school_data()},
        {1: ('school_133', '5а')},
        now=now,
    )
    assert len(out) == 1
    user_id, text, key = out[0]
    assert user_id == 1
    assert 'Математика' in text
    assert key == 'digest:1:school_133:5а:20260911'


def test_digest_handles_second_shift_in_afternoon(tz):
    """Вторая смена: первый урок в 14:00 — дайджест в 13:00, не утром."""
    now = datetime(2026, 9, 11, 13, 0, tzinfo=tz)
    out = DigestService().get_due_digests(
        {'school_133': _school_data('14:00')},
        {1: ('school_133', '5а')},
        now=now,
    )
    assert len(out) == 1


def test_digest_not_sent_outside_window(tz):
    now = datetime(2026, 9, 11, 6, 0, tzinfo=tz)  # за 2 часа — рано
    out = DigestService().get_due_digests(
        {'school_133': _school_data()},
        {1: ('school_133', '5а')},
        now=now,
    )
    assert out == []


def test_digest_catchup_window(tz):
    now = datetime(2026, 9, 11, 7, 10, tzinfo=tz)  # +10 мин после триггера
    out = DigestService().get_due_digests(
        {'school_133': _school_data()},
        {1: ('school_133', '5а')},
        now=now,
    )
    assert len(out) == 1


def test_digest_skips_weekend(tz):
    now = datetime(2026, 9, 12, 7, 0, tzinfo=tz)  # суббота
    out = DigestService().get_due_digests(
        {'school_133': _school_data()},
        {1: ('school_133', '5а')},
        now=now,
    )
    assert out == []


def test_digest_skips_class_without_lessons(tz):
    school = _school_data()
    school['CLASS_SCHEDULE']['p1']['c1'] = {}
    now = datetime(2026, 9, 11, 7, 0, tzinfo=tz)
    out = DigestService().get_due_digests(
        {'school_133': school},
        {1: ('school_133', '5а')},
        now=now,
    )
    assert out == []


def test_digest_includes_exchanges(tz):
    school = _school_data()
    school['CLASS_EXCHANGE'] = {'c1': {'11.09.2026': {'1': {'s': '2', 't': '1', 'r': '101'}}}}
    school['SUBJECTS']['2'] = 'Биология'
    school['TEACHERS']['1'] = 'Иванов Иван Иванович'
    school['ROOMS']['101'] = '101'
    now = datetime(2026, 9, 11, 7, 0, tzinfo=tz)
    out = DigestService().get_due_digests(
        {'school_133': school},
        {1: ('school_133', '5а')},
        now=now,
    )
    assert len(out) == 1
    assert 'Биология' in out[0][1]


def test_digest_on_transfer_day_uses_transferred_weekday(tz):
    """Перенос: пятница работает по субботнему расписанию (daynum=6)."""
    school = _school_data()
    school['SUBJECTS']['2'] = 'Биология'
    school['CLASS_SCHEDULE']['p1']['c1']['601'] = {'s': ['2'], 't': [], 'r': []}
    school['HOLIDAY_TRANSFER'] = {'11.09.2026': {'type': 'transfer', 'daynum': 6}}
    now = datetime(2026, 9, 11, 7, 0, tzinfo=tz)  # пятница, за 60 мин до 08:00
    out = DigestService().get_due_digests(
        {'school_133': school},
        {1: ('school_133', '5а')},
        now=now,
    )
    assert len(out) == 1
    assert 'Биология' in out[0][1]
    assert 'Математика' not in out[0][1]


def test_digest_on_vacation_day_is_empty(tz):
    school = _school_data()
    school['HOLIDAY_TRANSFER'] = {'11.09.2026': {'type': 'vacation'}}
    now = datetime(2026, 9, 11, 7, 0, tzinfo=tz)
    out = DigestService().get_due_digests(
        {'school_133': school},
        {1: ('school_133', '5а')},
        now=now,
    )
    assert out == []


def test_digest_transfer_weeknum_used(tz):
    """weeknum=2 у переноса: ключ расписания с префиксом недели."""
    school = _school_data()
    school['SUBJECTS']['2'] = 'Биология'
    school['CLASS_SCHEDULE']['p1']['c1']['2601'] = {'s': ['2'], 't': [], 'r': []}
    school['HOLIDAY_TRANSFER'] = {
        '11.09.2026': {'type': 'transfer', 'daynum': 6, 'weeknum': 2}
    }
    now = datetime(2026, 9, 11, 7, 0, tzinfo=tz)
    out = DigestService().get_due_digests(
        {'school_133': school},
        {1: ('school_133', '5а')},
        now=now,
    )
    assert len(out) == 1
    assert 'Биология' in out[0][1]


def test_digest_toggle_roundtrip(make_db):
    prefs = UserPreferencesService(make_db())
    assert prefs.get_notification_settings(1)['daily_digest'] is False
    prefs.enable_daily_digest(1)
    assert prefs.get_notification_settings(1)['daily_digest'] is True
    prefs.toggle_daily_digest(1)
    assert prefs.get_notification_settings(1)['daily_digest'] is False


def _make_updater(db, school_data):
    updater = object.__new__(BackgroundUpdater)
    updater.logger = logging.getLogger('test')
    updater.application = SimpleNamespace(
        bot_data={
            'user_service': UserService(db),
            'schools_data': {'school_133': school_data},
        },
        bot=None,
    )
    updater.reminder_service = __import__('services.reminder_service',
                                          fromlist=['ReminderService']).ReminderService()
    updater.digest_service = DigestService()
    updater.sent_digests = {}
    updater.sent_reminders = {}
    return updater


def test_send_digests_respects_toggle_and_dedups(make_db, tz, monkeypatch):
    db = make_db()
    us = UserService(db)
    us.set_user_class(1, '5а', 'school_133')
    UserPreferencesService(db).set_notification_settings(1, {'daily_digest': True})
    us.set_user_class(2, '5а', 'school_133')
    UserPreferencesService(db).set_notification_settings(2, {'daily_digest': False})

    updater = _make_updater(db, _school_data())
    sent = []

    async def _fake_send(bot, chat_id, text, parse_mode='Markdown'):
        sent.append((chat_id, text))
        return True

    updater.notification_service = SimpleNamespace(_send_message=_fake_send)

    now = datetime(2026, 9, 11, 7, 0, tzinfo=tz)
    monkeypatch.setattr(updater, '_now', lambda: now, raising=False)
    monkeypatch.setattr(updater, '_save_sent_digests', lambda: None, raising=False)

    asyncio.run(updater._send_digests())
    assert [uid for uid, _ in sent] == [1]

    # повтор — дедуп
    asyncio.run(updater._send_digests())
    assert len(sent) == 1


def test_send_digests_respects_quiet_hours(make_db, tz, monkeypatch):
    db = make_db()
    us = UserService(db)
    us.set_user_class(1, '5а', 'school_133')
    school = _school_data('07:00')
    UserPreferencesService(db).set_notification_settings(1, {
        'daily_digest': True,
        'quiet_hours': {'enabled': True, 'start': 22, 'end': 8},
    })

    updater = _make_updater(db, school)
    sent = []

    async def _fake_send(bot, chat_id, text, parse_mode='Markdown'):
        sent.append(chat_id)
        return True

    updater.notification_service = SimpleNamespace(_send_message=_fake_send)

    # 06:00 — триггер дайджеста для урока 07:00, но тихий час до 08:00
    now = datetime(2026, 9, 11, 6, 0, tzinfo=tz)
    monkeypatch.setattr(updater, '_now', lambda: now, raising=False)
    monkeypatch.setattr(updater, '_save_sent_digests', lambda: None, raising=False)

    asyncio.run(updater._send_digests())
    assert sent == []
    assert updater.sent_digests != {}


def test_send_digests_saved_once_per_pass(make_db, tz, monkeypatch):
    db = make_db()
    us = UserService(db)
    us.set_user_class(1, '5а', 'school_133')
    UserPreferencesService(db).set_notification_settings(1, {'daily_digest': True})
    us.set_user_class(2, '5а', 'school_133')
    UserPreferencesService(db).set_notification_settings(2, {'daily_digest': True})

    updater = _make_updater(db, _school_data())

    async def _fake_send(bot, chat_id, text, parse_mode='Markdown'):
        return True

    updater.notification_service = SimpleNamespace(_send_message=_fake_send)

    save_calls = []
    monkeypatch.setattr(updater, '_save_sent_digests',
                        lambda: save_calls.append(1), raising=False)
    now = datetime(2026, 9, 11, 7, 0, tzinfo=tz)
    monkeypatch.setattr(updater, '_now', lambda: now, raising=False)

    asyncio.run(updater._send_digests())

    assert len(updater.sent_digests) == 2
    assert len(save_calls) == 1


def test_sent_digests_persist_across_restart(tmp_path, monkeypatch):
    from config.config import Config

    monkeypatch.setattr(Config, 'DB_PATH', str(tmp_path / 'database.json'), raising=False)
    updater = object.__new__(BackgroundUpdater)
    updater.logger = logging.getLogger('test')
    updater.sent_digests = {'k1': __import__('time').time()}
    updater.sent_digests_file = updater._get_sent_digests_file()
    updater._save_sent_digests()

    restarted = object.__new__(BackgroundUpdater)
    restarted.logger = logging.getLogger('test')
    restarted.sent_digests = {}
    restarted.sent_digests_file = restarted._get_sent_digests_file()
    restarted._load_sent_digests()

    assert 'k1' in restarted.sent_digests
