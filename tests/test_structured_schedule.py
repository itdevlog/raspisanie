"""Структурный слой get_day/get_week (payload для Mini App)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.room_service import RoomService
from services.schedule_exceptions import EntityNotFoundError, PeriodNotFoundError
from services.schedule_service import ScheduleService
from services.teacher_service import TeacherService

TZ = ZoneInfo('Asia/Yekaterinburg')


def _school():
    return {
        'SCHOOL_NAME': 'Тест',
        'CLASSES': {'c1': '5а', 'c2': '9б'},
        'TEACHERS': {'t1': 'Иванов', 't2': 'Петрова'},
        'ROOMS': {'r1': '101', 'r2': '202'},
        'SUBJECTS': {'s1': 'Математика', 's2': 'Биология'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['08:55', '09:40']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
        # 13.09.2026 — воскресенье; берём понедельник 07.09.2026 (день 1)
        'CLASS_SCHEDULE': {'p1': {'c1': {'101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},
                                              '102': {'s': ['s2'], 't': ['t2'], 'r': ['r2']}}}},
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
    }


def _monday():
    return datetime(2026, 9, 7, 10, 0, tzinfo=TZ)


def test_get_day_class_payload():
    svc = ScheduleService(_school())
    day = svc.get_day('5а', _monday())
    assert day['date'] == '07.09.2026'
    assert day['day_name'] == 'Понедельник'
    assert day['kind'] == 'class'
    assert day['entity'] == '5а'
    assert day['vacation'] is False and day['weekend'] is False
    assert len(day['lessons']) == 2
    first = day['lessons'][0]
    assert first['num'] == 1 and first['start'] == '08:00' and first['end'] == '08:45'
    assert first['items'][0]['subject'] == 'Математика'
    assert first['items'][0]['teacher'] == 'Иванов'
    assert first['items'][0]['room'] == '101'
    assert first['items'][0]['class_name'] is None
    assert first['has_exchange'] is False and first['is_cancelled'] is False


def test_get_day_case_insensitive():
    svc = ScheduleService(_school())
    day = svc.get_day('5А', _monday())
    assert day['entity'] == '5а'


def test_get_day_unknown_class_raises():
    svc = ScheduleService(_school())
    with pytest.raises(EntityNotFoundError) as e:
        svc.get_day('11ю', _monday())
    assert '11ю' in e.value.message


def test_get_day_teacher_payload():
    svc = TeacherService(_school())
    day = svc.get_day('Иванов', _monday())
    assert day['kind'] == 'teacher'
    assert day['lessons'][0]['items'][0]['class_name'] == '5а'


def test_get_day_room_payload():
    svc = RoomService(_school())
    day = svc.get_day('202', _monday())
    assert day['kind'] == 'room'
    assert day['lessons'][0]['items'][0]['class_name'] == '5а'
    assert day['lessons'][0]['items'][0]['subject'] == 'Биология'


def test_get_day_weekend():
    svc = ScheduleService(_school())
    sunday = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    day = svc.get_day('5а', sunday)
    assert day['weekend'] is True and day['lessons'] == []


def test_get_day_vacation():
    school = _school()
    school['HOLIDAY_TRANSFER'] = {'07.09.2026': {'type': 'vacation'}}
    svc = ScheduleService(school)
    day = svc.get_day('5а', _monday())
    assert day['vacation'] is True and day['lessons'] == []


def test_get_day_exchange_marks():
    school = _school()
    school['CLASS_EXCHANGE'] = {'c1': {'07.09.2026': {'1': {'s': 's2', 't': 't2', 'r': 'r2'}}}}
    svc = ScheduleService(school)
    day = svc.get_day('5а', _monday())
    first = day['lessons'][0]
    assert first['has_exchange'] is True
    assert first['items'][0]['subject'] == 'Биология'


def test_get_day_cancelled():
    school = _school()
    school['CLASS_EXCHANGE'] = {'c1': {'07.09.2026': {'1': {'s': 'F'}}}}
    svc = ScheduleService(school)
    day = svc.get_day('5а', _monday())
    first = day['lessons'][0]
    assert first['is_cancelled'] is True


def test_get_day_no_period_raises():
    school = _school()
    school['PERIODS'] = {}
    svc = ScheduleService(school)
    with pytest.raises(PeriodNotFoundError):
        svc.get_day('5а', _monday())


def test_get_week_five_days():
    svc = ScheduleService(_school())
    days = svc.get_week('5а', 0)
    assert len(days) == 5
    assert days[0]['date'] == '07.09.2026'
    assert days[4]['date'] == '11.09.2026'


def test_get_week_offset_next_week():
    svc = ScheduleService(_school())
    days = svc.get_week('5а', 1)
    assert days[0]['date'] == '14.09.2026'
