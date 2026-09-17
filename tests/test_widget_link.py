# tests/test_widget_link.py
"""Кнопка «Ссылка на виджет» в настройках."""
from types import SimpleNamespace
from typing import Any

from handlers.common.settings import send_widget_link
from web.auth import validate_widget_token

BOT_TOKEN = '123456:ABC-DEF_token'


class _FakeQuery:
    def __init__(self):
        self.answers = []
        self.edits = []

    async def answer(self, text=None, **kwargs):
        self.answers.append(text)

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)


def _context(webapp_url, token=BOT_TOKEN):
    return SimpleNamespace(bot_data={
        'webapp_url': webapp_url,
        'config': SimpleNamespace(TELEGRAM_TOKEN=token),
    })


async def test_send_widget_link_builds_signed_url():
    query = _FakeQuery()
    update: Any = SimpleNamespace(effective_user=SimpleNamespace(id=42), callback_query=query)
    context = _context('https://example.com')

    await send_widget_link(update, context)

    assert query.edits, "сообщение не отправлено"
    text = query.edits[0]
    assert 'https://example.com/widget.html?user_id=42&token=' in text
    token = text.split('token=')[1].split('`')[0].strip()
    assert validate_widget_token(token, 42, BOT_TOKEN) is True


async def test_send_widget_link_without_webapp_url():
    query = _FakeQuery()
    update: Any = SimpleNamespace(effective_user=SimpleNamespace(id=42), callback_query=query)
    context = _context(None)

    await send_widget_link(update, context)

    assert not query.edits
    assert any('WEBAPP_URL' in (a or '') for a in query.answers)
