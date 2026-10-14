"""Diff замены «было → стало» в дневном payload (поле ``exchange``).

Поле опционально: добавляется к уроку с заменой/отменой и отсутствует у
обычных уроков. «Было» берётся из базового расписания (тот же lookup, что у
детектора замен), «стало» — из уже применённых данных урока.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from services.schedule_service import ScheduleService
from services.teacher_service import TeacherService
from web.api import create_app

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
        'DAY_NAMES': ['Понедельник', 'Вторник', 'Среда', 'Четверг',
                      'Пятница', 'Суббота', 'Воскресенье'],
        # 07.09.2026 — понедельник (день 1): урок 1 — математика, урок 2 — биология
        'CLASS_SCHEDULE': {'p1': {'c1': {
            '101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},
            '102': {'s': ['s2'], 't': ['t2'], 'r': ['r2']},
        }}},
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
    }


def _monday():
    return datetime(2026, 9, 7, 10, 0, tzinfo=TZ)


# --- класс -----------------------------------------------------------------

def test_exchanged_lesson_carries_exchange_diff():
    school = _school()
    school['CLASS_EXCHANGE'] = {
        'c1': {'07.09.2026': {'1': {'s': 's2', 't': 't2', 'r': 'r2'}}}}
    day = ScheduleService(school).get_day('5а', _monday())
    first = day['lessons'][0]
    assert first['has_exchange'] is True
    assert first['exchange'] == {
        'original_subject': 'Математика',
        'original_teacher': 'Иванов',
        'original_room': '101',
        'new_subject': 'Биология',
        'new_teacher': 'Петрова',
        'new_room': '202',
        'is_cancelled': False,
    }


def test_partial_exchange_keeps_unchanged_side_in_diff():
    """Замена только учителя: предмет/кабинет остаются прежними."""
    school = _school()
    school['CLASS_EXCHANGE'] = {
        'c1': {'07.09.2026': {'1': {'t': 't2'}}}}
    day = ScheduleService(school).get_day('5а', _monday())
    exchange = day['lessons'][0]['exchange']
    assert exchange['original_subject'] == 'Математика'
    assert exchange['new_subject'] == 'Математика'
    assert exchange['original_teacher'] == 'Иванов'
    assert exchange['new_teacher'] == 'Петрова'
    assert exchange['original_room'] == '101'
    assert exchange['new_room'] == '101'


def test_normal_lesson_has_no_exchange_field():
    day = ScheduleService(_school()).get_day('5а', _monday())
    assert day['lessons']
    assert all('exchange' not in lesson for lesson in day['lessons'])


def test_cancelled_lesson_marked_and_new_values_null():
    school = _school()
    school['CLASS_EXCHANGE'] = {'c1': {'07.09.2026': {'1': {'s': 'F'}}}}
    first = ScheduleService(school).get_day('5а', _monday())['lessons'][0]
    assert first['is_cancelled'] is True
    assert first['exchange'] == {
        'original_subject': 'Математика',
        'original_teacher': 'Иванов',
        'original_room': '101',
        'new_subject': None,
        'new_teacher': None,
        'new_room': None,
        'is_cancelled': True,
    }


# --- учитель ---------------------------------------------------------------

def test_teacher_exchange_lesson_carries_exchange_diff():
    school = _school()
    school['CLASS_EXCHANGE'] = {
        'c1': {'07.09.2026': {'1': {'s': 's2', 't': 't2', 'r': 'r2'}}}}
    day = TeacherService(school).get_day('Иванов', _monday())
    first = day['lessons'][0]
    assert first['has_exchange'] is True
    assert first['exchange']['original_subject'] == 'Математика'
    assert first['exchange']['new_subject'] == 'Биология'


def test_exchange_without_original_in_base_yields_nulls():
    """Исходного урока нет в базовом расписании (замена учителя в чужой класс):
    «было» неизвестно — отдаём null, а не выдумываем."""
    school = _school()
    # Иванов в четверг ведёт вместо своего урока урок 1 у 9б (c2), у которого
    # в базовом расписании урока 1 нет — original-урок не находится.
    school['CLASS_SCHEDULE']['p1']['c1'] = {
        '401': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}}
    school['TEACH_EXCHANGE'] = {
        't1': {'10.09.2026': {'1': {'s': 's2', 'c': ['c2'], 'r': ['r2']}}}}
    thursday = datetime(2026, 9, 10, 10, 0, tzinfo=TZ)
    day = TeacherService(school).get_day('Иванов', thursday)
    first = day['lessons'][0]
    assert first['has_exchange'] is True
    assert first['exchange']['original_subject'] is None
    assert first['exchange']['original_teacher'] is None
    assert first['exchange']['original_room'] is None
    assert first['exchange']['new_subject'] == 'Биология'
    assert first['exchange']['new_room'] == '202'


# --- API -------------------------------------------------------------------

def _client(school):
    bot_data = {'schools_data': {'school_133': school}}
    return TestClient(create_app({'bot_data': bot_data}))


def test_day_route_exposes_exchange_field():
    school = _school()
    school['CLASS_EXCHANGE'] = {
        'c1': {'07.09.2026': {'1': {'s': 's2', 't': 't2', 'r': 'r2'}}}}
    body = _client(school).get(
        '/api/school_133/schedule/class/5а?date=07.09.2026').json()
    first = body['lessons'][0]
    assert first['exchange']['original_subject'] == 'Математика'
    assert first['exchange']['new_subject'] == 'Биология'


def test_day_route_null_exchange_for_normal_lessons():
    body = _client(_school()).get(
        '/api/school_133/schedule/class/5а?date=07.09.2026').json()
    assert all('exchange' not in lesson for lesson in body['lessons'])
