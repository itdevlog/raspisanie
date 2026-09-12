"""Симметричный diff: исчезнувшая замена даёт событие «снята»."""
import logging
from datetime import datetime

import pytz

from services.exchange_detector import ExchangeDetector


def _detector():
    d = ExchangeDetector.__new__(ExchangeDetector)
    d.logger = logging.getLogger('test')
    d.moscow_tz = pytz.timezone('Asia/Yekaterinburg')
    d.previous_schedules = {}
    return d


def test_removed_exchange_is_reported():
    d = _detector()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=d.moscow_tz)
    school = {'SUBJECTS': {'1': 'Математика'}, 'TEACHERS': {}, 'ROOMS': {}}
    previous = {'3': {'lesson_num': '3', 'data': {'s': ['1']}, 'is_cancelled': False,
                      'formatted': {'lesson_num': 3, 'original_subject': 'Урок 3'}}}
    current: dict = {}
    events = d._compare_class_exchanges('5А', previous, current, school, date)
    removals = [e for e in events if e.get('removed')]
    assert len(removals) == 1
    assert removals[0]['lesson_num'] == 3
    assert removals[0]['original_subject'] == 'Урок 3'


def test_class_with_only_exchange_removed_emits_removal():
    d = _detector()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=d.moscow_tz)
    school = {
        'CLASSES': {'c1': '5А'},
        'CLASS_EXCHANGE': {'c1': {'11.09.2026': {'3': {'s': '1', 't': '1', 'r': '1'}}}},
        'SUBJECTS': {'1': 'Математика'},
        'TEACHERS': {'1': 'Иванов'},
        'ROOMS': {'1': '101'},
    }
    first = d.detect_exchanges('s', school, date, persist=False)
    assert first
    assert not any(e.get('removed') for e in first)

    school['CLASS_EXCHANGE'] = {'c1': {'11.09.2026': {}}}
    second = d.detect_exchanges('s', school, date, persist=False)
    removals = [e for e in second if e.get('removed')]
    assert len(removals) == 1
    assert removals[0]['class_name'] == '5А'
    assert removals[0]['lesson_num'] == 3


def test_removal_is_rendered_in_notification():
    from services.notification_service import NotificationService

    svc = NotificationService.__new__(NotificationService)
    svc.logger = logging.getLogger('test')
    svc.moscow_tz = pytz.timezone('Asia/Yekaterinburg')
    date = datetime(2026, 9, 11, 12, 0, tzinfo=svc.moscow_tz)
    exchanges = [{
        'class_name': '5А', 'lesson_num': 3, 'removed': True,
        'original_subject': 'Урок 3', 'new_subject': '', 'new_teacher': '',
        'new_room': '', 'is_cancelled': False, 'timestamp': date,
    }]
    text = svc._format_exchange_notification('5А', exchanges, date)
    assert '↩️' in text
    assert 'замена снята' in text


def test_removal_only_notification_header():
    from services.notification_service import NotificationService

    svc = NotificationService.__new__(NotificationService)
    svc.logger = logging.getLogger('test')
    svc.moscow_tz = pytz.timezone('Asia/Yekaterinburg')
    date = datetime(2026, 9, 11, 12, 0, tzinfo=svc.moscow_tz)
    exchanges = [{
        'class_name': '5А', 'lesson_num': 3, 'removed': True,
        'original_subject': 'Урок 3', 'new_subject': '', 'new_teacher': '',
        'new_room': '', 'is_cancelled': False, 'timestamp': date,
    }]
    text = svc._format_exchange_notification('5А', exchanges, date)
    assert 'Замены сняты' in text
    assert 'Новые замены' not in text


def test_mixed_notification_keeps_original_header():
    from services.notification_service import NotificationService

    svc = NotificationService.__new__(NotificationService)
    svc.logger = logging.getLogger('test')
    svc.moscow_tz = pytz.timezone('Asia/Yekaterinburg')
    date = datetime(2026, 9, 11, 12, 0, tzinfo=svc.moscow_tz)
    exchanges = [
        {
            'class_name': '5А', 'lesson_num': 3, 'removed': True,
            'original_subject': 'Урок 3', 'new_subject': '', 'new_teacher': '',
            'new_room': '', 'is_cancelled': False, 'timestamp': date,
        },
        {
            'class_name': '5А', 'lesson_num': 4, 'original_subject': 'Урок 4',
            'new_subject': 'Физика', 'new_teacher': '', 'new_room': '',
            'is_cancelled': False, 'timestamp': date,
        },
    ]
    text = svc._format_exchange_notification('5А', exchanges, date)
    assert 'Новые замены в расписании' in text
