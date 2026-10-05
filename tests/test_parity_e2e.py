"""W41: e2e-паритет новых полей через реальный API (`TestClient`).

Тест ходит по публичным маршрутам (`web/api.py`), а не по сервисам напрямую, и
использует детерминированную фикстуру, повторяющую фактические формы выгрузки
Nikasoft `school_133` (формы подтверждены в W33–W37):

- ``PERIODS`` — плоский ``{'5': {'b', 'e', 'name'}}``;
- ``CLASSGROUPS`` — плоский ``{'0': 'Группа 1', '1': 'Группа 2'}``;
- ``CLASS_SHIFT`` — ``{'5': {'012': 6}}`` (вторая смена, реальное значение ``6``);
- ``CLASS_SCHEDULE`` — многозаписная (групповая) ячейка с ``g == ['0', '1']``;
- ``WEEKDAYNUM == 6`` (учебная неделя Пн–Сб).

Реального снапшота `school_133` в репозитории нет, поэтому фикстура
**представительная** (см. отчёт W41). Сетевых запросов тест не делает.

Отдельно проверяется мандат W33: имена групп, которые строит текущий
index-путь (``_get_schedule_data``/``_apply_exchange`` теряют ключ ``g``), равны
тому, что дал бы реальный division-ключ ``g``. Инвариант реальной выгрузки —
``g == ['0', '1']`` по порядку у каждой многозаписной ячейки, ячеек без ``g`` с
несколькими записями нет.
"""
from datetime import datetime

from fastapi.testclient import TestClient

import web.api as api_module
from config.config import get_timezone
from services.schedule_service import ScheduleService
from web.api import create_app

_WEEKDAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница',
             'Суббота', 'Воскресенье']

_SCHOOL_ID = 'school_133'

_ALL_CALENDAR_FIELDS = {
    'date', 'day_name', 'weekend', 'vacation', 'no_period',
    'has_exchange', 'has_cancelled', 'lesson_count',
}


def _school_133():
    """Минимальная фикстура в форме реальной выгрузки `school_133`."""
    return {
        'SCHOOL_NAME': 'МАОУ СОШ №133',
        'CITY_NAME': 'Екатеринбург',
        'EXPORT_DATE': '04.10.2026',
        'EXPORT_TIME': '20:45:13',
        'HOMEPAGE_URL': 'https://school133.example/',
        'WEEKDAYNUM': 6,
        'LESSONSINDAY': 12,
        # Выключенное зачёркивание свободных уроков (W41 extension).
        'STRIKEOUT_FREE_LSN': False,
        'DAY_NAMES': _WEEKDAYS,
        'CLASSES': {'012': '5а', '013': '5б', '014': '10а'},
        'TEACHERS': {'t1': 'Иванов', 't2': 'Петрова'},
        'ROOMS': {'r1': '101', 'r2': '202'},
        'SUBJECTS': {'s1': 'Математика', 's2': 'Биология', 's3': 'История'},
        'PERIODS': {'5': {
            'b': '01.01.2020', 'e': '31.12.2099',
            'name': '01.01.2020 - 31.12.2099',
        }},
        'LESSON_TIMES': {
            '1': ['08:00', '08:45'],
            '2': ['08:55', '09:40'],
            '3': ['09:50', '10:35'],
        },
        'CLASS_SCHEDULE': {'5': {'012': {
            # Пн, урок 1: две группы, реальный `g` в порядке индексов.
            '101': {'s': ['s1', 's2'], 't': ['t1', 't2'], 'r': ['r1', 'r2'],
                    'g': ['0', '1']},
            # Пн, урок 2: одна группа, `g` отсутствует (не групповая ячейка).
            '102': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},
            # Пн, урок 3: метод-час.
            '103': {'s': ['M'], 't': ['t1'], 'r': ['r1']},
            # Сб, урок 1: 6-дневная неделя.
            '601': {'s': ['s3'], 't': ['t2'], 'r': ['r2']},
        }}},
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
        'CLASS_SHIFT': {'5': {'012': 6}},
        'CLASSGROUPS': {'0': 'Группа 1', '1': 'Группа 2'},
    }


