"""Sentry опционален: нет DSN/пакета — тихий пропуск, ошибки не всплывают."""
import logging
import sys
from types import SimpleNamespace

from bot import ScheduleBot


def _make_bot():
    bot = ScheduleBot.__new__(ScheduleBot)
    bot.logger = logging.getLogger('bot')
    return bot


def test_init_sentry_skipped_without_dsn(monkeypatch):
    monkeypatch.delenv('SENTRY_DSN', raising=False)
    calls = []
    monkeypatch.setitem(sys.modules, 'sentry_sdk',
                        SimpleNamespace(init=lambda **kw: calls.append(kw)))

    _make_bot()._init_sentry()

    assert calls == []


def test_init_sentry_missing_package_is_logged_not_raised(monkeypatch, caplog):
    monkeypatch.setenv('SENTRY_DSN', 'https://example@sentry.io/1')
    # None в sys.modules -> `import sentry_sdk` бросает ImportError
    monkeypatch.setitem(sys.modules, 'sentry_sdk', None)

    with caplog.at_level(logging.INFO, logger='bot'):
        _make_bot()._init_sentry()

    assert 'sentry_sdk' in caplog.text


def test_init_sentry_calls_init_with_dsn(monkeypatch):
    monkeypatch.setenv('SENTRY_DSN', 'https://example@sentry.io/1')
    calls = []
    monkeypatch.setitem(sys.modules, 'sentry_sdk',
                        SimpleNamespace(init=lambda **kw: calls.append(kw)))

    _make_bot()._init_sentry()

    assert calls
    assert calls[0]['dsn'] == 'https://example@sentry.io/1'


def test_init_sentry_failure_is_swallowed(monkeypatch):
    monkeypatch.setenv('SENTRY_DSN', 'https://example@sentry.io/1')

    def _boom(**kwargs):
        raise RuntimeError('bad dsn')

    monkeypatch.setitem(sys.modules, 'sentry_sdk', SimpleNamespace(init=_boom))

    _make_bot()._init_sentry()  # не должно бросать
