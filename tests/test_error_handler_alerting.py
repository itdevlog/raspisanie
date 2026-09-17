"""error_handler: повторяющиеся ошибки алертят админов, одиночные — нет."""
import logging
from types import SimpleNamespace
from typing import Any, cast

from bot import ScheduleBot
from services.alert_service import AlertService


class _NotificationStub:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def notify_admins(self, context, message, parse_mode='Markdown'):
        self.messages.append(message)


class _BoomNotifier:
    async def notify_admins(self, *args, **kwargs):
        raise RuntimeError('notify failed')


def _make_bot(alert_service, notification_service):
    bot = ScheduleBot.__new__(ScheduleBot)
    bot.logger = logging.getLogger('test')
    bot.application = cast(Any, SimpleNamespace(bot_data={
        'alert_service': alert_service,
        'notification_service': notification_service,
    }))
    return bot


def _make_update_and_context(error, bot_data):
    replies: list[str] = []

    async def reply_text(text, **kwargs):
        replies.append(text)

    update: Any = SimpleNamespace(effective_message=SimpleNamespace(reply_text=reply_text))
    context: Any = SimpleNamespace(error=error, bot_data=bot_data, bot=SimpleNamespace())
    return update, context, replies


async def test_repeated_error_alerts_admins_once():
    alert = AlertService(threshold=3, window_seconds=300, now=lambda: 0.0)
    notifier = _NotificationStub()
    bot = _make_bot(alert, notifier)

    for _ in range(5):
        update, context, _ = _make_update_and_context(
            RuntimeError('secret boom'), bot.application.bot_data)
        await bot.error_handler(update, context)

    assert len(notifier.messages) == 1
    assert 'RuntimeError' in notifier.messages[0]
    # сообщение об ошибке (потенциальный секрет) в алерт не попадает
    assert 'secret boom' not in notifier.messages[0]


async def test_single_error_does_not_alert_admin():
    alert = AlertService(threshold=3, window_seconds=300, now=lambda: 0.0)
    notifier = _NotificationStub()
    bot = _make_bot(alert, notifier)

    update, context, replies = _make_update_and_context(
        RuntimeError('boom'), bot.application.bot_data)
    await bot.error_handler(update, context)

    assert notifier.messages == []
    assert replies  # пользователь всё равно получает общий текст


async def test_alerting_failure_does_not_break_handler():
    alert = AlertService(threshold=1, window_seconds=300, now=lambda: 0.0)
    bot = _make_bot(alert, _BoomNotifier())

    update, context, replies = _make_update_and_context(
        RuntimeError('boom'), bot.application.bot_data)
    await bot.error_handler(update, context)

    assert replies  # обработчик дожил до ответа пользователю
