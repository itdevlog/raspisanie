# tests/test_free_rooms.py
"""Юнит-тесты поиска свободных кабинетов (как «Найти свободный кабинет» на сайте).

Свободный кабинет на урок N — тот, где после применения замен (CLASS_EXCHANGE,
TEACH_EXCHANGE) в это время нет занятий: базовый урок не привязан к кабинету,
или привязанный урок отменён ('F'), или кабинет в замене указан иной.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from services.room_service import RoomService

TZ = ZoneInfo('Asia/Yekaterinburg')


def _school_data():
    return {
        'CLASSES': {'c1': '5а', 'c2': '6б'},
        'TEACHERS': {'t1': 'Иванов'},
        'ROOMS': {'r1': '101', 'r2': '102', 'r3': '103'},
        'SUBJECTS': {'s1': 'Математика', 's2': 'Биология'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['09:00', '09:45']},
        'LESSONSINDAY': 12,
        # пятница (5), урок 1: 5а в каб. 101; урок 2: 6б в каб. 101
        'CLASS_SCHEDULE': {
            'p1': {
                'c1': {'501': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}},
                'c2': {'502': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}},
            }
        },
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
    }


def _friday(hour=10):
    return datetime(2026, 9, 11, hour, 0, tzinfo=TZ)


def test_free_rooms_on_lesson():
    """На урок 2: 101 занят, 102 и 103 свободны."""
    svc = RoomService(_school_data())
    free = svc.get_free_rooms(_friday(), lesson_num=2)
    assert free == ['102', '103']


def test_free_rooms_on_empty_schedule():
    """Урок, на который расписания нет вовсе — свободны все кабинеты."""
    svc = RoomService(_school_data())
    free = svc.get_free_rooms(_friday(), lesson_num=7)
    assert free == ['101', '102', '103']


def test_free_rooms_respect_class_exchange_cancel():
    """Отмена урока ('F') освобождает кабинет на этот слот."""
    school = _school_data()
    school['CLASS_EXCHANGE'] = {'c1': {'11.09.2026': {'1': {'s': 'F'}}}}
    svc = RoomService(school)
    free = svc.get_free_rooms(_friday(), lesson_num=1)
    assert '101' in free


def test_free_rooms_respect_class_exchange_move_in():
    """Замена, приводящая урок в кабинет 102, занимает его."""
    school = _school_data()
    school['CLASS_EXCHANGE'] = {'c1': {'11.09.2026': {
        '1': {'s': ['s2'], 't': ['t1'], 'r': ['r2']},
    }}}
    svc = RoomService(school)
    free = svc.get_free_rooms(_friday(), lesson_num=1)
    assert '102' not in free
    assert '103' in free


def test_free_rooms_respect_teacher_exchange_move_in():
    """Замена через TEACH_EXCHANGE с r занимает указанный кабинет."""
    school = _school_data()
    school['TEACH_EXCHANGE'] = {'t1': {'11.09.2026': {
        '1': {'s': 's2', 'c': ['c1'], 'r': ['r2']},
    }}}
    svc = RoomService(school)
    free = svc.get_free_rooms(_friday(), lesson_num=1)
    assert '102' not in free


def test_free_rooms_vacation_day():
    """Каникулы — все кабинеты свободны."""
    school = _school_data()
    school['HOLIDAY_TRANSFER'] = {'11.09.2026': {'type': 'vacation'}}
    svc = RoomService(school)
    free = svc.get_free_rooms(_friday(), lesson_num=1)
    assert free == ['101', '102', '103']


def test_format_free_rooms_message():
    """Текст сообщения со свободными кабинетами на текущий/следующий урок."""
    school = _school_data()
    svc = RoomService(school)
    text = svc.get_free_rooms_message(_friday(hour=9), lesson_num=2)
    assert '102' in text
    assert '103' in text
    assert '09:00' in text


def test_format_free_rooms_all_busy():
    """Все заняты — сообщение говорит об этом."""
    school = _school_data()
    for room in ('r2', 'r3'):
        school['CLASS_SCHEDULE']['p1']['c1']['502'] = {'s': ['s1'], 't': ['t1'], 'r': [room]}
    # перезапишем: урок 2 в 5а делится на 102 и 103, 6б — в 101
    school['CLASS_SCHEDULE']['p1']['c1']['502'] = {'s': ['s1', 's1'], 't': ['t1', 't1'], 'r': ['r2', 'r3']}
    svc = RoomService(school)
    text = svc.get_free_rooms_message(_friday(hour=9), lesson_num=2)
    assert 'Все кабинеты заняты' in text
