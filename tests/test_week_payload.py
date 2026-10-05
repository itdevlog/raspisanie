"""W34: неделя Пн–Сб по `WEEKDAYNUM` + `weekday_num` в payload `/week`.

`_week_dates` берёт число учебных дней из `school_data['WEEKDAYNUM']`
(default 5, clamp 1..6). Telegram-путь `_get_week_schedule` остаётся
`range(5)` — поведение бота прежнее.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from services.schedule_service import ScheduleService
from web.api import create_app

TZ = ZoneInfo('Asia/Yekaterinburg')

_WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница',
             'Суббота', 'Воскресенье']


def _school(**overrides):
    """Школа с уроком на каждом дне недели (включая субботу, день 6)."""
    schedule = {f'{day}01': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}
                for day in range(1, 7)}
    school = {
        'SCHOOL_NAME': 'Тест',
        'CLASSES': {'c1': '5а'},
        'TEACHERS': {'t1': 'Иванов'},
        'ROOMS': {'r1': '101'},
        'SUBJECTS': {'s1': 'Математика'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': _WEEKDAYS,
        'CLASS_SCHEDULE': {'p1': {'c1': schedule}},
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
    }
    school.update(overrides)
    return school


def _monday():
    return datetime(2026, 9, 7, 10, 0, tzinfo=TZ)


def _client(school):
    bot_data = {'schools_data': {'school_133': school}}
    return TestClient(create_app({'bot_data': bot_data}))


# --- свойство weekday_num --------------------------------------------------

def test_weekday_num_default_is_five():
    assert ScheduleService(_school()).weekday_num == 5


def test_weekday_num_reads_school_value():
    assert ScheduleService(_school(WEEKDAYNUM=6)).weekday_num == 6


def test_weekday_num_clamps_zero_to_one():
    assert ScheduleService(_school(WEEKDAYNUM=0)).weekday_num == 1


def test_weekday_num_clamps_seven_to_six():
    assert ScheduleService(_school(WEEKDAYNUM=7)).weekday_num == 6


# --- _week_dates -----------------------------------------------------------

def test_week_dates_five_day_school():
    svc = ScheduleService(_school())
    assert [d.date().isoformat() for d in svc._week_dates(0, today=_monday())] == [
        '2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10', '2026-09-11']


def test_week_dates_six_day_school_includes_saturday():
    svc = ScheduleService(_school(WEEKDAYNUM=6))
    assert [d.date().isoformat() for d in svc._week_dates(0, today=_monday())] == [
        '2026-09-07', '2026-09-08', '2026-09-09', '2026-09-10',
        '2026-09-11', '2026-09-12']


def test_week_dates_six_day_school_respects_offset():
    svc = ScheduleService(_school(WEEKDAYNUM=6))
    dates = svc._week_dates(1, today=_monday())
    assert dates[0].date().isoformat() == '2026-09-14'
    assert dates[-1].date().isoformat() == '2026-09-19'


# --- get_week payload count ------------------------------------------------

def test_get_week_five_days_by_default():
    svc = ScheduleService(_school())
    days = svc.get_week('5а', 0, today=_monday())
    assert len(days) == 5
    assert days[-1]['date'] == '11.09.2026'


def test_get_week_six_days_for_six_day_school():
    svc = ScheduleService(_school(WEEKDAYNUM=6))
    days = svc.get_week('5а', 0, today=_monday())
    assert len(days) == 6
    assert days[-1]['date'] == '12.09.2026'


# --- route /week -----------------------------------------------------------

def test_week_route_default_weekday_num():
    body = _client(_school()).get(
        '/api/school_133/schedule/class/5а/week?offset=0').json()
    assert body['weekday_num'] == 5
    assert len(body['days']) == 5


def test_week_route_six_day_weekday_num():
    body = _client(_school(WEEKDAYNUM=6)).get(
        '/api/school_133/schedule/class/5а/week?offset=0').json()
    assert body['weekday_num'] == 6
    assert len(body['days']) == 6


# --- Telegram-формат не меняется -------------------------------------------

def test_telegram_week_ignores_weekdaynum():
    five = ScheduleService(_school())
    six = ScheduleService(_school(WEEKDAYNUM=6))
    out_five = five._get_week_schedule(
        'class', '5а', five._get_class_schedule_for_date, 0)
    out_six = six._get_week_schedule(
        'class', '5а', six._get_class_schedule_for_date, 0)
    assert out_five == out_six
    # ровно 5 дневных заголовков, суббота не выводится
    assert out_six.count('📅 *5а - ') == 5
    assert 'Суббота' not in out_six
