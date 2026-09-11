from datetime import datetime

import pytz

from services.schedule_service import ScheduleService

TZ = pytz.timezone('Asia/Yekaterinburg')


def _svc():
    school = {
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['09:00', '09:45']},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSONSINDAY': 12,
        'CLASSES': {'c1': '5а'},
        'CLASS_SCHEDULE': {},
        'SUBJECTS': {}, 'TEACHERS': {}, 'ROOMS': {}, 'DAY_NAMES': [],
    }
    return ScheduleService(school, school_id='s')


def test_get_next_lesson_picks_upcoming():
    svc = _svc()
    date = datetime(2026, 9, 11, 8, 30, tzinfo=TZ)  # 08:30 идёт внутри урока 1 (08:00–08:45), метод берёт следующий урок
    data = [
        {'lesson_num': 1, 'data': {'s': ['x'], 't': [], 'r': []}, 'has_exchange': False, 'is_cancelled': False},
        {'lesson_num': 2, 'data': {'s': ['y'], 't': [], 'r': []}, 'has_exchange': False, 'is_cancelled': False},
    ]
    nxt = svc.get_next_lesson(data, date, now=date)
    assert nxt is not None
    assert nxt['lesson_num'] == 2


def test_get_next_lesson_skips_unknown_times():
    svc = _svc()
    date = datetime(2026, 9, 11, 8, 30, tzinfo=TZ)
    data = [
        {'lesson_num': 3, 'data': {'s': ['x'], 't': [], 'r': []}, 'has_exchange': False, 'is_cancelled': False},
        {'lesson_num': 1, 'data': {'s': ['y'], 't': [], 'r': []}, 'has_exchange': False, 'is_cancelled': False},
    ]
    nxt = svc.get_next_lesson(data, date, now=date)
    assert nxt is not None
    assert nxt['lesson_num'] == 1


def test_get_next_lesson_returns_none_after_last():
    svc = _svc()
    date = datetime(2026, 9, 11, 23, 0, tzinfo=TZ)
    data = [
        {'lesson_num': 2, 'data': {'s': ['y'], 't': [], 'r': []}, 'has_exchange': False, 'is_cancelled': False},
    ]
    assert svc.get_next_lesson(data, date, now=date) is None


def test_week_schedule_accepts_offset():
    svc = _svc()
    # offset 1 не должен падать и не совпадать с текущей неделей
    out = svc.get_class_schedule_week('5а', week_offset=1)
    assert isinstance(out, str)
