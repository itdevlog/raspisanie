"""T37: ретраи начальной загрузки данных школ при старте."""
import logging
from types import SimpleNamespace
from typing import Any

import bot as bot_module
from bot import ScheduleBot


def _bare_bot(bot_data: dict) -> ScheduleBot:
    b = ScheduleBot.__new__(ScheduleBot)
    b.logger = logging.getLogger('test')
    b.application = SimpleNamespace(bot_data=bot_data)  # type: ignore[assignment]
    return b


def _install_loader(monkeypatch, results: list[dict], calls: list[int]):
    """DataLoader, отдающий результаты по порядку вызовов (последний повторяется)."""

    def factory():
        def load():
            calls.append(1)
            return results[min(len(calls) - 1, len(results) - 1)]
        return SimpleNamespace(load_all_schools_data=load)

    monkeypatch.setattr(bot_module, 'DataLoader', factory)


def test_load_schools_data_success_second_attempt(monkeypatch):
    calls: list[int] = []
    sleeps: list[float] = []
    _install_loader(monkeypatch, [{}, {'school_133': {'SCHOOL_NAME': 'Школа'}}], calls)
    monkeypatch.setattr(bot_module.time, 'sleep', lambda s: sleeps.append(s))

    bot_data: dict[str, Any] = {}
    _bare_bot(bot_data).load_schools_data()

    assert len(calls) == 2
    assert sleeps == [1]
    assert bot_data['schools_data'] == {'school_133': {'SCHOOL_NAME': 'Школа'}}


def test_load_schools_data_success_third_attempt(monkeypatch):
    calls: list[int] = []
    sleeps: list[float] = []
    _install_loader(monkeypatch, [{}, {}, {'school_133': {'SCHOOL_NAME': 'Школа'}}], calls)
    monkeypatch.setattr(bot_module.time, 'sleep', lambda s: sleeps.append(s))

    bot_data: dict[str, Any] = {}
    _bare_bot(bot_data).load_schools_data()

    assert len(calls) == 3
    assert sleeps == [1, 2]
    assert bot_data['schools_data'] == {'school_133': {'SCHOOL_NAME': 'Школа'}}


def test_load_schools_data_permanent_failure_is_empty(monkeypatch):
    calls: list[int] = []
    sleeps: list[float] = []
    _install_loader(monkeypatch, [{}], calls)
    monkeypatch.setattr(bot_module.time, 'sleep', lambda s: sleeps.append(s))

    bot_data: dict[str, Any] = {}
    _bare_bot(bot_data).load_schools_data()

    assert len(calls) == 3
    assert sleeps == [1, 2]
    assert bot_data['schools_data'] == {}


def test_load_schools_data_no_delay_on_success(monkeypatch):
    calls: list[int] = []
    sleeps: list[float] = []
    _install_loader(monkeypatch, [{'school_133': {}}], calls)
    monkeypatch.setattr(bot_module.time, 'sleep', lambda s: sleeps.append(s))

    bot_data: dict[str, Any] = {}
    _bare_bot(bot_data).load_schools_data()

    assert len(calls) == 1
    assert sleeps == []


def test_load_schools_data_partial_result_not_retried(monkeypatch):
    calls: list[int] = []
    sleeps: list[float] = []
    partial = {'school_133': {'SCHOOL_NAME': 'Школа'}}
    _install_loader(monkeypatch, [partial], calls)
    monkeypatch.setattr(bot_module.time, 'sleep', lambda s: sleeps.append(s))

    bot_data: dict[str, Any] = {}
    _bare_bot(bot_data).load_schools_data()

    assert len(calls) == 1
    assert sleeps == []
    assert bot_data['schools_data'] == partial
