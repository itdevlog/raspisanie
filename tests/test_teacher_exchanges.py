# tests/test_teacher_exchanges.py
"""Юнит-тесты применения TEACH_EXCHANGE в расписании преподавателя.

Формат данных Nikasoft:
TEACH_EXCHANGE[teacher_id][дата.дд.мм.гггг][номер урока] = {
    's': <id предмета | 'F'>,      # 'F' — урок отменён (у учителя свободно)
    'c': [<id классов>],           # классы, которые ведёт заменяющий учитель
    'r': [<id кабинета>],
}
"""
from datetime import datetime

import pytz

from services.teacher_service import TeacherService

TZ = pytz.timezone('Asia/Yekaterinburg')


def _school_data():
    return {
        'CLASSES': {'c1': '5а', 'c2': '6б'},
        'TEACHERS': {'t1': 'Иванов', 't2': 'Петров'},
        'ROOMS': {'r1': '101', 'r2': '102'},
        'SUBJECTS': {'s1': 'Математика', 's2': 'Биология', 's3': 'Физика'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['09:00', '09:45']},
        'LESSONSINDAY': 12,
        # день 4 (четверг): Иванов ведёт урок 1 у 5а (математика, каб. 101),
        # урок 2 у 6б (математика, каб. 102)
        'CLASS_SCHEDULE': {
            'p1': {
                'c1': {'401': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}},
                'c2': {'402': {'s': ['s1'], 't': ['t1'], 'r': ['r2']}},
            }
        },
        'TEACH_EXCHANGE': {},
        'CLASS_EXCHANGE': {},
    }


def _thursday() -> datetime:
    return datetime(2026, 9, 10, 10, 0, tzinfo=TZ)  # четверг


def _teacher_lessons(svc: TeacherService, name: str, date: datetime):
    """Собирает данные расписания учителя на дату (внутренний формат)."""
    teacher_id = svc.find_teacher_id(name)
    period_id = svc._get_period_for_date(date)
    return svc._get_teacher_schedule_data(period_id, teacher_id, date.isoweekday(), date)


def test_teacher_schedule_without_exchanges():
    """Без TEACH_EXCHANGE расписание учителя строится как раньше (2 урока)."""
    svc = TeacherService(_school_data())
    lessons = _teacher_lessons(svc, 'Иванов', _thursday())
    assert [x['lesson_num'] for x in lessons] == [1, 2]
    assert not any(x.get('has_exchange') for x in lessons)


def test_teacher_exchange_replaces_lesson():
    """Замена урока учителем: предмет и кабинет берутся из TEACH_EXCHANGE."""
    school = _school_data()
    # Иванов на пятницу: урок 1 — Биология у 6б в каб. 102 (вместо математики у 5а)
    school['TEACH_EXCHANGE'] = {'t1': {'10.09.2026': {
        '1': {'s': 's2', 'c': ['c2'], 'r': ['r2']},
    }}}
    svc = TeacherService(school)
    lessons = _teacher_lessons(svc, 'Иванов', _thursday())

    lesson1 = next(x for x in lessons if x['lesson_num'] == 1)
    assert lesson1['has_exchange'] is True
    assert lesson1['data']['s'] == ['s2']
    # кабинет резолвится в имя (для отображения)
    assert lesson1['data']['r'] == ['102']
    # класс заменён на 6б
    assert lesson1['class_name'] == '6б'
    # урок 2 не затронут
    lesson2 = next(x for x in lessons if x['lesson_num'] == 2)
    assert lesson2['has_exchange'] is False


def test_teacher_exchange_cancelled_marks_is_cancelled():
    """"s": "F" — урок у учителя отменён: is_cancelled=True, урок скрыт."""
    school = _school_data()
    school['TEACH_EXCHANGE'] = {'t1': {'10.09.2026': {
        '1': {'s': 'F'},
    }}}
    svc = TeacherService(school)
    lessons = _teacher_lessons(svc, 'Иванов', _thursday())

    lesson1 = next(x for x in lessons if x['lesson_num'] == 1)
    assert lesson1['is_cancelled'] is True


def test_teacher_exchange_not_mutates_school_data():
    """Применение замен не мутирует исходный TEACH_EXCHANGE/CLASS_SCHEDULE."""
    school = _school_data()
    school['TEACH_EXCHANGE'] = {'t1': {'10.09.2026': {
        '1': {'s': 's2', 'c': ['c2'], 'r': ['r2']},
    }}}
    before = {
        'schedule': {k: {kk: {kkk: dict(vvv) for kkk, vvv in vv.items()}
                         for kk, vv in v.items()} for k, v in school['CLASS_SCHEDULE'].items()},
        'exchange': {k: {kk: {kkk: dict(vvv) for kkk, vvv in vv.items()}
                         for kk, vv in v.items()} for k, v in school['TEACH_EXCHANGE'].items()},
    }
    svc = TeacherService(school)
    _teacher_lessons(svc, 'Иванов', _thursday())

    assert school['CLASS_SCHEDULE'] == before['schedule']
    assert school['TEACH_EXCHANGE'] == before['exchange']


def test_teacher_exchange_other_date_ignored():
    """Замены на другую дату не применяются."""
    school = _school_data()
    school['TEACH_EXCHANGE'] = {'t1': {'11.09.2026': {
        '1': {'s': 's2', 'c': ['c2'], 'r': ['r2']},
    }}}
    svc = TeacherService(school)
    lessons = _teacher_lessons(svc, 'Иванов', _thursday())
    assert not any(x.get('has_exchange') or x.get('is_cancelled') for x in lessons)


def test_teacher_exchange_string_room_accepted():
    """r может прийти строкой (не списком) — принимаем оба формата."""
    school = _school_data()
    school['TEACH_EXCHANGE'] = {'t1': {'10.09.2026': {
        '1': {'s': 's2', 'c': ['c2'], 'r': 'r2'},
    }}}
    svc = TeacherService(school)
    lessons = _teacher_lessons(svc, 'Иванов', _thursday())
    lesson1 = next(x for x in lessons if x['lesson_num'] == 1)
    assert lesson1['data']['r'] == ['102']


def test_teacher_schedule_day_view_marks_exchange():
    """Готовый текст расписания учителя содержит маркер замены и новый предмет."""
    school = _school_data()
    school['TEACH_EXCHANGE'] = {'t1': {'10.09.2026': {
        '1': {'s': 's2', 'c': ['c2'], 'r': ['r2']},
    }}}
    svc = TeacherService(school)
    date = _thursday()
    teacher_id = svc.find_teacher_id('Иванов')
    period_id = svc._get_period_for_date(date)
    schedule_data = svc._get_teacher_schedule_data(period_id, teacher_id, date.isoweekday(), date)

    text = svc._format_schedule_response('teacher', 'Иванов', date, schedule_data, include_header=True)
    assert '🔄' in text
    assert 'Биология' in text

def test_teacher_schedule_day_view_shows_class():
    """В тексте расписания учителя указан класс урока (5а/6б)."""
    school = _school_data()
    svc = TeacherService(school)
    date = _thursday()
    teacher_id = svc.find_teacher_id('Иванов')
    period_id = svc._get_period_for_date(date)
    schedule_data = svc._get_teacher_schedule_data(period_id, teacher_id, date.isoweekday(), date)

    text = svc._format_schedule_response('teacher', 'Иванов', date, schedule_data, include_header=True)
    assert '5а' in text
    assert '6б' in text
