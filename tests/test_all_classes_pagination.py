# tests/test_all_classes_pagination.py
"""Регрессия: пагинация «Все классы» сохраняет тип расписания."""
from handlers.common.callback_handler import parse_all_classes_page


def test_parse_valid():
    assert parse_all_classes_page('all_classes_page_week_2') == ('week', 2)
    assert parse_all_classes_page('all_classes_page_today_0') == ('today', 0)


def test_parse_invalid():
    assert parse_all_classes_page('all_classes_page_2') is None
    assert parse_all_classes_page('all_classes_page_week_x') is None
    assert parse_all_classes_page('show_all_week') is None
