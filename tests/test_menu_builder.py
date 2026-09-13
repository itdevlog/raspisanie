# tests/test_menu_builder.py
"""Юнит-тесты общих построителей главного меню/справки."""
from handlers.common.menu_builder import (
    HELP_TEXT,
    build_help_keyboard,
    build_main_menu_keyboard,
    build_main_menu_text,
    resolve_school_name,
)


def test_help_text_nonempty():
    assert "Помощь" in HELP_TEXT
    assert "/start" in HELP_TEXT


def test_build_help_keyboard_rows():
    kb = build_help_keyboard().to_dict()
    buttons = [b['text'] for row in kb['inline_keyboard'] for b in row]
    assert any("Главное меню" in t for t in buttons)
    assert any("Настройки" in t for t in buttons)


def test_resolve_school_name():
    assert resolve_school_name(None) == "Не выбрана"
    assert resolve_school_name("school_133") == "МАОУ СОШ №133"
    assert resolve_school_name("nope") == "Не выбрана"


def test_build_main_menu_keyboard_has_class_when_selected():
    kb = build_main_menu_keyboard("5а").to_dict()
    texts = [b['text'] for row in kb['inline_keyboard'] for b in row]
    assert any("5а" in t for t in texts)


def test_build_main_menu_text_no_class():
    t = build_main_menu_text(None, None, None)
    assert "Главное меню" in t
    assert "Не выбрана" in t


def test_build_main_menu_keyboard_webapp_button():
    kb = build_main_menu_keyboard("5а", webapp_url="https://x.example").to_dict()
    buttons = [b for row in kb['inline_keyboard'] for b in row]
    wa = [b for b in buttons if b.get('web_app')]
    assert len(wa) == 1
    assert wa[0]['web_app']['url'] == "https://x.example"


def test_build_main_menu_keyboard_no_webapp_without_url():
    kb = build_main_menu_keyboard("5а").to_dict()
    buttons = [b for row in kb['inline_keyboard'] for b in row]
    assert all(not b.get('web_app') for b in buttons)
