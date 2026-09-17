# tests/test_callback_router.py
"""Юнит-тесты роутинга callback-префиксов `_get_handler_key`."""
import pytest

from handlers.callbacks import CallbackRouter

router = CallbackRouter()

CASES = {
    'class_digit_5_today': 'class_digit',
    'admin_refresh_all': 'admin',
    'teacher_today_idx_0': 'teacher',
    'teacher_search_page_2': 'teacher',
    'room_today_sidx_3': 'room',
    'class_today_5а': 'class',
    'menu_teacher': 'menu',
    'menu_room': 'menu',
    'school_info': 'school',
    'show_all_today': 'show_all',
    'all_classes_page_1': 'show_all',
    'clear_digit_today': 'clear_digit',
    'toggle_notifications_on': 'toggle_notifications',
    'toggle_lesson_reminders_on': 'toggle_lesson_reminders',
    'toggle_quiet_hours_off': 'toggle_quiet_hours',
    'toggle_daily_digest_on': 'toggle_daily_digest',
    'toggle_update_notifications_off': 'toggle_update_notifications',
    'class_week_5а_o1': 'class',
    'main_menu': 'main_menu',
    'change_class': 'change_class',
    'unsubscribe_teacher_0': 'unsubscribe',
    'widget_link': 'widget_link',
    'no_such_prefix': 'menu',
}


@pytest.mark.parametrize("cb,expected", list(CASES.items()))
def test_get_handler_key(cb, expected):
    assert router._get_handler_key(cb) == expected
