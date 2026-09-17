# tests/test_config_validation.py
"""Тесты валидации конфига: TIMEZONE, UPDATE_INTERVAL, MAX_RETRIES, WEBAPP_PORT.

Раньше мусорный TIMEZONE ронял импорт сырым ZoneInfoNotFoundError, а
UPDATE_INTERVAL<=0 / WEBAPP_PORT вне 0..65535 падали только в рантайме.
"""
import importlib

import pytest

from config import config as config_module


def _reload(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return importlib.reload(config_module)


@pytest.fixture(autouse=True)
def _restore_config(monkeypatch):
    yield
    for key in ('TIMEZONE', 'UPDATE_INTERVAL', 'MAX_RETRIES', 'WEBAPP_PORT'):
        monkeypatch.delenv(key, raising=False)
    importlib.reload(config_module)


def test_bad_timezone_raises_clear_error(monkeypatch):
    with pytest.raises(ValueError, match='TIMEZONE'):
        _reload(monkeypatch, TIMEZONE='Mars/Olympus')


def test_valid_timezone_passes(monkeypatch):
    module = _reload(monkeypatch, TIMEZONE='Europe/Moscow')
    assert module.Config.TIMEZONE == 'Europe/Moscow'
    assert str(module.get_timezone()) == 'Europe/Moscow'


def test_update_interval_zero_raises(monkeypatch):
    with pytest.raises(ValueError, match='UPDATE_INTERVAL'):
        _reload(monkeypatch, UPDATE_INTERVAL='0')


def test_update_interval_negative_raises(monkeypatch):
    with pytest.raises(ValueError, match='UPDATE_INTERVAL'):
        _reload(monkeypatch, UPDATE_INTERVAL='-5')


def test_update_interval_valid_passes(monkeypatch):
    module = _reload(monkeypatch, UPDATE_INTERVAL='120')
    assert module.Config.UPDATE_INTERVAL == 120


def test_max_retries_floor_is_one(monkeypatch):
    module = _reload(monkeypatch, MAX_RETRIES='0')
    assert module.Config.MAX_RETRIES == 1


def test_webapp_port_above_range_raises(monkeypatch):
    with pytest.raises(ValueError, match='WEBAPP_PORT'):
        _reload(monkeypatch, WEBAPP_PORT='70000')


def test_webapp_port_negative_raises(monkeypatch):
    with pytest.raises(ValueError, match='WEBAPP_PORT'):
        _reload(monkeypatch, WEBAPP_PORT='-1')


def test_webapp_port_zero_and_valid_pass(monkeypatch):
    assert _reload(monkeypatch, WEBAPP_PORT='0').Config.WEBAPP_PORT == 0
    assert _reload(monkeypatch, WEBAPP_PORT='8081').Config.WEBAPP_PORT == 8081
