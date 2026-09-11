# tests/test_entity_menu_state.py
"""Регрессия: search_results на callback не дёргает None.message."""
from types import SimpleNamespace

from handlers.common.entity_menu import EntityConfig, EntityMenuHandler


class _FakeQuery:
    def __init__(self):
        self.edits = []

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)


class _StubService:
    def __init__(self, school_data):
        pass

    def search_teachers(self, query):
        return ['Иванов И.']


def _handler():
    return EntityMenuHandler(EntityConfig(
        entity='teacher',
        label_singular='преподаватель',
        label_plural='преподавателей',
        icon='👨‍🏫',
        menu_title='Поиск преподавателя',
        search_input_hint='Введите фамилию',
        search_example='Иванов',
        empty_data_msg='нет',
        button_truncate=20,
        state_full_key='teachers',
        state_search_key='search_teachers',
        search_query_key='teacher_search_query',
        service_factory=_StubService,
        get_all_method='get_available_teachers',
        search_method='search_teachers',
    ))


async def test_search_results_callback_without_state_service():
    query = _FakeQuery()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        callback_query=query,
        message=None,
    )
    context = SimpleNamespace(
        bot_data={
            'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
            'schools_data': {'school_133': {'TEACHERS': {}}},
            'state_service': None,
        },
        user_data={},
    )

    await _handler().search_results(update, context, 'Иванов', 0)

    assert query.edits
    assert 'не доступен' in query.edits[-1]
