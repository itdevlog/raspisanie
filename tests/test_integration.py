# tests/test_integration.py
"""Интеграционные тесты с моками (pytest-asyncio)."""
from types import SimpleNamespace

pytest_plugins = ['anyio']


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append(text)
        return SimpleNamespace()

    async def send_chat_action(self, chat_id, action):
        pass


class FakeQuery:
    def __init__(self):
        self.edits = []
        self.answers = []

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)
        self.last_markup = kwargs.get('reply_markup')

    async def answer(self, text=None, **kwargs):
        self.answers.append(text or '')


def _update(query, chat=None, msg=None):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=100) if chat else None,
        callback_query=query,
        effective_message=msg,
        message=msg,
    )


def _context(bot_data, user_data=None):
    return SimpleNamespace(bot_data=bot_data, user_data=user_data or {}, bot=None)


async def test_school_not_loaded_toast():
    """Нажатие на «school_not_loaded» даёт тост без правки."""
    from handlers.callbacks.navigation_callbacks import NavigationCallbackHandler

    q = FakeQuery()
    up = _update(q)
    ctx = _context({})
    h = NavigationCallbackHandler()
    await h.handle(up, ctx, 'school_not_loaded')
    assert q.edits == []
    assert any('загружаются' in a for a in q.answers)


async def test_unknown_navigation_toast():
    from handlers.callbacks.navigation_callbacks import NavigationCallbackHandler

    q = FakeQuery()
    up = _update(q)
    ctx = _context({})
    await NavigationCallbackHandler().handle(up, ctx, 'nonexistent_cb')
    assert any('Неизвестная' in a for a in q.answers)


async def test_entity_search_render():
    """Рендер меню сущности (teacher) при наличии школы."""
    from handlers.teachers.teacher_menu import teacher_menu_handler

    q = FakeQuery()
    up = _update(q)
    school_data = {'CLASSES': {}, 'TEACHERS': {'t1': 'Иванов'}, 'ROOMS': {}, 'SUBJECTS': {}}
    bot_data = {
        'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
        'schools_data': {'school_133': school_data},
    }
    ctx = _context(bot_data)
    await teacher_menu_handler(up, ctx)
    assert q.edits and 'Поиск преподавателя' in q.edits[-1]


async def test_room_menu_has_free_rooms_button():
    """В меню кабинетов есть кнопка «Свободный кабинет»."""
    from handlers.rooms.room_schedule import room_menu_handler

    q = FakeQuery()
    up = _update(q)
    school_data = {'CLASSES': {}, 'TEACHERS': {}, 'ROOMS': {'r1': '101'}, 'SUBJECTS': {}}
    bot_data = {
        'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
        'schools_data': {'school_133': school_data},
    }
    ctx = _context(bot_data)
    await room_menu_handler(up, ctx)
    assert q.edits and 'Расписание кабинетов' in q.edits[-1]
    # Кнопка «Свободный кабинет» ведёт на room_free_now
    buttons = [btn.text for row in (q.last_markup.inline_keyboard if q.last_markup else [])
               for btn in row]
    assert any('Свободный кабинет' in text for text in buttons)


async def test_free_rooms_callback_renders():
    """Callback room_free_now рендерит список свободных кабинетов."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from handlers.rooms.room_schedule import free_rooms_handler

    school_data = {
        'CLASSES': {'c1': '5а'},
        'TEACHERS': {'t1': 'Иванов'},
        'ROOMS': {'r1': '101', 'r2': '102'},
        'SUBJECTS': {'s1': 'Математика'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['09:00', '09:45']},
        'LESSONSINDAY': 12,
        'CLASS_SCHEDULE': {'p1': {'c1': {'501': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}}}},
        'CLASS_EXCHANGE': {},
    }
    bot_data = {
        'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
        'schools_data': {'school_133': school_data},
    }
    q = FakeQuery()
    up = _update(q)
    ctx = _context(bot_data)

    # 08:30 пятницы — идёт урок 1 (101 занят, 102 свободен)
    import handlers.rooms.room_schedule as rs
    real_now = datetime.now
    fake_now = datetime(2026, 9, 11, 8, 30, tzinfo=ZoneInfo('Asia/Yekaterinburg'))
    setattr(rs, 'datetime', SimpleNamespace(now=lambda tz=None: fake_now))

    try:
        await free_rooms_handler(up, ctx)
    finally:
        setattr(rs, 'datetime', real_now)

    assert q.edits
    assert 'Свободные кабинеты' in q.edits[-1]
    assert '102' in q.edits[-1]
    assert '101' not in q.edits[-1].replace('Свободные кабинеты на 1-й урок', '')
