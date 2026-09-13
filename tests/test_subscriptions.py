# tests/test_subscriptions.py
"""Тесты подписок на преподавателей/кабинеты и уведомлений подписчикам."""
import os
import tempfile
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from database.file_db import FileDB
from services.notification_service import NotificationService
from services.subscription_service import SubscriptionService
from services.user_preferences import UserPreferencesService
from services.user_service import UserService


def _svc():
    d = tempfile.mkdtemp()
    return SubscriptionService(FileDB(os.path.join(d, 'database.json')))


def test_whitespace_in_source_name_matches_stripped_subscription():
    s = _svc()
    assert s.subscribe(1, 'school_133', 'teacher', '  Иванов  ') is True
    assert s.get_subscriptions(1, 'school_133') == [('teacher', 'Иванов')]
    assert s.is_subscribed(1, 'school_133', 'teacher', 'Иванов') is True
    assert s.get_subscribers('school_133', 'teacher', 'Иванов') == [1]
    assert s.get_subscribers('school_133', 'teacher', '  Иванов ') == [1]
    assert s.unsubscribe(1, 'school_133', 'teacher', ' Иванов ') is True
    assert s.get_subscriptions(1, 'school_133') == []


def test_blank_name_is_rejected():
    s = _svc()
    assert s.subscribe(1, 'school_133', 'teacher', '   ') is False
    assert s.get_subscriptions(1, 'school_133') == []


def test_subscribe_and_get():
    s = _svc()
    assert s.subscribe(1, 'school_133', 'teacher', 'Иванов') is True
    assert s.get_subscriptions(1, 'school_133') == [('teacher', 'Иванов')]
    assert s.get_subscribers('school_133', 'teacher', 'Иванов') == [1]


def test_unsubscribe():
    s = _svc()
    s.subscribe(1, 'school_133', 'room', '101')
    assert s.unsubscribe(1, 'school_133', 'room', '101') is True
    assert s.get_subscriptions(1, 'school_133') == []


def test_idempotent_subscribe():
    s = _svc()
    s.subscribe(1, 'school_133', 'teacher', 'Иванов')
    s.subscribe(1, 'school_133', 'teacher', 'Иванов')
    assert s.get_subscribers('school_133', 'teacher', 'Иванов') == [1]


def test_unsubscribe_missing_returns_false():
    s = _svc()
    assert s.unsubscribe(1, 'school_133', 'teacher', 'Иванов') is False


def test_malformed_kind_returns_false_without_crash():
    s = _svc()
    assert s.subscribe(1, 'school_133', 'subject', 'Математика') is False
    assert s.unsubscribe(1, 'school_133', 'subject', 'Математика') is False
    assert s.get_subscriptions(1, 'school_133') == []


def test_subscriptions_are_scoped_by_school_and_user():
    s = _svc()
    s.subscribe(1, 'school_133', 'teacher', 'Иванов')
    s.subscribe(2, 'school_133', 'teacher', 'Иванов')
    s.subscribe(1, 'school_181', 'teacher', 'Иванов')
    assert s.get_subscribers('school_133', 'teacher', 'Иванов') == [1, 2]
    assert s.get_subscribers('school_181', 'teacher', 'Иванов') == [1]
    assert s.get_subscriptions(2, 'school_181') == []


def test_unsubscribe_removes_only_target_item():
    s = _svc()
    s.subscribe(1, 'school_133', 'teacher', 'Иванов')
    s.subscribe(1, 'school_133', 'room', '101')
    assert s.unsubscribe(1, 'school_133', 'room', '101') is True
    assert s.get_subscriptions(1, 'school_133') == [('teacher', 'Иванов')]


class _FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode=None):
        self.sent.append((chat_id, text))
        return True


@pytest.mark.asyncio
async def test_notify_subscribers_sends_to_each():
    s = _svc()
    s.subscribe(7, 'school_133', 'teacher', 'Иванов')
    s.subscribe(8, 'school_133', 'teacher', 'Иванов')

    bot = _FakeBot()
    svc = NotificationService()
    context: Any = SimpleNamespace(bot=bot, bot_data={'subscription_service': s})

    delivered, skipped_quiet = await svc.notify_subscribers(
        context, 'school_133', 'teacher', 'Иванов', 'Текст замены')

    assert delivered == 2
    assert skipped_quiet == 0
    assert [cid for cid, _ in bot.sent] == [7, 8]
    assert all(text == 'Текст замены' for _, text in bot.sent)


