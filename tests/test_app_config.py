# tests/test_app_config.py
"""Тесты AppConfig.from_env() и совместимости Config-фасада.

AppConfig — единый источник настроек из окружения; Config остаётся
обратно-совместимым фасадом с прежними именами атрибутов (Config.X).
"""
import importlib

import pytest

from config import config as config_module
from config.config import AppConfig

_ENV_KEYS = (
    'TELEGRAM_TOKEN',
    'UPDATE_INTERVAL',
    'MAX_RETRIES',
    'MAX_PARALLEL_SCHOOLS',
    'ADMIN_IDS',
    'DB_PATH',
    'CACHE_PATH',
    'LOG_LEVEL',
    'LOG_FILE',
    'ADMIN_LOG_FILE',
    'TIMEZONE',
    'WEBAPP_HOST',
    'WEBAPP_PORT',
    'WEBAPP_URL',
    'EDGE_HOST',
    'EDGE_PORT',
    'SNAPSHOT_PATH',
    'SNAPSHOT_MAX_AGE',
    'SNAPSHOT_MAX_BYTES',
    'SNAPSHOT_MAX_RETRIES',
    'EDGE_INGEST_URL',
    'EDGE_INGEST_SECRET',
    'EDGE_AUTH_SECRET',
    'EDGE_ORIGIN_URL',
    'VAPID_PUBLIC_KEY',
    'VAPID_PRIVATE_KEY',
    'VAPID_SUBJECT',
)


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    importlib.reload(config_module)


def test_from_env_reads_all_fields(monkeypatch):
    monkeypatch.setenv('TELEGRAM_TOKEN', 'tok-123')
    monkeypatch.setenv('UPDATE_INTERVAL', '120')
    monkeypatch.setenv('MAX_RETRIES', '5')
    monkeypatch.setenv('MAX_PARALLEL_SCHOOLS', '2')
    monkeypatch.setenv('ADMIN_IDS', '1, 2,3')
    monkeypatch.setenv('DB_PATH', '/tmp/db.json')
    monkeypatch.setenv('CACHE_PATH', '/tmp/cache.json')
    monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
    monkeypatch.setenv('LOG_FILE', '/tmp/bot.log')
    monkeypatch.setenv('ADMIN_LOG_FILE', '/tmp/admin.log')
    monkeypatch.setenv('TIMEZONE', 'Europe/Moscow')
    monkeypatch.setenv('WEBAPP_HOST', '0.0.0.0')
    monkeypatch.setenv('WEBAPP_PORT', '9090')
    monkeypatch.setenv('WEBAPP_URL', 'example.com')
    monkeypatch.setenv('EDGE_HOST', '0.0.0.0')
    monkeypatch.setenv('EDGE_PORT', '9091')
    monkeypatch.setenv('SNAPSHOT_PATH', '/tmp/snapshot.json')
    monkeypatch.setenv('SNAPSHOT_MAX_AGE', '3600')
    monkeypatch.setenv('SNAPSHOT_MAX_BYTES', '1048576')
    monkeypatch.setenv('SNAPSHOT_MAX_RETRIES', '7')
    monkeypatch.setenv('EDGE_INGEST_URL', 'https://origin.example.com/api/snapshot')
    monkeypatch.setenv('EDGE_INGEST_SECRET', 'ingest-secret')
    monkeypatch.setenv('EDGE_AUTH_SECRET', 'auth-secret')
    monkeypatch.setenv('EDGE_ORIGIN_URL', 'https://origin.example.com')
    monkeypatch.setenv('VAPID_PUBLIC_KEY', 'pub-key')
    monkeypatch.setenv('VAPID_PRIVATE_KEY', 'priv-key')
    monkeypatch.setenv('VAPID_SUBJECT', 'mailto:ops@example.ru')

    cfg = AppConfig.from_env()

    assert cfg.telegram_token == 'tok-123'
    assert cfg.update_interval == 120
    assert cfg.max_retries == 5
    assert cfg.max_parallel_schools == 2
    assert cfg.admin_ids == [1, 2, 3]
    assert cfg.db_path == '/tmp/db.json'
    assert cfg.cache_path == '/tmp/cache.json'
    assert cfg.log_level == 'DEBUG'
    assert cfg.log_file == '/tmp/bot.log'
    assert cfg.admin_log_file == '/tmp/admin.log'
    assert cfg.timezone == 'Europe/Moscow'
    assert cfg.webapp_host == '0.0.0.0'
    assert cfg.webapp_port == 9090
    assert cfg.webapp_url == 'https://example.com'
    assert cfg.edge_host == '0.0.0.0'
    assert cfg.edge_port == 9091
    assert cfg.snapshot_path == '/tmp/snapshot.json'
    assert cfg.snapshot_max_age == 3600
    assert cfg.snapshot_max_bytes == 1048576
    assert cfg.snapshot_max_retries == 7
    assert cfg.edge_ingest_url == 'https://origin.example.com/api/snapshot'
    assert cfg.edge_ingest_secret == 'ingest-secret'
    assert cfg.edge_auth_secret == 'auth-secret'
    assert cfg.edge_origin_url == 'https://origin.example.com'
    assert cfg.vapid_public_key == 'pub-key'
    assert cfg.vapid_private_key == 'priv-key'
    assert cfg.vapid_subject == 'mailto:ops@example.ru'


