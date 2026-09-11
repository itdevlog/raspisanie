# tests/test_subscriptions.py
"""Тесты подписок на преподавателей/кабинеты и уведомлений подписчикам."""
import os
import tempfile
from types import SimpleNamespace

import pytest

from database.file_db import FileDB
from services.notification_service import NotificationService
from services.subscription_service import SubscriptionService


def _svc():
    d = tempfile.mkdtemp()
    return SubscriptionService(FileDB(os.path.join(d, 'database.json')))


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
    context = SimpleNamespace(bot=bot, bot_data={'subscription_service': s})

    count = await svc.notify_subscribers(context, 'school_133', 'teacher', 'Иванов', 'Текст замены')

    assert count == 2
    assert [cid for cid, _ in bot.sent] == [7, 8]
    assert all(text == 'Текст замены' for _, text in bot.sent)


@pytest.mark.asyncio
async def test_notify_subscribers_no_subscribers_returns_zero():
    s = _svc()
    bot = _FakeBot()
    svc = NotificationService()
    context = SimpleNamespace(bot=bot, bot_data={'subscription_service': s})

    count = await svc.notify_subscribers(context, 'school_133', 'room', '101', 'Текст')

    assert count == 0
    assert bot.sent == []


@pytest.mark.asyncio
async def test_notify_subscribers_without_service_returns_zero():
    bot = _FakeBot()
    svc = NotificationService()
    context = SimpleNamespace(bot=bot, bot_data={})

    count = await svc.notify_subscribers(context, 'school_133', 'room', '101', 'Текст')

    assert count == 0


@pytest.mark.asyncio
async def test_background_hook_notifies_new_teacher_and_room(monkeypatch):
    from core.background_updater import BackgroundUpdater

    calls = []

    class _Notif:
        def _format_exchange_notification(self, class_name, exchanges, date):
            return 'Замена'

        async def notify_subscribers(self, context, school_id, kind, name, text):
            calls.append((school_id, kind, name, text))
            return 1

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