@pytest.mark.asyncio
async def test_notify_subscribers_no_subscribers_returns_zero():
    s = _svc()
    bot = _FakeBot()
    svc = NotificationService()
    context: Any = SimpleNamespace(bot=bot, bot_data={'subscription_service': s})

    count = await svc.notify_subscribers(context, 'school_133', 'room', '101', 'Текст')

    assert count == (0, 0)
    assert bot.sent == []


@pytest.mark.asyncio
async def test_notify_subscribers_without_service_returns_zero():
    bot = _FakeBot()
    svc = NotificationService()
    context: Any = SimpleNamespace(bot=bot, bot_data={})

    count = await svc.notify_subscribers(context, 'school_133', 'room', '101', 'Текст')

    assert count == (0, 0)


@pytest.mark.asyncio
async def test_force_check_exchanges_notifies_entity_subscribers(monkeypatch):
    from core.background_updater import BackgroundUpdater

    class _Detector:
        moscow_tz = None

        def _get_current_exchanges(self, school_data, today):
            return {'5А': {1: {'data': {}, 'is_cancelled': False}}}

        def _format_exchange_for_notification(self, class_name, exchange, school_data, today):
            return {'class_name': class_name, 'new_teacher': 'Иванов', 'new_room': ''}

    class _Notif:
        async def notify_exchange_updates(self, context, school_id, class_name, exchanges):
            return 1

    app = SimpleNamespace(
        bot_data={
            'exchange_detector': _Detector(),
            'notification_service': _Notif(),
            'schools_data': {'school_133': {}},
        },
        bot=None,
    )
    updater = BackgroundUpdater(app)

    calls = []

    async def _fake_notify(context, notification_service, school_id, class_name, exchanges, date):
        calls.append((school_id, class_name, exchanges))

    monkeypatch.setattr(updater, '_notify_entity_subscribers', _fake_notify)

    await updater.force_check_exchanges(SimpleNamespace())

    assert len(calls) == 1
    assert calls[0][0] == 'school_133'
    assert calls[0][1] == '5А'


@pytest.mark.asyncio
async def test_notify_subscribers_skips_quiet_hours(monkeypatch):
    from zoneinfo import ZoneInfo

    d = tempfile.mkdtemp()
    db = FileDB(os.path.join(d, 'database.json'))
    us = UserService(db)
    UserPreferencesService(db).set_notification_settings(7, {
        'quiet_hours': {'enabled': True, 'start': 22, 'end': 7},
    })
    s = SubscriptionService(db)
    s.subscribe(7, 'school_133', 'teacher', 'Иванов')
    s.subscribe(8, 'school_133', 'teacher', 'Иванов')

    bot = _FakeBot()
    svc = NotificationService.__new__(NotificationService)
    svc.logger = __import__('logging').getLogger('test')
    svc._min_send_interval = 0
    svc._last_sent_at = {}
    svc.moscow_tz = ZoneInfo('Asia/Yekaterinburg')
    monkeypatch.setattr(
        svc, '_now',
        lambda: datetime(2026, 9, 11, 23, 0, tzinfo=ZoneInfo('Asia/Yekaterinburg')),
        raising=False,
    )

    context: Any = SimpleNamespace(
        bot=bot, bot_data={'subscription_service': s, 'user_service': us})
    count = await svc.notify_subscribers(context, 'school_133', 'teacher', 'Иванов', 'Текст')

    assert count == (1, 1)
    assert [cid for cid, _ in bot.sent] == [8]


@pytest.mark.asyncio
async def test_notify_entity_subscribers_dedups_same_entity_date(monkeypatch):
    from core.background_updater import BackgroundUpdater

    calls = []

    class _Notif:
        def _format_exchange_notification(self, class_name, exchanges, date):
            return 'Замена'

        async def notify_subscribers(self, context, school_id, kind, name, text):
            calls.append((school_id, kind, name))
            return (1, 0)

    app = SimpleNamespace(bot_data={}, bot=None)
    updater = BackgroundUpdater(app)
    date = datetime(2026, 9, 11)
    exchanges = [{'class_name': '5А', 'new_teacher': 'Иванов', 'new_room': '101'}]

    await updater._notify_entity_subscribers(
        SimpleNamespace(), _Notif(), 'school_133', '5А', exchanges, date)
    await updater._notify_entity_subscribers(
        SimpleNamespace(), _Notif(), 'school_133', '5А', exchanges, date)

    assert calls == [
        ('school_133', 'teacher', 'Иванов'),
        ('school_133', 'room', '101'),
    ]


