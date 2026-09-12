# tests/test_schools.py
"""Юнит-тесты для config/schools.py::get_display_name."""
from config.schools import get_display_name


def test_normal_name_passthrough():
    d = {"SCHOOL_NAME": "МАОУ СОШ №133"}
    assert get_display_name("school_133", d) == "МАОУ СОШ №133"


def test_empty_name_falls_back():
    # ключ есть, но значение пустое — как у школы 181
    assert get_display_name("school_181", {"SCHOOL_NAME": ""}) == "МАОУ СОШ №181"


def test_missing_school_data():
    assert get_display_name("school_181", None) == "МАОУ СОШ №181"  # type: ignore[arg-type]  # None обрабатывается функцией


def test_unknown_school_id():
    assert get_display_name("school_999", {"SCHOOL_NAME": ""}) == "school_999"
