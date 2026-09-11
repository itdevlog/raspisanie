"""Мёртвые ветки удалены; ошибки не утекают через str(e)."""
import inspect

from handlers.callbacks import class_callbacks, room_callbacks, teacher_callbacks
from handlers.common import entity_menu
from services.exchange_detector import ExchangeDetector


def _src(mod):
    return inspect.getsource(mod)


def test_no_raw_exception_interpolation_in_entity_menu():
    src = _src(entity_menu)
    assert '{e}' not in src
    assert 'log_user_error' in src


def test_dead_menu_branches_removed():
    assert 'menu_teacher' not in _src(teacher_callbacks)
    assert 'menu_room' not in _src(room_callbacks)
    assert 'parts[1] == "digit"' not in _src(class_callbacks)


def test_unused_exchange_detector_methods_removed():
    assert not hasattr(ExchangeDetector, 'get_current_exchanges_for_class')
    assert not hasattr(ExchangeDetector, '_get_teacher_name')
    assert hasattr(ExchangeDetector, 'clear_school_cache')
