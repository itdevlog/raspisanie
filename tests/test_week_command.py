# tests/test_week_command.py
"""Поведенческие тесты /week <класс> (handlers/common/week_command.py)."""
from types import SimpleNamespace

from handlers.common.week_command import week_command_handler
from services.schedule_service import ScheduleService

SCHOOL_DATA = {
    'CLASSES': {'c1': '5и', 'c2': '6а'},
    'TEACHERS': {},
    'ROOMS': {},
    'SUBJECTS': {},
    'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
    'LESSON_TIMES': {'1': ['08:00', '08:45']},
    'LESSONSINDAY': 12,
    'CLASS_SCHEDULE': {'p1': {'c1': {'101': {'s': [], 't': [], 'r': []}}}},
    'CLASS_EXCHANGE': {},
    'TEACH_EXCHANGE': {},
    'HOLIDAY_TRANSFER': {},
}


class FakeMessage:
    def __init__(self):
        self.replies = []
        self.deleted = 0

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)
        return self

    async def delete(self):
        self.deleted += 1


def _update(message=None):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_message=message,
        message=message,
        callback_query=None,
    )


def _context(args=None, bot_data=None):
    return SimpleNamespace(
        args=args or [],
        bot_data=bot_data if bot_data is not None else {
            'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
            'schools_data': {'school_133': SCHOOL_DATA},
        },
        user_data={},
    )


async def test_no_args_lists_classes():
    msg = FakeMessage()
    await week_command_handler(_update(msg), _context())
    assert msg.replies
    assert '5и' in msg.replies[-1]
    assert '/week' in msg.replies[-1]


async def test_no_args_no_classes(monkeypatch):
    monkeypatch.setattr(ScheduleService, 'get_available_classes', lambda self: [])
    msg = FakeMessage()
    await week_command_handler(_update(msg), _context())
    assert 'Нет доступных классов' in msg.replies[-1]


async def test_unknown_class():
    msg = FakeMessage()
    await week_command_handler(_update(msg), _context(args=['11ю']))
    assert "Класс '11ю' не найден" in msg.replies[-1]


async def test_success_renders_week(monkeypatch):
    monkeypatch.setattr(ScheduleService, 'get_class_schedule_week',
                        lambda self, name, week_offset=0: f"📅 Расписание {name}")
    msg = FakeMessage()
    await week_command_handler(_update(msg), _context(args=['5И']))
    assert msg.replies[0].startswith('🔄')
    assert any('Расписание 5и' in r for r in msg.replies)
    assert msg.deleted == 1


async def test_schedule_error_is_hidden(monkeypatch):
    def boom(self, name, week_offset=0):
        raise RuntimeError('secret /root/path')
    monkeypatch.setattr(ScheduleService, 'get_class_schedule_week', boom)
    msg = FakeMessage()
    await week_command_handler(_update(msg), _context(args=['5и']))
    assert any('непредвиденная' in r.lower() for r in msg.replies)
    assert not any('/root/path' in r for r in msg.replies)
    assert msg.deleted == 1


async def test_requires_school_no_service():
    msg = FakeMessage()
    ctx = _context(bot_data={})
    await week_command_handler(_update(msg), ctx)
    assert msg.replies == ['❌ Сервис не доступен']


async def test_requires_school_unknown_school():
    msg = FakeMessage()
    ctx = _context(bot_data={
        'user_service': SimpleNamespace(get_user_school=lambda uid: None),
        'schools_data': {'school_133': SCHOOL_DATA},
    })
    await week_command_handler(_update(msg), ctx)
    assert msg.replies == ['❌ Данные для вашей школы не загружены']
