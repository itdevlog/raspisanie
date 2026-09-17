# tests/test_callback_data_length.py
"""T31: callback_data кнопки «Обновить» не превышает лимит Telegram в 64 байта."""
from types import SimpleNamespace
from typing import Any, cast

from handlers.common.entity_menu import EntityConfig, EntityMenuHandler
from services.state_service import UserStateService


class _Query:
    def __init__(self):
        self.edits = []
        self.answers = []
        self.last_markup = None

    async def answer(self, text=None, **kwargs):
        self.answers.append(text)

    async def edit_message_text(self, text, reply_markup=None, **kwargs):
        self.edits.append(text)
        self.last_markup = reply_markup


class _StubService:
    def __init__(self, school_data):
        pass

    def get_teacher_schedule_today(self, name):
        return f"расписание {name}"


class _EmptyState:
    def __init__(self):
        self.saved = {}

    def get_user_list(self, user_id, key):
        return None

    def set_user_list(self, user_id, key, items):
        self.saved[key] = items

    def get_user_page(self, user_id, key, default=0):
        return default


def _handler() -> EntityMenuHandler:
    return EntityMenuHandler(EntityConfig(
        entity='teacher',
        label_singular='преподаватель',
        label_plural='преподавателей',
        icon='👨‍🏫',
        menu_title='Поиск преподавателя',
        search_input_hint='hint',
        search_example='eg',
        empty_data_msg='empty',
        button_truncate=20,
        state_full_key='teachers',
        state_search_key='search_teachers',
        search_query_key='teacher_search_query',
        service_factory=_StubService,
        get_all_method='get_available_teachers',
        search_method='search_teachers',
    ))


async def test_refresh_callback_data_fits_64_bytes_for_long_name():
    long_name = 'Александровская-Петрова-' * 4  # >64 байт в кириллице
    query = _Query()
    update: Any = SimpleNamespace(
        effective_user=SimpleNamespace(id=1), callback_query=query,
        effective_chat=SimpleNamespace(id=100),
    )
    context: Any = SimpleNamespace(
        bot_data={
            'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
            'schools_data': {'school_133': {'TEACHERS': {}}},
            'state_service': _EmptyState(),
            'subscription_service': None,
        },
        user_data={},
    )

    await _handler().select(update, context, long_name, 'today')

    assert query.last_markup is not None
    assert query.answers  # T32: спиннер снят на успешном пути
    buttons = [
        btn for row in query.last_markup.inline_keyboard for btn in row
        if btn.text == '🔄 Обновить'
    ]
    assert len(buttons) == 1
    assert len(buttons[0].callback_data.encode('utf-8')) <= 64
    assert buttons[0].callback_data == 'teacher_today_idx_0'


def test_refresh_callback_uses_index_and_stores_entity():
    state = _EmptyState()
    cb = _handler()._refresh_callback(1, 'Иванов И.И.', 'today', 'idx', None, cast(UserStateService, state))
    assert cb == 'teacher_today_idx_0'
    assert state.saved['teachers'] == ['Иванов И.И.']


def test_refresh_callback_keeps_short_fallback_without_state():
    cb = _handler()._refresh_callback(1, 'Иванов', 'today', 'idx', None, None)
    assert cb == 'teacher_today_Иванов'
    assert len(cb.encode('utf-8')) <= 64


def test_refresh_callback_drops_too_long_fallback_without_state():
    cb = _handler()._refresh_callback(1, 'Я' * 40, 'today', 'idx', None, None)
    assert cb is None
