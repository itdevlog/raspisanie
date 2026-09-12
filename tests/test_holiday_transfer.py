# tests/test_holiday_transfer.py
"""Юнит-тесты HOLIDAY_TRANSFER (переносы праздников, как на сайте Nikasoft).

Формат: HOLIDAY_TRANSFER["дд.мм.гггг"] = {
    "type": "vacation"             — день неучебный (занятий нет),
    "period": <id периода>         — опционально, период переноса,
} или {
    "type": "transfer",            — день работает по расписанию другого дня:
    "daynum": <iso день недели 1..7>,   "weeknum": <1|2> (опц.),
}
"""
from datetime import datetime

import pytz

from services.schedule_service import ScheduleService
from services.teacher_service import TeacherService

TZ = pytz.timezone('Asia/Yekaterinburg')


def _school_data():
    return {
        'CLASSES': {'c1': '5а'},
        'TEACHERS': {'t1': 'Иванов'},
        'ROOMS': {'r1': '101'},
        'SUBJECTS': {'s1': 'Математика', 's2': 'Биология'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
        # пятница (5): биология; суббота (6): математика
        'CLASS_SCHEDULE': {
            'p1': {
                'c1': {
                    '501': {'s': ['s2'], 't': ['t1'], 'r': ['r1']},
                    '601': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},
                }
            }
        },
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
    }


def test_transfer_day_uses_other_weekday_schedule():
    """Перенос: пятница работает по расписанию субботы (daynum=6)."""
    school = _school_data()
    school['HOLIDAY_TRANSFER'] = {'11.09.2026': {'type': 'transfer', 'daynum': 6}}
    svc = ScheduleService(school)
    date = datetime(2026, 9, 11, 10, 0, tzinfo=TZ)  # пятница

    text = svc._get_class_schedule_for_date('5а', date, include_header=True)
    assert 'Математика' in text          # субботнее расписание
    assert 'Биология' not in text         # пятничное не должно показаться


def test_vacation_day_has_no_lessons():
    """Каникулы: в указанный день занятий нет."""
    school = _school_data()
    school['HOLIDAY_TRANSFER'] = {'11.09.2026': {'type': 'vacation'}}
    svc = ScheduleService(school)
    date = datetime(2026, 9, 11, 10, 0, tzinfo=TZ)  # пятница

    text = svc._get_class_schedule_for_date('5а', date, include_header=True)
    assert 'Занятий нет' in text or 'нет занятий' in text.lower() or 'каникул' in text.lower()


def test_no_transfer_usual_schedule():
    """Без переноса — обычное пятничное расписание."""
    svc = ScheduleService(_school_data())
    date = datetime(2026, 9, 11, 10, 0, tzinfo=TZ)
    text = svc._get_class_schedule_for_date('5а', date, include_header=True)
    assert 'Биология' in text


def test_transfer_day_teacher_schedule():
    """Перенос действует и в расписании учителя."""
    school = _school_data()
    school['HOLIDAY_TRANSFER'] = {'11.09.2026': {'type': 'transfer', 'daynum': 6}}
    svc = TeacherService(school)
    date = datetime(2026, 9, 11, 10, 0, tzinfo=TZ)

    text = svc._get_teacher_schedule_for_date('Иванов', date, include_header=True)
    assert 'Математика' in text       # субботнее расписание
    assert 'Биология' not in text


def test_transfer_day_weeknum_prefix():
    """weeknum=2: ключ расписания с префиксом недели ('2' + '6' + '01')."""
    school = _school_data()
    school['HOLIDAY_TRANSFER'] = {'11.09.2026': {'type': 'transfer', 'daynum': 6, 'weeknum': 2}}
    school['CLASS_SCHEDULE']['p1']['c1']['2601'] = {'s': ['s2'], 't': ['t1'], 'r': ['r1']}
    svc = ScheduleService(school)
    date = datetime(2026, 9, 11, 10, 0, tzinfo=TZ)

    text = svc._get_class_schedule_for_date('5а', date, include_header=True)
    # суббота 2-й недели: биология
    assert 'Биология' in text


def test_transfer_with_period_override():
    """period в переносе перекрывает период даты."""
    school = _school_data()
    school['PERIODS']['p2'] = {'b': '01.09.2026', 'e': '31.05.2027'}
    school['HOLIDAY_TRANSFER'] = {'11.09.2026': {'type': 'transfer', 'daynum': 6, 'period': 'p2'}}
    # в p2 у 5а суббота — математика; в p1 у 5а субботы нет уроков… есть, поставим иначе:
    school['CLASS_SCHEDULE']['p2'] = {'c1': {'601': {'s': ['s2'], 't': ['t1'], 'r': ['r1']}}}
    svc = ScheduleService(school)
    date = datetime(2026, 9, 11, 10, 0, tzinfo=TZ)

    text = svc._get_class_schedule_for_date('5а', date, include_header=True)
    assert 'Биология' in text


def test_vacation_day_teacher_schedule_empty():
    """Каникулы: у учителя уроков в этот день нет."""
    school = _school_data()
    school['HOLIDAY_TRANSFER'] = {'11.09.2026': {'type': 'vacation'}}
    svc = TeacherService(school)
    date = datetime(2026, 9, 11, 10, 0, tzinfo=TZ)

    text = svc._get_teacher_schedule_for_date('Иванов', date, include_header=True)
    assert 'занятий нет' in text.lower()