@pytest.mark.asyncio
async def test_notify_entity_subscribers_does_not_mark_on_send_failure(monkeypatch):
    """Провал отправки (0 доставлено, 0 тихих) не должен глушить сущность на 24ч."""
    from core.background_updater import BackgroundUpdater

    calls = []

    class _Notif:
        def _format_exchange_notification(self, class_name, exchanges, date):
            return 'Замена'

        async def notify_subscribers(self, context, school_id, kind, name, text):
            calls.append((kind, name))
            return (0, 0)

    app = SimpleNamespace(bot_data={}, bot=None)
    updater = BackgroundUpdater(app)
    date = datetime(2026, 9, 11)
    exchanges = [{'class_name': '5А', 'new_teacher': 'Иванов', 'new_room': '101'}]

    await updater._notify_entity_subscribers(
        SimpleNamespace(), _Notif(), 'school_133', '5А', exchanges, date)
    await updater._notify_entity_subscribers(
        SimpleNamespace(), _Notif(), 'school_133', '5А', exchanges, date)

    assert calls == [('teacher', 'Иванов'), ('room', '101'),
                     ('teacher', 'Иванов'), ('room', '101')]


@pytest.mark.asyncio
async def test_notify_entity_subscribers_marks_on_quiet_skip(monkeypatch):
    """Все подписчики на тихих часах (0 доставлено, >0 тихих) — ключ помечается."""
    from core.background_updater import BackgroundUpdater

    calls = []

    class _Notif:
        def _format_exchange_notification(self, class_name, exchanges, date):
            return 'Замена'

        async def notify_subscribers(self, context, school_id, kind, name, text):
            calls.append((kind, name))
            return (0, 1)

    app = SimpleNamespace(bot_data={}, bot=None)
    updater = BackgroundUpdater(app)
    date = datetime(2026, 9, 11)
    exchanges = [{'class_name': '5А', 'new_teacher': 'Иванов', 'new_room': '101'}]

    await updater._notify_entity_subscribers(
        SimpleNamespace(), _Notif(), 'school_133', '5А', exchanges, date)
    await updater._notify_entity_subscribers(
        SimpleNamespace(), _Notif(), 'school_133', '5А', exchanges, date)

    assert calls == [('teacher', 'Иванов'), ('room', '101')]


@pytest.mark.asyncio
async def test_notify_entity_subscribers_distinct_classes_same_signature(monkeypatch):
    """Два класса с одинаковыми полями замены не должны глушить друг друга."""
    from core.background_updater import BackgroundUpdater

    calls = []

    class _Notif:
        def _format_exchange_notification(self, class_name, exchanges, date):
            return f'Замена {class_name}'

        async def notify_subscribers(self, context, school_id, kind, name, text):
            calls.append((text, kind, name))
            return (1, 0)

    app = SimpleNamespace(bot_data={}, bot=None)
    updater = BackgroundUpdater(app)
    date = datetime(2026, 9, 11)
    exchange = {'new_teacher': 'Иванов', 'new_room': '', 'lesson_num': 1,
                'new_subject': 'Математика', 'is_cancelled': False}

    await updater._notify_entity_subscribers(
        SimpleNamespace(), _Notif(), 'school_133', '5А',
        [{'class_name': '5А', **exchange}], date)
    await updater._notify_entity_subscribers(
        SimpleNamespace(), _Notif(), 'school_133', '5Б',
        [{'class_name': '5Б', **exchange}], date)

    assert calls == [
        ('Замена 5А', 'teacher', 'Иванов'),
        ('Замена 5Б', 'teacher', 'Иванов'),
    ]


@pytest.mark.asyncio
async def test_background_hook_notifies_new_teacher_and_room(monkeypatch):
    from core.background_updater import BackgroundUpdater

    calls = []

    class _Notif:
        def _format_exchange_notification(self, class_name, exchanges, date):
            return 'Замена'

        async def notify_subscribers(self, context, school_id, kind, name, text):
            calls.append((school_id, kind, name, text))
            return (1, 0)

    app = SimpleNamespace(bot_data={}, bot=None)
    updater = BackgroundUpdater(app)
    exchanges = [
        {'class_name': '5А', 'new_teacher': 'Иванов', 'new_room': '101'},
        {'class_name': '5А', 'new_teacher': 'Иванов', 'new_room': '102'},
    ]

    await updater._notify_entity_subscribers(
        SimpleNamespace(), _Notif(), 'school_133', '5А', exchanges, None)

    assert calls == [
        ('school_133', 'teacher', 'Иванов', 'Замена'),
        ('school_133', 'room', '101', 'Замена'),
        ('school_133', 'room', '102', 'Замена'),
    ]
