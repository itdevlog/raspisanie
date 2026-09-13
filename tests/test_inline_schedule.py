"""Inline-режим: поиск расписания в любом чате."""
from types import SimpleNamespace

from handlers.inline_schedule import build_inline_results


def _school():
    return {
        'SCHOOL_NAME': 'Тест',
        'CLASSES': {'c1': '5а', 'c2': '9б'},
        'TEACHERS': {'t1': 'Иванов'},
        'ROOMS': {'r1': '101'},
        'SUBJECTS': {'s1': 'Математика'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
        'CLASS_SCHEDULE': {'p1': {'c1': {'101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}}}},
        'CLASS_EXCHANGE': {}, 'TEACH_EXCHANGE': {}, 'HOLIDAY_TRANSFER': {},
    }


def _ctx(school_data):
    return SimpleNamespace(
        bot_data={'schools_data': {'school_133': school_data},
                  'user_service': SimpleNamespace(
                      get_user_school=lambda uid: 'school_133',
                      get_user_class=lambda uid, s=None: '5а')},
    )


def test_build_results_by_prefix():
    results = build_inline_results('9', _ctx(_school()), user_id=1)
    assert len(results) == 1
    assert results[0].title == '📅 9б — сегодня'


def test_build_results_case_insensitive():
    results = build_inline_results('5А', _ctx(_school()), user_id=1)
    assert len(results) == 1
    assert results[0].id == 'cls_5а'


def test_build_results_empty_query_uses_profile_class():
    results = build_inline_results('', _ctx(_school()), user_id=1)
    assert len(results) == 1
    assert results[0].title == '📅 5а — сегодня'


def test_build_results_limited_to_5():
    school = _school()
    school['CLASSES'] = {f'c{i}': f'{i}а' for i in range(1, 11)}
    results = build_inline_results('а', _ctx(school), user_id=1)
    assert len(results) <= 5


def test_build_results_missing_data_returns_empty():
    assert build_inline_results('9', SimpleNamespace(bot_data={}), user_id=1) == []
