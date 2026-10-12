# tests/test_schools.py
"""Юнит-тесты для config/schools.py::get_display_name и внешнего JSON школ."""
import importlib
import json

from config import schools as schools_module
from config.schools import SCHOOLS_CONFIG, _load_schools_config, get_display_name


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


def test_added_schools_present_and_active():
    expected = {
        "school_16": ("МАОУ СОШ №16", "63506790"),
        "school_19": ("МАОУ СОШ №19", "69409577"),
        "school_123": ("МАОУ СОШ №123", "12210248"),
    }
    for sid, (name, nikasoft_id) in expected.items():
        cfg = SCHOOLS_CONFIG[sid]
        assert cfg["name"] == name
        assert cfg["city"] == "Екатеринбург"
        assert cfg["active"] is True
        assert cfg["base_url"] == "https://raspisanie.nikasoft.ru/static/public/"
        assert cfg["check_url"] == (
            f"https://raspisanie.nikasoft.ru/check/{nikasoft_id}.html"
        )


def test_builtin_schools_have_real_homepage():
    """Реальные сайты школ прописаны в homepage встроенного конфига."""
    expected = {
        "school_133": "https://xn--133-5cd3cgu2f.xn--80acgfbsl1azdqr.xn--p1ai/",
        "school_181": "https://xn--181-5cd3cgu2f.xn--80acgfbsl1azdqr.xn--p1ai/",
        "school_16": "https://xn--16-6kc3bfr2e.xn--80acgfbsl1azdqr.xn--p1ai/",
        "school_19": "https://xn--19-6kc3bfr2e.xn--80acgfbsl1azdqr.xn--p1ai/",
        "school_123": "https://xn--123-5cd3cgu2f.xn--80acgfbsl1azdqr.xn--p1ai/",
    }
    for sid, homepage in expected.items():
        assert SCHOOLS_CONFIG[sid]["homepage"] == homepage


def test_external_json_adds_and_overrides_schools(tmp_path):
    path = tmp_path / 'schools.json'
    path.write_text(json.dumps({
        "school_133": {"id": "school_133", "name": "Новая 133", "active": True},
        "school_999": {"id": "school_999", "name": "Новая школа", "active": True},
    }), encoding='utf-8')

    cfg = _load_schools_config(str(path))

    assert cfg["school_133"]["name"] == "Новая 133"
    assert cfg["school_999"]["name"] == "Новая школа"
    assert cfg["school_181"]["name"] == "МАОУ СОШ №181"


def test_invalid_json_falls_back_to_builtin(tmp_path):
    path = tmp_path / 'broken.json'
    path.write_text('{ not valid json', encoding='utf-8')

    cfg = _load_schools_config(str(path))

    assert cfg["school_133"]["name"] == "МАОУ СОШ №133"
    assert cfg["school_181"]["name"] == "МАОУ СОШ №181"


def test_missing_file_falls_back_to_builtin(tmp_path):
    cfg = _load_schools_config(str(tmp_path / 'absent.json'))

    assert cfg["school_133"]["name"] == "МАОУ СОШ №133"
    assert cfg["school_181"]["name"] == "МАОУ СОШ №181"


def test_non_object_json_falls_back_to_builtin(tmp_path):
    path = tmp_path / 'list.json'
    path.write_text('[1, 2, 3]', encoding='utf-8')

    cfg = _load_schools_config(str(path))

    assert cfg["school_133"]["name"] == "МАОУ СОШ №133"


def test_empty_path_returns_builtin():
    cfg = _load_schools_config('')

    assert cfg["school_133"]["name"] == "МАОУ СОШ №133"


def test_builtin_config_not_mutated_by_merge(tmp_path):
    path = tmp_path / 'schools.json'
    path.write_text(json.dumps({"school_181": {"name": "X"}}), encoding='utf-8')

    _load_schools_config(str(path))

    assert SCHOOLS_CONFIG["school_181"]["name"] == "МАОУ СОШ №181"


def test_env_var_used_on_import(monkeypatch, tmp_path):
    path = tmp_path / 'external.json'
    path.write_text(json.dumps({
        "school_ext": {"id": "school_ext", "name": "External", "active": True},
    }), encoding='utf-8')
    monkeypatch.setenv('SCHOOLS_CONFIG_FILE', str(path))

    module = importlib.reload(schools_module)
    try:
        assert "school_ext" in module.SCHOOLS_CONFIG
        assert module.SCHOOLS_CONFIG["school_ext"]["name"] == "External"
    finally:
        monkeypatch.delenv('SCHOOLS_CONFIG_FILE', raising=False)
        importlib.reload(schools_module)
