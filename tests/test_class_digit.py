# tests/test_class_digit.py
"""Юнит-тесты для матчинга цифры класса (p.11)."""
from handlers.common.callback_handler import _class_matches_digit, _get_class_letters_for_digit


def test_one_does_not_match_eleven():
    assert _class_matches_digit("11а", 1) is False
    assert _class_matches_digit("1а", 1) is True


def test_ten_as_two_digit():
    assert _class_matches_digit("10а", 10) is True
    assert _class_matches_digit("10а", 1) is False


def test_bare_digit_no_letter():
    assert _class_matches_digit("1", 1) is False


def test_letters_grouped_by_digit():
    classes = ["1а", "1б", "11а", "2а", "10б"]
    assert _get_class_letters_for_digit(classes, 1) == ["а", "б"]
    assert _get_class_letters_for_digit(classes, 11) == ["а"]
    assert _get_class_letters_for_digit(classes, 2) == ["а"]
