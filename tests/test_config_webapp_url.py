# tests/test_config_webapp_url.py
"""Тесты нормализации WEBAPP_URL.

Telegram принимает в WebAppInfo только http(s)-URL: 'raspisanie.devlogit.ru'
без схемы приводит к BadRequest 'only https links are allowed' и падению /start.
"""
from config.config import normalize_webapp_url


def test_empty_stays_empty():
    assert normalize_webapp_url('') == ''
    assert normalize_webapp_url('   ') == ''


def test_bare_host_gets_https():
    assert normalize_webapp_url('raspisanie.devlogit.ru') == 'https://raspisanie.devlogit.ru'


def test_existing_https_preserved():
    assert normalize_webapp_url('https://x.example') == 'https://x.example'


def test_existing_http_preserved():
    assert normalize_webapp_url('http://localhost:8080') == 'http://localhost:8080'


def test_whitespace_trimmed():
    assert normalize_webapp_url('  raspisanie.devlogit.ru  ') == 'https://raspisanie.devlogit.ru'
