# tests/test_school_selection.py
"""Регрессия: выбор несуществующей школы не показывает успех и чистит флаги."""
from types import SimpleNamespace

import handlers.common.main_menu as main_menu_module
from handlers.schools import school_selection


class _Query:
    def __init__(self):
        self.answers = []
        self.edits = []

    async def answer(self, *args, **kwargs):
        self.answers.append(args[0] if args else '')

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)


def _update(query):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        callback_query=query,
        message=None,
    )


async def test_invalid_school(monkeypatch):
    called = {'main': False}

    async def fake_main(update, context):
        called['main'] = True

    monkeypatch.setattr(main_menu_module, 'main_menu_handler', fake_main)

    query = _Query()
    user_service = SimpleNamespace(set_user_school=lambda uid, sid: False)
    context = SimpleNamespace(
        bot_data={'user_service': user_service},
        user_data={'waiting_for_teacher_search': True, 'class_digit': '5'},
    )

    await school_selection.handle_school_selection(_update(query), context, 'no_such')

    assert called['main'] is False
    assert any('недоступна' in e for e in query.edits)


async def test_valid_school_clears_flags(monkeypatch):
    called = {'main': False}

    async def fake_main(update, context):
        called['main'] = True

    monkeypatch.setattr(main_menu_module, 'main_menu_handler', fake_main)

    query = _Query()
    user_service = SimpleNamespace(set_user_school=lambda uid, sid: True)
    context = SimpleNamespace(
        bot_data={'user_service': user_service},
        user_data={'waiting_for_teacher_search': True, 'class_digit': '5'},
    )

    await school_selection.handle_school_selection(_update(query), context, 'school_181')

    assert called['main'] is True
    assert 'waiting_for_teacher_search' not in context.user_data
    assert 'class_digit' not in context.user_data