def test_from_env_defaults():
    cfg = AppConfig.from_env()

    assert cfg.telegram_token is None
    assert cfg.update_interval == 3600
    assert cfg.max_retries == 3
    assert cfg.max_parallel_schools == 4
    assert cfg.admin_ids == []
    assert cfg.db_path == './data/database.json'
    assert cfg.cache_path == './data/cache.json'
    assert cfg.log_level == 'INFO'
    assert cfg.log_file == './logs/bot.log'
    assert cfg.admin_log_file == './logs/admin.log'
    assert cfg.timezone == 'Asia/Yekaterinburg'
    assert cfg.webapp_host == '127.0.0.1'
    assert cfg.webapp_port == 8080
    assert cfg.webapp_url == ''
    assert cfg.edge_host == '127.0.0.1'
    assert cfg.edge_port == 8090
    assert cfg.snapshot_path == './data/snapshot.json'
    assert cfg.snapshot_max_age == 7200
    assert cfg.snapshot_max_bytes == 20 * 1024 * 1024
    assert cfg.snapshot_max_retries == 3
    assert cfg.edge_ingest_url == ''
    assert cfg.edge_ingest_secret == ''
    assert cfg.edge_auth_secret == ''
    assert cfg.edge_origin_url == ''
    assert cfg.vapid_public_key == ''
    assert cfg.vapid_private_key == ''
    assert cfg.vapid_subject == 'mailto:admin@example.ru'


def test_snapshot_max_retries_separate_from_max_retries(monkeypatch):
    monkeypatch.setenv('MAX_RETRIES', '9')
    cfg = AppConfig.from_env()
    assert cfg.max_retries == 9
    assert cfg.snapshot_max_retries == 3


def test_from_env_max_parallel_floor_one(monkeypatch):
    monkeypatch.setenv('MAX_PARALLEL_SCHOOLS', '0')
    assert AppConfig.from_env().max_parallel_schools == 1


def test_from_env_bad_timezone_raises(monkeypatch):
    monkeypatch.setenv('TIMEZONE', 'Mars/Olympus')
    with pytest.raises(ValueError, match='TIMEZONE'):
        AppConfig.from_env()


def test_from_env_bad_port_raises(monkeypatch):
    monkeypatch.setenv('WEBAPP_PORT', '70000')
    with pytest.raises(ValueError, match='WEBAPP_PORT'):
        AppConfig.from_env()


def test_from_env_bad_update_interval_raises(monkeypatch):
    monkeypatch.setenv('UPDATE_INTERVAL', '0')
    with pytest.raises(ValueError, match='UPDATE_INTERVAL'):
        AppConfig.from_env()


def test_config_facade_matches_app_config(monkeypatch):
    monkeypatch.setenv('UPDATE_INTERVAL', '777')
    module = importlib.reload(config_module)

    assert module.Config.UPDATE_INTERVAL == 777
    assert module.Config.UPDATE_INTERVAL == module.AppConfig.from_env().update_interval


def test_config_facade_keeps_public_attrs():
    for name in (
        'TELEGRAM_TOKEN',
        'UPDATE_INTERVAL',
        'MAX_RETRIES',
        'MAX_PARALLEL_SCHOOLS',
        'ADMIN_IDS',
        'DB_PATH',
        'CACHE_PATH',
        'LOG_LEVEL',
        'LOG_FILE',
        'ADMIN_LOG_FILE',
        'TIMEZONE',
        'WEBAPP_HOST',
        'WEBAPP_PORT',
        'WEBAPP_URL',
        'EDGE_HOST',
        'EDGE_PORT',
        'SNAPSHOT_PATH',
        'SNAPSHOT_MAX_AGE',
        'SNAPSHOT_MAX_BYTES',
        'SNAPSHOT_MAX_RETRIES',
        'EDGE_INGEST_URL',
        'EDGE_INGEST_SECRET',
        'EDGE_AUTH_SECRET',
        'EDGE_ORIGIN_URL',
        'VAPID_PUBLIC_KEY',
        'VAPID_PRIVATE_KEY',
        'VAPID_SUBJECT',
    ):
        assert hasattr(config_module.Config, name)
    assert callable(config_module.Config.is_admin)
    assert callable(config_module.Config.setup_directories)
    assert callable(config_module.Config.get_updatelog_path)
