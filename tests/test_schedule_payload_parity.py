"""W33: паритет полей дневного payload — период, смена, группы, метод-час.

Проверяем только структурный `get_day` (API); Telegram-форматирование не
затрагивается. Форматы Nikasoft (проверены на реальной выгрузке school_133):

- ``PERIODS``: ``{period_id: {'b': ..., 'e': ..., 'name': ...}}``;
- ``CLASS_SHIFT``: ``{period_id: {class_id: shift_number}}`` — только у классов
  со второй сменой;
- ``CLASSGROUPS``: плоский ``{'0': 'Группа 1', '1': 'Группа 2'}``; в некоторых
  выгрузках вложен по периодам — тогда под-словари объединяются;
- ключ группы у урока — параллельный список ``g`` (``g[i]`` соответствует
  ``s[i]``/``t[i]``/``r[i]``); при отсутствии ``g`` берётся индекс ``str(i)``;
- предмет ``'M'`` — метод-час (``METHOD_STR``).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

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
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027',
                           'name': '01.09.2026 - 31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['08:55', '09:40'],
                         '3': ['09:50', '10:35']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': ['Понедельник', 'Вторник', 'Среда', 'Четверг',
                      'Пятница', 'Суббота', 'Воскресенье'],
        # 07.09.2026 — понедельник (день 1).
        'CLASS_SCHEDULE': {'p1': {'c1': {
            # урок 1: две группы, параллельные списки выровнены через `g`
            '101': {'s': ['s1', 's2'], 't': ['t1', 't2'], 'r': ['r1', 'r2'],
                    'g': ['0', '1']},
            # урок 2: одна группа, `g` отсутствует
            '102': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},
            # урок 3: метод-час
            '103': {'s': ['M'], 't': ['t1'], 'r': ['r1']},
        }}},
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
        # вторая смена только у 5а (c1)
        'CLASS_SHIFT': {'p1': {'c1': 2}},
        'CLASSGROUPS': {'0': 'Группа 1', '1': 'Группа 2'},
    }


def _monday():
    return datetime(2026, 9, 7, 10, 0, tzinfo=TZ)


# --- get_period_info -------------------------------------------------------

def test_get_period_info_present():
    svc = ScheduleService(_school())
    assert svc.get_period_info(_monday()) == {
        'b': '01.09.2026', 'e': '31.05.2027', 'name': '01.09.2026 - 31.05.2027'}


def test_get_period_info_none_when_no_periods():
    school = _school()
    school['PERIODS'] = {}
    svc = ScheduleService(school)
    assert svc.get_period_info(_monday()) is None


def test_get_period_info_none_when_date_outside_period():
    school = _school()
    school['PERIODS'] = {'p1': {'b': '01.09.2026', 'e': '09.09.2026'}}
    svc = ScheduleService(school)
    assert svc.get_period_info(datetime(2026, 10, 5, tzinfo=TZ)) is None


# --- _day_payload: period / shift -----------------------------------------

def test_day_payload_has_period():
    svc = ScheduleService(_school())
    day = svc.get_day('5а', _monday())
    assert day['period'] == {
        'b': '01.09.2026', 'e': '31.05.2027', 'name': '01.09.2026 - 31.05.2027'}


def test_day_payload_shift_present():
    svc = ScheduleService(_school())
    day = svc.get_day('5а', _monday())
    assert day['shift'] == 2


def test_day_payload_shift_absent_for_class_without_second_shift():
    svc = ScheduleService(_school())
    day = svc.get_day('9б', _monday())
    assert day['shift'] is None


def test_day_payload_shift_absent_for_teacher():
    svc = TeacherService(_school())
    day = svc.get_day('Иванов', _monday())
    assert day['shift'] is None


def test_week_no_period_payload_has_none_period():
    school = _school()
    school['PERIODS'] = {}
    svc = ScheduleService(school)
    days = svc.get_week('5а', 0, today=_monday())
    assert all(d['no_period'] is True for d in days)
    assert all(d['period'] is None for d in days)


# --- _lessons_payload: groups / is_method_hour ----------------------------

def test_items_groups_aligned_with_parallel_lists():
    svc = ScheduleService(_school())
    day = svc.get_day('5а', _monday())
    first = day['lessons'][0]['items']
    assert first[0]['groups'] == 'Группа 1'
    assert first[1]['groups'] == 'Группа 2'


def test_item_groups_none_for_single_division():
    svc = ScheduleService(_school())
    day = svc.get_day('5а', _monday())
    second = day['lessons'][1]['items']
    assert second[0]['groups'] is None


def test_item_groups_none_when_classgroups_absent():
    school = _school()
    school['CLASSGROUPS'] = {}
    svc = ScheduleService(school)
    day = svc.get_day('5а', _monday())
    assert day['lessons'][0]['items'][0]['groups'] is None


def test_item_groups_supports_period_nested_shape():
    school = _school()
    school['CLASSGROUPS'] = {'p1': {'0': 'Группа 1', '1': 'Группа 2'}}
    svc = ScheduleService(school)
    day = svc.get_day('5а', _monday())
    assert day['lessons'][0]['items'][0]['groups'] == 'Группа 1'


def test_item_groups_falls_back_to_index_without_g():
    school = _school()
    # нет `g`, но две параллельные записи -> ключи '0' и '1'
    school['CLASS_SCHEDULE']['p1']['c1']['101'] = {
        's': ['s1', 's2'], 't': ['t1', 't2'], 'r': ['r1', 'r2']}
    svc = ScheduleService(school)
    day = svc.get_day('5а', _monday())
    items = day['lessons'][0]['items']
    assert items[0]['groups'] == 'Группа 1'
    assert items[1]['groups'] == 'Группа 2'


def test_item_groups_uses_explicit_division_key():
    svc = ScheduleService(_school())
    data = [{
        'lesson_num': 1,
        'data': {'s': ['s1', 's2'], 't': ['t1', 't2'], 'r': ['r1', 'r2'],
                 'g': ['1', '0']},
        'has_exchange': False, 'is_cancelled': False,
    }]
    items = svc._lessons_payload(data)[0]['items']
    assert items[0]['groups'] == 'Группа 2'
    assert items[1]['groups'] == 'Группа 1'


def test_get_day_uses_explicit_division_key_not_index():
    """W41: `g` не теряется в `_get_schedule_data` — переставленный `g` управляет именами."""
    school = _school()
    # Переставляем реальный division-ключ: index-путь дал бы «1», «2» по порядку.
    school['CLASS_SCHEDULE']['p1']['c1']['101']['g'] = ['1', '0']
    svc = ScheduleService(school)
    day = svc.get_day('5а', _monday())
    items = day['lessons'][0]['items']
    assert items[0]['groups'] == 'Группа 2'
    assert items[1]['groups'] == 'Группа 1'


def test_is_method_hour_flag():
    svc = ScheduleService(_school())
    day = svc.get_day('5а', _monday())
    assert day['lessons'][0]['items'][0]['is_method_hour'] is False
    method = day['lessons'][2]['items'][0]
    assert method['is_method_hour'] is True
    assert method['subject'] == 'M'


# --- Telegram-формат не меняется ------------------------------------------

def test_telegram_formatter_untouched_by_parity_fields():
    svc = ScheduleService(_school())
    schedule_data = svc._get_schedule_data('p1', 'c1', 1)
    text = svc._format_schedule_response('class', '5а', _monday(), schedule_data)
    assert 'Математика' in text
    assert 'Группа 1' not in text
    assert 'is_method_hour' not in text
