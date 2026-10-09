"""W35: календарь месяца — `get_month` + `GET /schedule/{kind}/{name}/calendar`.

Каждая запись дня месяца строится на `self.get_day(...)`: флаги
выходного/каникул/уроков берутся из дневного payload, а дни вне учебного
периода (PeriodNotFoundError) помечаются `no_period=True` (как в `get_week`).
"""
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from services.room_service import RoomService
from services.schedule_service import ScheduleService
from services.teacher_service import TeacherService
from web.api import create_app

TZ = ZoneInfo('Asia/Yekaterinburg')

_WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница',
             'Суббота', 'Воскресенье']

_ALL_FIELDS = {'date', 'day_name', 'weekend', 'vacation', 'no_period',
               'has_exchange', 'has_cancelled', 'lesson_count'}


def _school(**overrides):
    """Школа с периодом 2024–2027 и уроками: Пн — 2, Вт — 1."""
    schedule = {
        '101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},  # Пн, урок 1
        '102': {'s': ['s2'], 't': ['t1'], 'r': ['r2']},  # Пн, урок 2
        '201': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},  # Вт, урок 1
    }
    school = {
        'SCHOOL_NAME': 'Тест',
        'CLASSES': {'c1': '5а'},
        'TEACHERS': {'t1': 'Иванов', 't2': 'Петров'},
        'ROOMS': {'r1': '101', 'r2': '102'},
        'SUBJECTS': {'s1': 'Математика', 's2': 'Физика'},
        'PERIODS': {'p1': {'b': '01.01.2024', 'e': '31.12.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['08:55', '09:40']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': _WEEKDAYS,
        'CLASS_SCHEDULE': {'p1': {'c1': schedule}},
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
    }
    school.update(overrides)
    return school


def _client(school):
    return TestClient(create_app({'bot_data': {'schools_data': {'school_133': school}}}))


def _by_date(days):
    return {d['date']: d for d in days}


# --- длины месяцев и формат дат --------------------------------------------

def test_month_31_days_january():
    days = ScheduleService(_school()).get_month('5а', 2026, 1)
    assert len(days) == 31
    assert days[0]['date'] == '01.01.2026'
    assert days[-1]['date'] == '31.01.2026'


def test_month_30_days_april():
    days = ScheduleService(_school()).get_month('5а', 2026, 4)
    assert len(days) == 30
    assert days[0]['date'] == '01.04.2026'
    assert days[-1]['date'] == '30.04.2026'


def test_month_28_days_february_non_leap():
    days = ScheduleService(_school()).get_month('5а', 2026, 2)
    assert len(days) == 28
    assert days[-1]['date'] == '28.02.2026'


def test_month_29_days_february_leap():
    days = ScheduleService(_school()).get_month('5а', 2024, 2)
    assert len(days) == 29
    assert days[-1]['date'] == '29.02.2024'


def test_month_entries_have_exact_fields():
    day = ScheduleService(_school()).get_month('5а', 2026, 1)[0]
    assert set(day) == _ALL_FIELDS


def test_month_day_name_follows_calendar():
    days = ScheduleService(_school()).get_month('5а', 2026, 1)
    assert days[0]['day_name'] == 'Четверг'  # 01.01.2026


# --- флаги выходных / каникул ----------------------------------------------

def test_month_marks_weekends():
    days = _by_date(ScheduleService(_school()).get_month('5а', 2026, 1))
    assert days['03.01.2026']['weekend'] is True   # суббота
    assert days['04.01.2026']['weekend'] is True   # воскресенье
    assert days['05.01.2026']['weekend'] is False  # понедельник


def test_month_marks_vacation():
    school = _school(HOLIDAY_TRANSFER={'05.01.2026': {'type': 'vacation'}})
    days = _by_date(ScheduleService(school).get_month('5а', 2026, 1))
    day = days['05.01.2026']
    assert day['vacation'] is True
    assert day['lesson_count'] == 0
    assert day['has_exchange'] is False
    assert day['has_cancelled'] is False
    assert days['06.01.2026']['vacation'] is False


# --- количество уроков ------------------------------------------------------

def test_month_lesson_count():
    days = _by_date(ScheduleService(_school()).get_month('5а', 2026, 1))
    assert days['05.01.2026']['lesson_count'] == 2  # Пн
    assert days['06.01.2026']['lesson_count'] == 1  # Вт
    assert days['03.01.2026']['lesson_count'] == 0  # Сб


# --- замены / отмены --------------------------------------------------------

def test_month_detects_exchange_and_cancelled():
    school = _school(CLASS_EXCHANGE={'c1': {
        '05.01.2026': {'1': {'t': 't2'}},   # замена
        '06.01.2026': {'1': {'s': 'F'}},    # отмена
    }})
    days = _by_date(ScheduleService(school).get_month('5а', 2026, 1))
    assert days['05.01.2026']['has_exchange'] is True
    assert days['05.01.2026']['has_cancelled'] is False
    assert days['05.01.2026']['lesson_count'] == 2
    assert days['06.01.2026']['has_exchange'] is False
    assert days['06.01.2026']['has_cancelled'] is True
    assert days['06.01.2026']['lesson_count'] == 1
    assert days['07.01.2026']['has_exchange'] is False


def test_month_teacher_detects_cancelled_via_class_exchange():
    """Отмена урока класса видна в календаре учителя (маркер «О»)."""
    school = _school(CLASS_EXCHANGE={'c1': {'05.01.2026': {'1': {'s': 'F'}}}})
    days = _by_date(TeacherService(school).get_month('Иванов', 2026, 1))
    assert days['05.01.2026']['has_cancelled'] is True
    assert days['05.01.2026']['lesson_count'] == 2  # урок 1 отменён, урок 2 остался


def test_month_room_detects_cancelled_via_class_exchange():
    """Отмена урока класса видна в календаре кабинета (маркер «О»)."""
    school = _school(CLASS_EXCHANGE={'c1': {'05.01.2026': {'1': {'s': 'F'}}}})
    days = _by_date(RoomService(school).get_month('101', 2026, 1))
    assert days['05.01.2026']['has_cancelled'] is True
    assert days['05.01.2026']['lesson_count'] == 1  # в кабинете 101 только урок 1
    assert days['06.01.2026']['has_cancelled'] is False


# --- дни вне периода --------------------------------------------------------

def test_month_outside_period_is_no_period():
    days = ScheduleService(_school()).get_month('5а', 2020, 1)
    assert len(days) == 31
    assert all(d['no_period'] is True for d in days)
    assert all(d['lesson_count'] == 0 for d in days)
    assert all(d['weekend'] is False for d in days)


# --- все виды сущностей -----------------------------------------------------

def test_month_works_for_teacher_and_room():
    school = _school()
    teacher_days = TeacherService(school).get_month('Иванов', 2026, 1)
    room_days = RoomService(school).get_month('101', 2026, 1)
    assert len(teacher_days) == 31
    assert len(room_days) == 31
    assert teacher_days[0]['date'] == '01.01.2026'
    assert _by_date(teacher_days)['05.01.2026']['lesson_count'] == 2
    assert _by_date(room_days)['05.01.2026']['lesson_count'] == 1


# --- маршрут /calendar ------------------------------------------------------

def test_month_route_class_returns_days():
    body = _client(_school()).get(
        '/api/school_133/schedule/class/5а/calendar?year=2026&month=1').json()
    assert len(body['days']) == 31
    assert body['days'][0]['date'] == '01.01.2026'
    assert body['days'][-1]['date'] == '31.01.2026'


def test_month_route_teacher_and_room():
    client = _client(_school())
    teacher = client.get(
        '/api/school_133/schedule/teacher/Иванов/calendar?year=2026&month=1').json()
    room = client.get(
        '/api/school_133/schedule/room/101/calendar?year=2026&month=1').json()
    assert len(teacher['days']) == 31
    assert len(room['days']) == 31


def test_month_route_year_before_2020_is_422():
    resp = _client(_school()).get(
        '/api/school_133/schedule/class/5а/calendar?year=2019&month=1')
    assert resp.status_code == 422


def test_month_route_year_above_9999_is_422_not_500():
    """W41 fix: `year=10000` раньше падал ValueError в datetime -> 500; теперь 422."""
    resp = _client(_school()).get(
        '/api/school_133/schedule/class/5а/calendar?year=10000&month=1')
    assert resp.status_code == 422


def test_month_route_month_zero_is_422():
    resp = _client(_school()).get(
        '/api/school_133/schedule/class/5а/calendar?year=2026&month=0')
    assert resp.status_code == 422


def test_month_route_month_thirteen_is_422():
    resp = _client(_school()).get(
        '/api/school_133/schedule/class/5а/calendar?year=2026&month=13')
    assert resp.status_code == 422


def test_month_route_unknown_entity_is_404():
    resp = _client(_school()).get(
        '/api/school_133/schedule/class/9z/calendar?year=2026&month=1')
    assert resp.status_code == 404
