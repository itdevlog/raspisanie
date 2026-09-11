"""Админ-панель: одна реализация, /stats показывает статистику."""
from types import SimpleNamespace

from telegram import Chat, Message, MessageEntity, Update, User
from telegram.ext import CommandHandler

import handlers.admin.admin_panel as ap
from handlers.callbacks.admin_callbacks import AdminCallbackHandler


class _FakeBot:
    username = 'testbot'

    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append(text)
        return SimpleNamespace(message_id=2)


def _admin_context():
    return SimpleNamespace(
        bot_data={
            'config': SimpleNamespace(ADMIN_IDS=[1]),
            'user_service': SimpleNamespace(get_users_with_classes=lambda: [
                {'user_id': 1, 'current_school': 'school_133', 'school_classes': {'school_133': '5а'}},
            ]),
        },
        user_data={},
        args=None,
    )


def _stats_update(bot):
    """Настоящий Update с `message.text='/stats'` (BOT_COMMAND-entity)."""
    user = User(id=1, first_name='Тест', is_bot=False)
    chat = Chat(id=100, type='private')
    text = '/stats'
    entity = MessageEntity(type=MessageEntity.BOT_COMMAND, offset=0, length=len(text))
    message = Message(message_id=1, date=None, chat=chat, from_user=user, text=text, entities=[entity])
    message.set_bot(bot)
    return Update(update_id=1, message=message)


async def test_stats_command_handler_shows_user_statistics():
    """/stats, прогнанный через настоящий CommandHandler, показывает статистику."""
    bot = _FakeBot()
    update = _stats_update(bot)
    handler = CommandHandler("stats", ap.stats_handler)
    check_result = handler.check_update(update)

    assert check_result, "CommandHandler должен распознать /stats"
    context = _admin_context()
    handler.collect_additional_context(context, update, None, check_result)
    assert context.args == []

    await handler.callback(update, context)

    assert bot.sent
    assert 'Пользователей с классами' in bot.sent[-1]
    assert '*1*' in bot.sent[-1]


async def test_stats_handler_uses_statistics():
    """/stats делегирует в _show_statistics, а не в админ-панель."""
    sent = []

    async def reply_text(text, **k):
        sent.append(text)

    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), message=SimpleNamespace(reply_text=reply_text))
    await ap.stats_handler(update, _admin_context())

    assert sent
    assert 'Пользователей с классами' in sent[-1]
    assert '*1*' in sent[-1]


async def test_show_statistics_callback_branch():
    edits = []

    async def edit_message_text(text, **k):
        edits.append(text)

    update = SimpleNamespace(
        callback_query=SimpleNamespace(edit_message_text=edit_message_text),
        message=None,
    )
    await AdminCallbackHandler()._show_statistics(update, _admin_context())

    assert edits
    assert 'Пользователей с классами' in edits[-1]


async def test_admin_panel_handler_delegates_to_callback_handler(monkeypatch):
    """`/admin` использует единую панель из AdminCallbackHandler."""
    calls = []

    async def show_panel(self, update, context, message_text=None):
        calls.append('panel')

    monkeypatch.setattr(AdminCallbackHandler, '_show_admin_panel', show_panel)

    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), message=SimpleNamespace())
    context = SimpleNamespace(
        bot_data={'config': SimpleNamespace(ADMIN_IDS=[1])},
        args=None,
    )
    await ap.admin_panel_handler(update, context)
    assert calls == ['panel']
