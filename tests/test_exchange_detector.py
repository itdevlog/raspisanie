# tests/test_exchange_detector.py
"""Юнит-тесты ExchangeDetector: раунд-трип строковых ключей через JSON."""
import json
import logging
from datetime import datetime

import pytz

from services.exchange_detector import ExchangeDetector


def _make_detector():
    d = ExchangeDetector.__new__(ExchangeDetector)
    d.logger = logging.getLogger('test')
    d.moscow_tz = pytz.timezone('Asia/Yekaterinburg')
    d.previous_schedules = {}
    return d


def test_compare_class_exchanges_json_roundtrip():
    """Ключи lesson_num после JSON раунд-трипа сравниваются как строки (п.5)."""
    d = _make_detector()

    current = {
        '1': {'lesson_num': '1', 'data': {'s': ['Математика'], 't': ['Петров'], 'r': ['201']}, 'is_cancelled': False},
    }
    # Сохранили в файл и загрузили обратно — ключи остаются строками
    serialized = json.dumps({'school_133': {'5А': current}}, ensure_ascii=False)
    loaded = json.loads(serialized)
    prev = loaded['school_133'].get('5А') or {}

    sch = {'SUBJECTS': {'1': ''}, 'TEACHERS': {}, 'ROOMS': {}}
    date = datetime(2026, 9, 11, 12, 0, tzinfo=d.moscow_tz)
    # 'previous' == 'current' -> НОВЫХ замен нет (ключ '1' в prev найден как строка)
    new = d._compare_class_exchanges('5А', prev, current, sch, date)
    assert new == [], f"expected no new exchanges after round-trip, got {new}"


def test_compare_class_exchanges_new_exchange():
    d = _make_detector()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=d.moscow_tz)
    school = {'SUBJECTS': {'1': 'Математика'}, 'TEACHERS': {}, 'ROOMS': {}}
    current = {'3': {'lesson_num': '3', 'data': {'s': ['1']}, 'is_cancelled': False}}
    new = d._compare_class_exchanges('5А', {}, current, school, date)
    assert len(new) == 1
    assert new[0]['lesson_num'] == 3  # приведено к int для уведомления
