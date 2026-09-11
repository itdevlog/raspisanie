# tests/test_class_schedule_search.py
"""Регрессия: длинный запрос в поиске учителя не падает с KeyError."""
from types import SimpleNamespace

from handlers.common.class_schedule import class_schedule_handler


async def test_long_teacher_search_does_not_keyerror():
    replies = []

    async def reply_text(text, **kwargs):
        replies.append(text)

    message = SimpleNamespace(text='x' * 81, reply_text=reply_text)
    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), message=message)
    context = SimpleNamespace(
        bot_data={},
        user_data={'waiting_for_teacher_search': True},
    )

    await class_schedule_handler(update, context)

    assert any('Слишком длинный' in r for r in replies)
    assert 'waiting_for_teacher_search' not in context.user_data
    assert 'waiting_for_room_search' not in context.user_data
