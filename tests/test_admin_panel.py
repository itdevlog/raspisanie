"""Админ-панель: одна реализация, /stats показывает статистику."""
from types import SimpleNamespace

import handlers.admin.admin_panel as ap
from handlers.callbacks.admin_callbacks import AdminCallbackHandler


class _Query:
    def __init__(self):
        self.edits = []
        self.answers = []

    async def answer(self, *a, **k):
        self.answers.append(a[0] if a else '')

    async def edit_message_text(self, text, **k):
        self.edits.append(text)


async def test_stats_shows_user_statistics(monkeypatch):
    sent = []

    async def reply_text(text, **k):
        sent.append(text)

    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), message=SimpleNamespace(reply_text=reply_text))
    context = SimpleNamespace(
        bot_data={
            'config': SimpleNamespace(ADMIN_IDS=[1]),
            'user_service': SimpleNamespace(get_users_with_classes=lambda: [
                {'user_id': 1, 'current_school': 'school_133', 'school_classes': {'school_133': '5а'}},
            ]),
        },
        args=['stats'],
    )
    await ap.admin_panel_handler(update, context)
    assert sent and 'Стат' in sent[-1] or any('ользовател' in s for s in sent)


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
