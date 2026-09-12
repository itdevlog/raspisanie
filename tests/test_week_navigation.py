# tests/test_week_navigation.py
"""Навигация по неделям: парсинг callback-смещения и клавиатура."""
from handlers.callbacks.class_callbacks import parse_week_offset
from handlers.common.callback_handler import create_class_navigation_keyboard


def test_parse_week_offset_absent_is_zero():
    assert parse_week_offset('class_week_5а') == 0


def test_parse_week_offset_positive_and_negative():
    assert parse_week_offset('class_week_5а_o1') == 1
    assert parse_week_offset('class_week_5а_o-2') == -2
    assert parse_week_offset('class_week_10б_o2') == 2


def _button_callbacks(markup):
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def test_week_keyboard_has_prev_and_next():
    markup = create_class_navigation_keyboard('5а', 'week', week_offset=0)
    callbacks = _button_callbacks(markup)
    assert 'class_week_5а_o-1' in callbacks
    assert 'class_week_5а_o1' in callbacks
    assert 'class_week_5а' in callbacks


def test_week_keyboard_limits_offsets():
    # На границе -2 нет кнопки «прошлая», но есть «следующая»
    markup = create_class_navigation_keyboard('5а', 'week', week_offset=-2)
    callbacks = _button_callbacks(markup)
    assert 'class_week_5а_o-3' not in callbacks
    assert 'class_week_5а_o-1' in callbacks

    markup = create_class_navigation_keyboard('5а', 'week', week_offset=2)
    callbacks = _button_callbacks(markup)
    assert 'class_week_5а_o3' not in callbacks
    assert 'class_week_5а_o1' in callbacks


def test_week_refresh_keeps_offset():
    markup = create_class_navigation_keyboard('5а', 'week', week_offset=1)
    callbacks = _button_callbacks(markup)
    assert 'class_week_5а_o1' in callbacks


def test_non_week_keyboard_has_no_week_buttons():
    markup = create_class_navigation_keyboard('5а', 'today')
    callbacks = _button_callbacks(markup)
    assert not any('_o' in cb for cb in callbacks)


def test_handle_strips_zero_offset_suffix():
    """`_o0` (кнопка «Текущая») не должен попадать в имя класса."""
    from handlers.callbacks.class_callbacks import _WEEK_OFFSET_RE
    assert _WEEK_OFFSET_RE.sub('', 'class_week_5а_o0') == 'class_week_5а'
    assert _WEEK_OFFSET_RE.sub('', 'class_week_5а') == 'class_week_5а'
