import os
import tempfile
from datetime import datetime
from types import SimpleNamespace

import pytz

from core.background_updater import BackgroundUpdater
from database.file_db import FileDB
from services.reminder_service import ReminderService
from services.user_preferences import UserPreferencesService
from services.user_service import UserService

TZ = pytz.timezone('Asia/Yekaterinburg')


def test_due_reminder_within_window():
    now = datetime(2026, 9, 11, 7, 55, tzinfo=TZ)
    school_data = {
        'CLASSES': {'c1': '5а'},
        'LESSON_TIMES': {'1': ['08:00', '08:45']},
        'CLASS_SCHEDULE': {'p1': {'c1': {'501': {'s': ['1'], 't': [], 'r': []}}}},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'SUBJECTS': {'1': 'Математика'},
    }
    svc = ReminderService()
    out = svc.get_due_reminders(
        {'school_133': school_data},
        {'user_1': ('school_133', '5а')},
        now=now,
        window_minutes=10,
    )
    assert out and out[0][1].lower().startswith('через')


def _school_data():
    return {
        'CLASSES': {'c1': '5а'},
        'LESSON_TIMES': {'1': ['08:00', '08:45']},
        'CLASS_SCHEDULE': {'p1': {'c1': {'501': {'s': ['1'], 't': [], 'r': []}}}},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'SUBJECTS': {'1': 'Математика'},
    }


def test_no_reminder_outside_window():
    now = datetime(2026, 9, 11, 7, 30, tzinfo=TZ)
    svc = ReminderService()
    out = svc.get_due_reminders(
        {'school_133': _school_data()},
        {'user_1': ('school_133', '5а')},
        now=now,
        window_minutes=10,
    )
    assert out == []


def test_reminder_skips_weekend():
    now = datetime(2026, 9, 12, 7, 55, tzinfo=TZ)  # суббота
    svc = ReminderService()
    out = svc.get_due_reminders(
        {'school_133': _school_data()},
        {'user_1': ('school_133', '5а')},
        now=now,
        window_minutes=10,
    )
    assert out == []


def test_to_user_classes_builds_map():
    users = [
        {'user_id': 1, 'school_classes': {'school_133': '5а'}},
        {'user_id': 2, 'school_classes': {'school_181': '7б'}},
        {'user_id': 3},
    ]
    mapping = ReminderService.to_user_classes(users)
    assert mapping == {1: ('school_133', '5а'), 2: ('school_181', '7б')}


def _make_db() -> FileDB:
    d = tempfile.mkdtemp()
    db = FileDB(os.path.join(d, 'database.json'))
    UserService(db)
    return db


def test_reminder_loop_dedups_and_respects_toggle(monkeypatch):
    db = _make_db()
    us = UserService(db)
    us.set_user_class(1, '5а', 'school_133')
    UserPreferencesService(db).set_notification_settings(1, {'lesson_reminders': True})
    us.set_user_class(2, '5а', 'school_133')
    UserPreferencesService(db).set_notification_settings(2, {'lesson_reminders': False})

    updater = object.__new__(BackgroundUpdater)
    import logging
    updater.logger = logging.getLogger('test')
    updater._update_lock = __import__('asyncio').Lock()
    updater.application = SimpleNamespace(
        bot_data={
            'user_service': us,
            'schools_data': {'school_133': _school_data()},
        },
        bot=None,
    )
    updater.reminder_service = ReminderService()
    updater.sent_reminders = {}

    sent = []

    async def _fake_send(bot, chat_id, text, parse_mode='Markdown'):
        sent.append((chat_id, text))
        return True

    updater.notification_service = SimpleNamespace(_send_message=_fake_send)

    now = datetime(2026, 9, 11, 7, 55, tzinfo=TZ)
    monkeypatch.setattr(updater, '_now', lambda: now, raising=False)
    import asyncio
    asyncio.run(updater._send_reminders())

    # user 1 включён, user 2 выключен
    assert [uid for uid, _ in sent] == [1]

    # повторный проход — дедуп, ничего не шлём
    asyncio.run(updater._send_reminders())
    assert len(sent) == 1


def test_reminder_loop_skips_quiet_hours_but_dedups(monkeypatch):
    db = _make_db()
    us = UserService(db)
    us.set_user_class(1, '5а', 'school_133')
    UserPreferencesService(db).set_notification_settings(1, {
        'lesson_reminders': True,
        'quiet_hours': {'enabled': True, 'start': 22, 'end': 8},
    })

    school_data = _school_data()
    school_data['LESSON_TIMES'] = {'1': ['07:00', '07:45']}

    updater = object.__new__(BackgroundUpdater)
    import logging
    updater.logger = logging.getLogger('test')
    updater._update_lock = __import__('asyncio').Lock()
    updater.application = SimpleNamespace(
        bot_data={
            'user_service': us,
            'schools_data': {'school_133': school_data},
        },
        bot=None,
    )
    updater.reminder_service = ReminderService()
    updater.sent_reminders = {}

    sent = []

    async def _fake_send(bot, chat_id, text, parse_mode='Markdown'):
        sent.append((chat_id, text))
        return True

    updater.notification_service = SimpleNamespace(_send_message=_fake_send)

    # 06:55, урок в 07:00 попадает в окно, но идёт тихий час (22–8)
    now = datetime(2026, 9, 11, 6, 55, tzinfo=TZ)
    monkeypatch.setattr(updater, '_now', lambda: now, raising=False)
    import asyncio
    asyncio.run(updater._send_reminders())

    # не отправлено, но ключ дедупа сохранён
    assert sent == []
    assert updater.sent_reminders != {}

    asyncio.run(updater._send_reminders())
    assert sent == []


def test_lesson_reminders_toggle_roundtrip():
    db = _make_db()
    prefs = UserPreferencesService(db)
    assert prefs.get_notification_settings(1)['lesson_reminders'] is False
    prefs.enable_lesson_reminders(1)
    assert prefs.get_notification_settings(1)['lesson_reminders'] is True
    prefs.toggle_lesson_reminders(1)
    assert prefs.get_notification_settings(1)['lesson_reminders'] is False
    prefs.disable_lesson_reminders(1)
    assert prefs.get_notification_settings(1)['lesson_reminders'] is False
