"""Регрессия: RetryAfter приводит к повторной отправке."""
from datetime import timedelta

from telegram.error import RetryAfter

from services.notification_service import NotificationService


class _Bot:
    def __init__(self):
        self.calls = 0

    async def send_message(self, chat_id, text, parse_mode=None):
        self.calls += 1
        if self.calls == 1:
            raise RetryAfter(timedelta(seconds=0))
        return True


async def test_send_retries_after_retryafter():
    svc = NotificationService()
    bot = _Bot()
    ok = await svc._send_message(bot, 1, 'hi')
    assert ok is True
    assert bot.calls == 2
