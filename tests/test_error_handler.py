"""Глобальный обработчик ошибок отдаёт общий безопасный текст."""
import logging
from types import SimpleNamespace

from bot import ScheduleBot
from handlers.common.messaging import GENERIC_ERROR_MSG


async def test_error_handler_uses_generic_message():
    bot = ScheduleBot.__new__(ScheduleBot)
    bot.logger = logging.getLogger('test')

    replies = []

    async def reply_text(text, **kwargs):
        replies.append(text)

    update = SimpleNamespace(
        effective_message=SimpleNamespace(reply_text=reply_text))
    context = SimpleNamespace(error=RuntimeError('boom'))

    await bot.error_handler(update, context)

    assert replies == [GENERIC_ERROR_MSG]
