# tests/test_exchange_detector.py
"""Юнит-тесты ExchangeDetector: раунд-трип строковых ключей через JSON."""
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from services.exchange_detector import ExchangeDetector


def _make_detector():
    d = ExchangeDetector.__new__(ExchangeDetector)
    d.logger = logging.getLogger('test')
    d.moscow_tz = ZoneInfo('Asia/Yekaterinburg')
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


def _school_with_schedule():
    """Школа с базовым расписанием: 5А, пятница (день 5), урок 3 — Математика."""
    return {
        'CLASSES': {'c1': '5А'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '30.05.2027'}},
        'CLASS_SCHEDULE': {'p1': {'c1': {'503': {'s': ['1'], 't': ['2'], 'r': ['301']}}}},
        'SUBJECTS': {'1': 'Математика'},
        'TEACHERS': {'2': 'Ищенко Ксения Александровна'},
        'ROOMS': {'301': '301'},
        'LESSON_TIMES': {'3': ['10:10', '10:55']},
    }


def test_original_lesson_found_from_base_schedule():
    d = _make_detector()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=d.moscow_tz)  # пятница
    original = d._get_original_lesson('5А', 3, date, _school_with_schedule())
    assert original == {'subject': 'Математика',
                        'teacher': 'Ищенко Ксения Александровна',
                        'room': '301'}


def test_original_lesson_missing_lesson_returns_none():
    d = _make_detector()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=d.moscow_tz)
    assert d._get_original_lesson('5А', 7, date, _school_with_schedule()) is None


def test_original_lesson_no_school_data_returns_none():
    d = _make_detector()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=d.moscow_tz)
    assert d._get_original_lesson('5А', 3, date, None) is None


def test_original_subject_fallback_to_lesson_n():
    d = _make_detector()
    assert d._get_original_subject('5А', 3, None) == 'Урок 3'


def test_formatted_exchange_includes_original_details_and_time():
    """formatted-словарь несёт original_* и lesson_time для уведомления."""
    d = _make_detector()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=d.moscow_tz)
    school = _school_with_schedule()
    school['CLASS_EXCHANGE'] = {'c1': {'11.09.2026': {'3': {'s': '3', 't': '9', 'r': '4022'}}}}
    school['SUBJECTS']['3'] = 'Биология'
    school['TEACHERS']['9'] = 'Усольцева Анастасия Дмитриевна'
    school['ROOMS']['4022'] = '4022'
    school['ROOMS']['4022'] = '4022'

    events = d.detect_exchanges('s', school, date, persist=False)
    assert len(events) == 1
    event = events[0]
    assert event['original_subject'] == 'Математика'
    assert event['original_teacher'] == 'Ищенко Ксения Александровна'
    assert event['original_room'] == '301'
    assert event['lesson_time'] == '10:10-10:55'
    assert event['new_subject'] == 'Биология'
    assert event['new_teacher'] == 'Усольцева Анастасия Дмитриевна'
    assert event['new_room'] == '4022'
