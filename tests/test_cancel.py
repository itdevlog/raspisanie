"""Сброс «залипшего» состояния: reset_user_flow и /cancel."""
from types import SimpleNamespace
from typing import Any

from handlers.common.messaging import reset_user_flow
from handlers.start import cancel_handler


def _context():
    return SimpleNamespace(
        user_data={'waiting_for_teacher_search': True, 'waiting_for_room_search': True,
                   'class_digit': '5', 'teacher_search_query': 'Ив',
                   'room_search_query': '101'},
        bot_data={
            'user_service': SimpleNamespace(
                get_user_school=lambda uid: 'school_133',
                get_current_class=lambda uid: None,
            ),
            'schools_data': {'school_133': {'CLASSES': {}}},
        },
    )


def test_reset_user_flow_clears_all():
    ctx = _context()
    reset_user_flow(ctx)
    assert ctx.user_data == {}


async def test_cancel_handler_replies_main_menu():
    sent = []

    async def reply_text(text, **k):
        sent.append(text)

    message = SimpleNamespace(reply_text=reply_text)
    update: Any = SimpleNamespace(effective_user=SimpleNamespace(id=1, first_name='Тест'),
                                 message=message, effective_message=message)
    ctx: Any = _context()
    await cancel_handler(update, ctx)
    assert sent and 'меню' in sent[-1].lower()
    assert ctx.user_data == {}
