# tests/test_search_flags.py
"""T30: TTL и сброс sibling-флагов ожидания поиска (teacher/room)."""
import time
from types import SimpleNamespace
from typing import Any

import handlers.rooms.room_schedule as room_schedule
from handlers.common.class_schedule import class_schedule_handler
from handlers.common.entity_menu import EntityConfig, EntityMenuHandler
from handlers.common.messaging import (
    SEARCH_FLAG_TTL,
    clear_search_flags,
    search_flag_active,
    set_search_flag,
)


class _Query:
    def __init__(self):
        self.edits = []
        self.answers = []

    async def answer(self, text=None, **kwargs):
        self.answers.append(text)

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)


def _menu(entity: str) -> EntityMenuHandler:
    return EntityMenuHandler(EntityConfig(
        entity=entity,
        label_singular='item',
        label_plural='items',
        icon='📛',
        menu_title='Menu',
        search_input_hint='hint',
        search_example='eg',
        empty_data_msg='empty',
        button_truncate=10,
        state_full_key='full',
        state_search_key='search',
        search_query_key='search_query',
    ))


async def test_search_input_teacher_resets_room_flag():
    q = _Query()
    update: Any = SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=q)
    context: Any = SimpleNamespace(user_data={
        'waiting_for_room_search': True,
        'waiting_for_room_search_at': time.time(),
    })

    await _menu('teacher').search_input(update, context)

    assert context.user_data.get('waiting_for_teacher_search') is True
    assert 'waiting_for_room_search' not in context.user_data
    assert 'waiting_for_room_search_at' not in context.user_data
    assert 'waiting_for_teacher_search_at' in context.user_data


async def test_search_input_room_resets_teacher_flag():
    q = _Query()
    update: Any = SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=q)
    context: Any = SimpleNamespace(user_data={
        'waiting_for_teacher_search': True,
        'waiting_for_teacher_search_at': time.time(),
    })

    await _menu('room').search_input(update, context)

    assert context.user_data.get('waiting_for_room_search') is True
    assert 'waiting_for_teacher_search' not in context.user_data
    assert 'waiting_for_teacher_search_at' not in context.user_data
    assert 'waiting_for_room_search_at' in context.user_data


def test_search_flag_active_requires_fresh_timestamp():
    now = time.time()
    fresh = {'waiting_for_room_search': True, 'waiting_for_room_search_at': now}
    assert search_flag_active(fresh, 'room') is True

    stale = {
        'waiting_for_room_search': True,
        'waiting_for_room_search_at': now - SEARCH_FLAG_TTL - 1,
    }
    assert search_flag_active(stale, 'room') is False
    assert 'waiting_for_room_search' not in stale
    assert 'waiting_for_room_search_at' not in stale


def test_search_flag_active_backward_compatible_without_timestamp():
    assert search_flag_active({'waiting_for_teacher_search': True}, 'teacher') is True
    assert search_flag_active({}, 'teacher') is False


def test_set_search_flag_stores_timestamp_and_clears_siblings():
    user_data: dict = {'waiting_for_room_search': True, 'waiting_for_room_search_at': 1.0}

    set_search_flag(user_data, 'teacher')

    assert user_data['waiting_for_teacher_search'] is True
    assert isinstance(user_data['waiting_for_teacher_search_at'], float)
    assert 'waiting_for_room_search' not in user_data
    assert 'waiting_for_room_search_at' not in user_data


def test_clear_search_flags_removes_timestamps():
    user_data = {
        'waiting_for_teacher_search': True, 'waiting_for_teacher_search_at': 1.0,
        'waiting_for_room_search': True, 'waiting_for_room_search_at': 2.0,
    }

    clear_search_flags(SimpleNamespace(user_data=user_data))

    assert user_data == {}


async def test_stale_room_flag_treated_as_class(monkeypatch):
    called: list = []

    async def fake_room_search(*args, **kwargs):
        called.append('room')

    monkeypatch.setattr(room_schedule, 'handle_room_search_results', fake_room_search)

    replies: list = []

    async def reply_text(text, **kwargs):
        replies.append(text)

    message = SimpleNamespace(text='5а', reply_text=reply_text)
    update: Any = SimpleNamespace(
        effective_user=SimpleNamespace(id=1), message=message, effective_message=message)
    context: Any = SimpleNamespace(
        bot_data={},
        user_data={
            'waiting_for_room_search': True,
            'waiting_for_room_search_at': time.time() - SEARCH_FLAG_TTL - 1,
        },
    )

    await class_schedule_handler(update, context)

    assert called == []
    assert 'waiting_for_room_search' not in context.user_data
    assert replies  # пошло по ветке класса, а не поиска


async def test_fresh_room_flag_routes_to_search(monkeypatch):
    called: list = []

    async def fake_room_search(update, context, query):
        called.append(query)

    monkeypatch.setattr(room_schedule, 'handle_room_search_results', fake_room_search)

    async def reply_text(text, **kwargs):
        pass

    message = SimpleNamespace(text='101', reply_text=reply_text)
    update: Any = SimpleNamespace(
        effective_user=SimpleNamespace(id=1), message=message, effective_message=message)
    context: Any = SimpleNamespace(
        bot_data={
            'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
            'schools_data': {'school_133': {'CLASSES': {}}},
        },
        user_data={'waiting_for_room_search': True, 'waiting_for_room_search_at': time.time()},
    )

    await class_schedule_handler(update, context)

    assert called == ['101']
    assert 'waiting_for_room_search' not in context.user_data
