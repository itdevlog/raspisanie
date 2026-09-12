import os
import tempfile
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytz

from database.file_db import FileDB
from services.notification_service import NotificationService
from services.user_preferences import UserPreferencesService
from services.user_service import UserService

TZ = pytz.timezone('Asia/Yekaterinburg')


def test_quiet_hours_detection():
    svc = NotificationService.__new__(NotificationService)
    settings = {'quiet_hours': {'enabled': True, 'start': 22, 'end': 7}}
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 23, 0, tzinfo=TZ)) is True
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 12, 0, tzinfo=TZ)) is False
    assert svc._is_quiet_hours({'quiet_hours': {'enabled': False}}, datetime(2026, 9, 11, 23, 0, tzinfo=TZ)) is False


def test_quiet_hours_malformed_settings_not_quiet():
    svc = NotificationService.__new__(NotificationService)
    now = datetime(2026, 9, 11, 23, 0, tzinfo=TZ)
    assert svc._is_quiet_hours({}, now) is False
    assert svc._is_quiet_hours(None, now) is False  # type: ignore[arg-type]  # None обрабатывается функцией
    assert svc._is_quiet_hours({'quiet_hours': {'enabled': True}}, now) is False
    assert svc._is_quiet_hours({'quiet_hours': {'enabled': True, 'start': 'x', 'end': 7}}, now) is False


def test_quiet_hours_wrap_around_boundaries():
    svc = NotificationService.__new__(NotificationService)
    settings = {'quiet_hours': {'enabled': True, 'start': 22, 'end': 7}}
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 22, 0, tzinfo=TZ)) is True
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 6, 59, tzinfo=TZ)) is True
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 7, 0, tzinfo=TZ)) is False


def test_quiet_hours_same_day_range():
    svc = NotificationService.__new__(NotificationService)
    settings = {'quiet_hours': {'enabled': True, 'start': 1, 'end': 5}}
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 3, 0, tzinfo=TZ)) is True
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 6, 0, tzinfo=TZ)) is False


def test_quiet_hours_start_equals_end_is_not_quiet():
    svc = NotificationService.__new__(NotificationService)
    settings = {'quiet_hours': {'enabled': True, 'start': 22, 'end': 22}}
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 22, 0, tzinfo=TZ)) is False
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 3, 0, tzinfo=TZ)) is False
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 12, 0, tzinfo=TZ)) is False


def _make_db() -> FileDB:
    d = tempfile.mkdtemp()
    db = FileDB(os.path.join(d, 'database.json'))
    UserService(db)
    return db


def test_default_settings_gain_quiet_hours():
    db = _make_db()
    prefs = UserPreferencesService(db)
    settings = prefs.get_notification_settings(999)
    assert settings['quiet_hours'] == {'enabled': False, 'start': 22, 'end': 7}
    # существующие ключи на месте — обратная совместимость
    assert settings['update_notifications'] is False
    assert settings['lesson_reminders'] is False


def test_enable_quiet_hours_roundtrip():
    db = _make_db()
    prefs = UserPreferencesService(db)
    prefs.enable_quiet_hours(1, start=23, end=6)
    quiet = prefs.get_notification_settings(1)['quiet_hours']
    assert quiet == {'enabled': True, 'start': 23, 'end': 6}
    prefs.disable_quiet_hours(1)
    assert prefs.get_notification_settings(1)['quiet_hours']['enabled'] is False


def _fake_bot():
    class _Bot:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, parse_mode=None):
            self.sent.append((chat_id, text))
            return True

    return _Bot()


async def test_send_message_anti_flood_paces_without_dropping(monkeypatch):
    svc = NotificationService.__new__(NotificationService)
    svc.logger = __import__('logging').getLogger('test')
    svc._last_sent_at = {}
    # маленький интервал: проверяем пейсинг, не тормозя тест на 1 c
    svc._min_send_interval = 0.01
    bot = _fake_bot()

    assert await svc._send_message(bot, 42, 'first') is True
    # второй вызов в пределах интервала не дропается, а выжидает и уходит
    assert await svc._send_message(bot, 42, 'second') is True
    assert [m[1] for m in bot.sent] == ['first', 'second']

    # другой чат не задет
    assert await svc._send_message(bot, 43, 'other') is True
    assert [m[0] for m in bot.sent] == [42, 42, 43]


async def test_send_message_no_wait_when_interval_zero():
    svc = NotificationService.__new__(NotificationService)
    svc.logger = __import__('logging').getLogger('test')
    svc._last_sent_at = {}
    svc._min_send_interval = 0
    bot = _fake_bot()

    assert await svc._send_message(bot, 42, 'a') is True
    assert await svc._send_message(bot, 42, 'b') is True
    assert [m[1] for m in bot.sent] == ['a', 'b']


async def test_toggle_quiet_hours_handler_roundtrip():
    from handlers.common.settings import toggle_quiet_hours

    db = _make_db()
    us = UserService(db)

    class _Query:
        def __init__(self):
            self.answers = []

        async def answer(self, text=None, **kwargs):
            self.answers.append(text)

    query = _Query()
    update: Any = SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=query)
    context: Any = SimpleNamespace(bot_data={'user_service': us})

    redraws = []

    async def _fake_settings(update, context):
        redraws.append(True)

    import handlers.common.settings as settings_module
    orig = settings_module.settings_handler
    settings_module.settings_handler = _fake_settings
    try:
        await toggle_quiet_hours(update, context, 'on')
        assert UserPreferencesService(db).get_notification_settings(1)['quiet_hours']['enabled'] is True
        await toggle_quiet_hours(update, context, 'off')
        assert UserPreferencesService(db).get_notification_settings(1)['quiet_hours']['enabled'] is False
    finally:
        settings_module.settings_handler = orig

    assert redraws == [True, True]
    assert any('Тихие часы' in (a or '') for a in query.answers)


def test_exchange_notification_skipped_and_marked_during_quiet(monkeypatch):
    db = _make_db()
    us = UserService(db)
    us.set_user_class(1, '5а', 'school_133')
    us.set_user_notification_settings(1, True, 'school_133')
    prefs = UserPreferencesService(db)
    prefs.set_notification_settings(1, {
        'update_notifications': False,
        'lesson_reminders': False,
        'quiet_hours': {'enabled': True, 'start': 22, 'end': 7},
    })

    svc = NotificationService.__new__(NotificationService)
    svc.logger = __import__('logging').getLogger('test')
    svc.moscow_tz = TZ
    svc.sent_notifications = {}
    svc._user_class_index = {}
    svc._index_loaded_for_school = None
    svc._settings_for_school = {}
    svc._last_sent_at = {}
    svc.save_notifications_cache = lambda: None  # type: ignore[method-assign]

    bot = _fake_bot()
    context: Any = SimpleNamespace(bot=bot, bot_data={'user_service': us})

    quiet_now = datetime(2026, 9, 11, 23, 0)  # naive; hour matters only

    # фиксируем "тихое" время через now, который использует notify_exchange_updates
    monkeypatch.setattr(svc, '_now', lambda: quiet_now, raising=False)

    exchanges = [{'lesson_num': 1, 'new_subject': 'Физика', 'new_teacher': '',
                  'new_room': '', 'is_cancelled': False, 'timestamp': quiet_now}]

    import asyncio
    result = asyncio.run(svc.notify_exchange_updates(context, 'school_133', '5а', exchanges))

    # не отправлено, но помечено как отправленное (dedup)
    assert bot.sent == []
    assert result is False
    assert any(svc._is_notification_sent(k) for k in
               [k for entries in svc.sent_notifications.values() for k in entries])
