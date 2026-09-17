# tests/test_class_callbacks.py
"""T32: на успешной загрузке расписания класса query.answer() вызывается."""
from types import SimpleNamespace
from typing import Any

import handlers.callbacks.class_callbacks as class_callbacks
from handlers.callbacks.class_callbacks import ClassCallbackHandler


class _Query:
    def __init__(self):
        self.edits = []
        self.answers = []

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)

    async def answer(self, text=None, **kwargs):
        self.answers.append(text)


def _update(query):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        callback_query=query,
        effective_chat=SimpleNamespace(id=100),
    )


def _context():
    return SimpleNamespace(
        bot_data={
            'user_service': SimpleNamespace(
                set_user_class=lambda *a, **k: True,
                get_user_school=lambda uid: 'school_133',
            ),
            'schools_data': {'school_133': {'CLASSES': {}}},
            'cache_service': None,
        },
        user_data={},
        bot=None,
    )


async def test_successful_class_load_answers_query(monkeypatch):
    class _FakeSchedule:
        def __init__(self, *a, **k):
            pass

        def get_class_schedule_today(self, class_name):
            return 'расписание 5а'

    monkeypatch.setattr(class_callbacks, 'ScheduleService', _FakeSchedule)

    query = _Query()
    update: Any = _update(query)

    await ClassCallbackHandler().handle(update, _context(), 'class_today_5а')

    assert query.answers  # спиннер снят
    assert any('расписание 5а' in e for e in query.edits)
