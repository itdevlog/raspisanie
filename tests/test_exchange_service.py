# tests/test_exchange_service.py
"""Юнит-тесты ExchangeService: точный матчинг класса и нет мутации исходных данных."""
from datetime import datetime
from typing import Any

import pytz

from services.exchange_service import ExchangeService


def _school(classes, exchanges=None):
    return {
        'CLASSES': classes,
        'CLASS_EXCHANGE': exchanges or {},
    }


def test_find_class_exact_match_only():
    """'5' не должен матчить '10Б' — только точное (как сделано в schedule_service уже; тут проверка helper)."""
    svc = ExchangeService(_school({'c10a': '10Б', 'c5a': '5а'}))
    assert svc._find_class_id('5а') == 'c5a'
    assert svc._find_class_id('10Б') == 'c10a'
    assert svc._find_class_id('5') is None  # нет класса '5', несмотря на подстроку '10Б'
    assert svc._find_class_id('NOPE') is None


def test_apply_exchanges_does_not_mutate_input():
    """Применение замен не мутирует исходный school_data (п.1 deep-copy фикс)."""
    school = _school(
        {'c1': '5А'},
        {'c1': {'11.09.2026': {'1': {'s': 'Математика', 't': 'Петров', 'r': '201'}}}},
    )
    svc = ExchangeService(school)
    date = datetime(2026, 9, 11, 12, 0, tzinfo=pytz.timezone('Asia/Yekaterinburg'))
    lesson: Any = {'lesson_num': 1, 'data': {'s': ['Физра'], 't': ['Иванов'], 'r': ['101']},
                   'has_exchange': False, 'is_cancelled': False}

    before = {k: (list(v) if isinstance(v, list) else v) for k, v in lesson['data'].items()}
    res = svc.apply_exchanges_to_schedule('5А', [lesson], date)

    assert res[0]['has_exchange'] is True
    # исходный lesson['data'] не изменился (глубокое копирование)
    assert lesson['data'] == before, f"input mutated: {lesson['data']} != {before}"
