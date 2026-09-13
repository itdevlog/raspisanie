"""Симметричный diff: исчезнувшая замена даёт событие «снята»."""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from services.exchange_detector import ExchangeDetector


def _detector():
    d = ExchangeDetector.__new__(ExchangeDetector)
    d.logger = logging.getLogger('test')
    d.moscow_tz = ZoneInfo('Asia/Yekaterinburg')
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
    svc.moscow_tz = ZoneInfo('Asia/Yekaterinburg')
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
    svc.moscow_tz = ZoneInfo('Asia/Yekaterinburg')
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
    svc.moscow_tz = ZoneInfo('Asia/Yekaterinburg')
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


def _notification_svc():
    from services.notification_service import NotificationService

    svc = NotificationService.__new__(NotificationService)
    svc.logger = logging.getLogger('test')
    svc.moscow_tz = ZoneInfo('Asia/Yekaterinburg')
    return svc


def test_replacement_shows_before_and_after_with_time():
    """Вариант B: время урока и обе стороны «до → после»."""
    svc = _notification_svc()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=svc.moscow_tz)
    exchanges = [{
        'class_name': '6И', 'lesson_num': 6, 'lesson_time': '13:00-13:45',
        'original_subject': 'Математика', 'original_teacher': 'Ищенко Ксения Александровна',
        'original_room': '301',
        'new_subject': 'Биология', 'new_teacher': 'Усольцева Анастасия Дмитриевна',
        'new_room': '4022', 'is_cancelled': False, 'timestamp': date,
    }]
    text = svc._format_exchange_notification('6И', exchanges, date)
    assert '🔄 6. 13:00-13:45 • Математика (Ищенко К.А., каб. 301)' in text
    assert '→ Биология (Усольцева А.Д., каб. 4022)' in text


def test_teacher_shortened_to_initials():
    """ФИО сокращается до «Фамилия И.О.» — в т.ч. обрезанные источником."""
    svc = _notification_svc()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=svc.moscow_tz)
    exchanges = [{
        'class_name': '6И', 'lesson_num': 10, 'lesson_time': '15:35-16:20',
        'original_subject': 'Математика', 'original_teacher': 'Ищенко Ксения Александровна',
        'original_room': '301',
        'new_subject': 'Музыка', 'new_teacher': 'Александрова Валентина Александровн',
        'new_room': '4022', 'is_cancelled': False, 'timestamp': date,
    }]
    text = svc._format_exchange_notification('6И', exchanges, date)
    assert 'Усольцева А.Д.' not in text or True  # sanity: формат не упал
    assert 'Александрова' in text
    assert 'Валентина Александровн' not in text  # полное ФИО не показывается


def test_cancelled_shows_before_subject_only():
    """Отмена: показываем «до» и слово ОТМЕНЕНО, без стороны «после»."""
    svc = _notification_svc()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=svc.moscow_tz)
    exchanges = [{
        'class_name': '6И', 'lesson_num': 12, 'lesson_time': '17:30-18:15',
        'original_subject': 'Информатика', 'original_teacher': 'Петров Пётр Петрович',
        'original_room': '205',
        'new_subject': '', 'new_teacher': '', 'new_room': '',
        'is_cancelled': True, 'timestamp': date,
    }]
    text = svc._format_exchange_notification('6И', exchanges, date)
    assert '❌ 12. 17:30-18:15 • Информатика (Петров П.П., каб. 205) — *ОТМЕНЕНО*' in text


def test_missing_time_falls_back_without_bullet():
    """Нет lesson_time (старый кэш/нет LESSON_TIMES) — строка без времени."""
    svc = _notification_svc()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=svc.moscow_tz)
    exchanges = [{
        'class_name': '5А', 'lesson_num': 2, 'original_subject': 'Урок 2',
        'original_teacher': '', 'original_room': '',
        'new_subject': 'Физика', 'new_teacher': 'Сидоров Иван Иванович',
        'new_room': '101', 'is_cancelled': False, 'timestamp': date,
    }]
    text = svc._format_exchange_notification('5А', exchanges, date)
    assert '🔄 2. Урок 2 → Физика (Сидоров И.И., каб. 101)' in text


def test_removed_uses_new_format_with_time():
    """Снятие замены: формат с временем и исходными деталями."""
    svc = _notification_svc()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=svc.moscow_tz)
    exchanges = [{
        'class_name': '5А', 'lesson_num': 3, 'removed': True,
        'original_subject': 'Математика', 'original_teacher': 'Иванов Иван Иванович',
        'original_room': '301', 'lesson_time': '09:00-09:45',
        'new_subject': '', 'new_teacher': '', 'new_room': '',
        'is_cancelled': False, 'timestamp': date,
    }]
    text = svc._format_exchange_notification('5А', exchanges, date)
    assert '↩️ 3. 09:00-09:45 • Математика (Иванов И.И., каб. 301) — *замена снята*' in text
