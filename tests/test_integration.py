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
