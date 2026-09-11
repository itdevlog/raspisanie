"""Мёртвые ветки удалены; ошибки не утекают пользователю."""
import inspect
from types import SimpleNamespace

from handlers.callbacks import class_callbacks, room_callbacks, teacher_callbacks
from handlers.common.entity_menu import EntityConfig, EntityMenuHandler
from handlers.common.messaging import GENERIC_ERROR_MSG
from services.exchange_detector import ExchangeDetector


def _src(mod):
    return inspect.getsource(mod)


class _BoomService:
    def __init__(self, school_data):
        pass

    def get_available_teachers(self):
        raise RuntimeError('secret-internal-path /root/x')


class _Query:
    def __init__(self):
        self.edits = []
        self.answers = []

    async def answer(self, *a, **k):
        self.answers.append(a[0] if a else '')

    async def edit_message_text(self, text, **k):
        self.edits.append(text)


def _handler():
    return EntityMenuHandler(EntityConfig(
        entity='teacher', label_singular='преподаватель', label_plural='преподавателей',
        icon='👨‍🏫', menu_title='Поиск преподавателя', search_input_hint='x',
        search_example='x', empty_data_msg='нет', button_truncate=20,
        state_full_key='teachers', state_search_key='search_teachers',
        search_query_key='teacher_search_query',
        service_factory=_BoomService, get_all_method='get_available_teachers',
        search_method='search_teachers',
    ))


async def test_entity_menu_does_not_leak_exception_text():
    query = _Query()
    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=query, message=None)
    context = SimpleNamespace(
        bot_data={
            'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
            'schools_data': {'school_133': {'TEACHERS': {}}},
        },
        user_data={},
    )
    await _handler().menu(update, context)
    assert query.edits and query.edits[-1] == GENERIC_ERROR_MSG
    assert 'secret-internal-path' not in query.edits[-1]


def test_dead_menu_branches_removed():
    assert 'menu_teacher' not in _src(teacher_callbacks)
    assert 'menu_room' not in _src(room_callbacks)
    assert 'parts[1] == "digit"' not in _src(class_callbacks)


def test_unused_exchange_detector_methods_removed():
    assert not hasattr(ExchangeDetector, 'get_current_exchanges_for_class')
    assert not hasattr(ExchangeDetector, '_get_teacher_name')
    assert hasattr(ExchangeDetector, 'clear_school_cache')