def _client(school=None, schools_config=None):
    school = _school_133() if school is None else school
    services = {'bot_data': {'schools_data': {_SCHOOL_ID: school}}}
    if schools_config is not None:
        services['schools_config'] = schools_config
    return TestClient(create_app(services))


def _freeze_now(monkeypatch, hour, minute):
    """Фиксирует `web.api._now` на 07.12.2026 (понедельник)."""
    fixed = datetime(2026, 12, 7, hour, minute, tzinfo=get_timezone())
    monkeypatch.setattr(api_module, '_now', lambda: fixed)
    return fixed


# --- 1. Метаданные школы ----------------------------------------------------

def test_metadata_endpoint_exposes_parity_fields():
    """`/api/schools` отдаёт city/updated/homepage_url/features (W32+W41)."""
    client = _client(schools_config={
        _SCHOOL_ID: {'name': 'МАОУ СОШ №133', 'active': True},
    })
    body = client.get('/api/schools').json()
    assert body['today']
    entry = body['schools'][0]
    assert entry['id'] == _SCHOOL_ID
    assert entry['loaded'] is True
    # city из CITY_NAME (в конфиге школы города нет).
    assert entry['city'] == 'Екатеринбург'
    assert entry['updated'] == '04.10.2026 20:45:13'
    assert entry['homepage_url'] == 'https://school133.example/'
    assert entry['features'] == {
        'teachers': True, 'classrooms': True, 'rooms': True, 'homepage': True,
        'strikeout_free_lsn': False,
    }


# --- 2. Дневной payload: period / shift / groups / method hour -------------

def test_day_payload_parity_fields():
    day = _client().get(
        '/api/school_133/schedule/class/5а?date=07.09.2026').json()
    assert day['period'] == {
        'b': '01.01.2020', 'e': '31.12.2099',
        'name': '01.01.2020 - 31.12.2099',
    }
    # Реальное значение второй смены school_133 — 6 (renderer проверяет >1).
    assert day['shift'] == 6

    first = day['lessons'][0]['items']
    assert [item['groups'] for item in first] == ['Группа 1', 'Группа 2']
    assert first[0]['subject'] == 'Математика'

    # Одиночная ячейка без `g` — группы нет.
    assert day['lessons'][1]['items'][0]['groups'] is None

    method = day['lessons'][2]['items'][0]
    assert method['is_method_hour'] is True
    assert method['subject'] == 'M'


# --- 3. Неделя Пн–Сб --------------------------------------------------------

def test_week_route_returns_six_days_and_saturday_lessons():
    body = _client().get(
        '/api/school_133/schedule/class/5а/week?offset=0').json()
    assert body['weekday_num'] == 6
    assert len(body['days']) == 6
    saturday = body['days'][5]
    assert saturday['day_name'] == 'Суббота'
    assert saturday['weekend'] is False
    assert [item['subject'] for item in saturday['lessons'][0]['items']] == ['История']


# --- 4. Календарь месяца ----------------------------------------------------

def test_calendar_route_one_entry_per_day_with_exact_fields():
    body = _client().get(
        '/api/school_133/schedule/class/5а/calendar?year=2026&month=9').json()
    days = body['days']
    assert len(days) == 30  # сентябрь
    assert days[0]['date'] == '01.09.2026'
    assert days[-1]['date'] == '30.09.2026'
    assert all(set(day) == _ALL_CALENDAR_FIELDS for day in days)
    # 07.09.2026 (Пн) — 3 урока по фикстуре.
    monday = next(day for day in days if day['date'] == '07.09.2026')
    assert monday['lesson_count'] == 3
    assert monday['weekend'] is False
    assert monday['no_period'] is False


# --- 5. Текущий/следующий урок ---------------------------------------------

def test_now_route_shape_and_nullable(monkeypatch):
    _freeze_now(monkeypatch, 7, 30)
    body = _client().get(
        '/api/school_133/schedule/class/5а/now?date=07.12.2026').json()
    assert set(body) == {'server_time', 'current', 'next'}
    assert body['server_time'].startswith('2026-12-07T07:30')
    assert body['current'] is None
    assert body['next'] == {
        'num': 1, 'time': '08:00-08:45',
        'subject': 'Математика', 'room': '101', 'in_minutes': 30,
    }


