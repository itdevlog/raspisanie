# tests/test_schedule_now.py
"""Тесты селектора текущего/следующего урока (W36).

`BaseScheduleService.select_current_and_next(lessons, date, now=None)`
работает с payload-уроками (`get_day`): поля ``num/start/end/items/
is_cancelled``. Возвращает ``{'current': ..., 'next': ...}``, где каждая
запись — ``{num, time, subject, room, in_minutes}`` либо ``None``.
"""
from datetime import datetime

from config.config import get_timezone
from services.schedule_service import ScheduleService

TZ = get_timezone()
DATE = datetime(2026, 12, 7, tzinfo=TZ)


def _svc():
    school = {
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['09:00', '09:45']},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSONSINDAY': 12,
        'CLASSES': {'c1': '5а'},
        'CLASS_SCHEDULE': {},
        'SUBJECTS': {}, 'TEACHERS': {}, 'ROOMS': {}, 'DAY_NAMES': [],
        'CLASS_EXCHANGE': {},
    }
    return ScheduleService(school, school_id='s')


def _at(hour, minute):
    return datetime(2026, 12, 7, hour, minute, tzinfo=TZ)


def _lesson(num, start, end, subject='Математика', room='101', cancelled=False):
    return {
        'num': num,
        'start': start,
        'end': end,
        'items': [{'subject': subject, 'room': room}],
        'has_exchange': False,
        'is_cancelled': cancelled,
    }


def test_before_first_lesson():
    """До первого урока: current=None, next — первый урок."""
    svc = _svc()
    result = svc.select_current_and_next([_lesson(1, '08:00', '08:45')], DATE, now=_at(7, 0))
    assert result['current'] is None
    assert result['next'] == {
        'num': 1, 'time': '08:00-08:45',
        'subject': 'Математика', 'room': '101', 'in_minutes': 60,
    }


def test_during_lesson():
    """Во время урока: current — идущий урок, next=None."""
    svc = _svc()
    result = svc.select_current_and_next([_lesson(1, '08:00', '08:45')], DATE, now=_at(8, 30))
    assert result['next'] is None
    assert result['current'] == {
        'num': 1, 'time': '08:00-08:45',
        'subject': 'Математика', 'room': '101', 'in_minutes': 15,
    }


def test_between_lessons():
    """Между уроками: current=None, next — ближайший будущий."""
    svc = _svc()
    lessons = [_lesson(1, '08:00', '08:45'), _lesson(2, '09:00', '09:45', subject='Физика', room='202')]
    result = svc.select_current_and_next(lessons, DATE, now=_at(8, 50))
    assert result['current'] is None
    assert result['next'] == {
        'num': 2, 'time': '09:00-09:45',
        'subject': 'Физика', 'room': '202', 'in_minutes': 10,
    }


def test_after_last_lesson():
    """После последнего урока: current=None, next=None."""
    svc = _svc()
    lessons = [_lesson(1, '08:00', '08:45'), _lesson(2, '09:00', '09:45')]
    result = svc.select_current_and_next(lessons, DATE, now=_at(10, 0))
    assert result == {'current': None, 'next': None}


def test_cancelled_lesson_skipped():
    """Отменённый будущий урок не выбирается как next."""
    svc = _svc()
    lessons = [
        _lesson(1, '08:00', '08:45', cancelled=True),
        _lesson(2, '09:00', '09:45', subject='Физика', room='202'),
    ]
    result = svc.select_current_and_next(lessons, DATE, now=_at(7, 0))
    assert result['current'] is None
    assert result['next'] is not None
    assert result['next']['num'] == 2


def test_cancelled_current_skipped():
    """Отменённый идущий урок не считается current."""
    svc = _svc()
    lessons = [_lesson(1, '08:00', '08:45', cancelled=True)]
    result = svc.select_current_and_next(lessons, DATE, now=_at(8, 30))
    assert result == {'current': None, 'next': None}


def test_empty_lessons():
    """Пустой список уроков — обе записи None."""
    svc = _svc()
    assert svc.select_current_and_next([], DATE, now=_at(8, 0)) == {'current': None, 'next': None}


def test_invalid_times_skipped():
    """Урок без валидного времени пропускается."""
    svc = _svc()
    lessons = [
        {'num': 1, 'start': '?', 'end': '?', 'items': [], 'is_cancelled': False},
        {'num': 2, 'start': '', 'end': '', 'items': [], 'is_cancelled': False},
    ]
    assert svc.select_current_and_next(lessons, DATE, now=_at(7, 0)) == {'current': None, 'next': None}


def test_missing_items_yields_empty_subject_and_room():
    """Урок без items не падает; subject/room — пустые строки."""
    svc = _svc()
    lesson = {'num': 1, 'start': '08:00', 'end': '08:45', 'items': [], 'is_cancelled': False}
    result = svc.select_current_and_next([lesson], DATE, now=_at(7, 0))
    assert result['next'] == {
        'num': 1, 'time': '08:00-08:45', 'subject': '', 'room': '', 'in_minutes': 60,
    }


def test_default_now_is_used_when_omitted():
    """now=None не падает (берётся текущее время школы)."""
    svc = _svc()
    result = svc.select_current_and_next([_lesson(1, '08:00', '08:45')], DATE)
    assert set(result) == {'current', 'next'}
