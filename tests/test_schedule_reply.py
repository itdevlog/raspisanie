"""Реакции и CopyTextButton при запросе расписания текстом."""
from types import SimpleNamespace

from handlers.common.messaging import reply_long_message


class _Message:
    def __init__(self):
        self.chat_id = 10
        self.message_id = 20
        self.sent = []

    async def reply_text(self, text, parse_mode=None, reply_markup=None, **kw):
        self.sent.append((text, reply_markup))
        return SimpleNamespace(chat=SimpleNamespace(id=self.chat_id), message_id=self.message_id)


class _Bot:
    def __init__(self):
        self.reactions = []

    async def set_message_reaction(self, chat_id, message_id, reaction=None, **kw):
        self.reactions.append((chat_id, message_id, reaction))


async def test_copy_text_keyboard_added():
    msg = _Message()
    update = SimpleNamespace(message=msg, effective_chat=SimpleNamespace(id=10))
    context = SimpleNamespace(bot=_Bot())
    await reply_long_message(update, context, "коротко", copy_text="коротко")
    text, markup = msg.sent[0]
    assert markup is not None
    btn = markup.inline_keyboard[0][0]
    assert btn.copy_text.text == "коротко"


async def test_copy_text_skipped_when_long():
    msg = _Message()
    update = SimpleNamespace(message=msg, effective_chat=SimpleNamespace(id=10))
    context = SimpleNamespace(bot=_Bot())
    await reply_long_message(update, context, "x" * 300, copy_text="x" * 300)
    text, markup = msg.sent[0]
    assert markup is None