def test_now_route_current_and_next_can_both_be_null(monkeypatch):
    _freeze_now(monkeypatch, 23, 0)
    body = _client().get(
        '/api/school_133/schedule/class/5а/now?date=07.12.2026').json()
    assert body['current'] is None
    assert body['next'] is None


# --- 6. Поиск классов -------------------------------------------------------

def test_search_returns_classes_alongside_teachers_and_rooms():
    body = _client().get('/api/school_133/search?q=5').json()
    assert set(body) == {'classes', 'teachers', 'rooms'}
    assert body['classes'] == ['5а', '5б']


# --- 7. Мандат: группы по индексу == группы по реальному `g` ----------------

def _multi_entry_cells(school):
    cells = []
    for period in school['CLASS_SCHEDULE'].values():
        for class_schedule in period.values():
            for cell in class_schedule.values():
                length = max(len(cell.get('s', [])), len(cell.get('t', [])),
                             len(cell.get('r', [])))
                if length > 1:
                    cells.append(cell)
    return cells


def test_fixture_multi_entry_cells_carry_ordered_g():
    """Инвариант реальной выгрузки: у каждой групповой ячейки `g` по порядку."""
    cells = _multi_entry_cells(_school_133())
    assert cells, 'фикстура обязана содержать хотя бы одну групповую ячейку'
    for cell in cells:
        length = max(len(cell.get('s', [])), len(cell.get('t', [])),
                     len(cell.get('r', [])))
        assert cell.get('g') == [str(i) for i in range(length)]


def test_groups_index_path_equals_explicit_division_key():
    """W33/W41: index-путь API даёт те же имена, что реальный ключ `g`."""
    school = _school_133()
    cell = school['CLASS_SCHEDULE']['5']['012']['101']
    assert cell['g'] == ['0', '1']

    # Путь API: `_get_schedule_data` теряет `g`, группы берутся по индексу.
    day = _client(school).get(
        '/api/school_133/schedule/class/5а?date=07.09.2026').json()
    api_groups = [item['groups'] for item in day['lessons'][0]['items']]

    # Эталон: тот же `_lessons_payload`, но с реальным `g` в data.
    explicit_items = ScheduleService(school)._lessons_payload([{
        'lesson_num': 1,
        'data': dict(cell),
        'has_exchange': False,
        'is_cancelled': False,
    }])[0]['items']
    explicit_groups = [item['groups'] for item in explicit_items]

    assert api_groups == explicit_groups == ['Группа 1', 'Группа 2']


def test_groups_index_equivalence_survives_exchange():
    """`g` теряется в `_get_schedule_data` ещё до замены — путь остаётся эквивалентным.

    `_apply_exchange` лишь копирует `data` (в котором `g` уже отсутствует),
    поэтому после применения замены имена групп по-прежнему строятся по индексу
    и совпадают с тем, что дал бы реальный ключ `g`.
    """
    school = _school_133()
    school['CLASS_EXCHANGE'] = {'012': {'07.09.2026': {
        '1': {'s': ['s1', 's2'], 't': ['t1', 't2'], 'r': ['r1', 'r2']},
    }}}
    day = _client(school).get(
        '/api/school_133/schedule/class/5а?date=07.09.2026').json()
    assert day['lessons'][0]['has_exchange'] is True
    api_groups = [item['groups'] for item in day['lessons'][0]['items']]

    explicit_groups = [item['groups'] for item in ScheduleService(school)._lessons_payload([{
        'lesson_num': 1,
        'data': {'s': ['s1', 's2'], 't': ['t1', 't2'], 'r': ['r1', 'r2'],
                 'g': ['0', '1']},
        'has_exchange': True,
        'is_cancelled': False,
    }])[0]['items']]

    assert api_groups == explicit_groups == ['Группа 1', 'Группа 2']
