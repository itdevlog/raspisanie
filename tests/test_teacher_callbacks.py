# tests/test_teacher_callbacks.py
"""Поведенческие тесты TeacherCallbackHandler: роутинг, пагинация, выбор преподавателя."""
from types import SimpleNamespace

import handlers.teachers.teacher_menu as teacher_menu
from handlers.callbacks.teacher_callbacks import TeacherCallbackHandler


class FakeQuery:
    def __init__(self):
        self.edits = []
        self.answers = []

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)

    async def answer(self, text=None, **kwargs):
        self.answers.append(text or '')


class FakeState:
    def __init__(self, lists=None, pages=None):
        self.lists = lists or {}
        self.pages = pages or {}

    def get_user_list(self, uid, key):
        return self.lists.get(key)

    def get_user_page(self, uid, key, default=0):
        return self.pages.get(key, default)


def _update(query, msg=None):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        callback_query=query,
        effective_message=msg,
        message=msg,
        effective_chat=SimpleNamespace(id=100),
    )


def _context(bot_data=None, user_data=None):
    return SimpleNamespace(bot_data=bot_data or {}, user_data=user_data or {}, bot=None)


async def test_pages_info_toast():
    q = FakeQuery()
    await TeacherCallbackHandler().handle(_update(q), _context(), 'teacher_pages_info')
    assert any('навигации' in a for a in q.answers)


async def test_unknown_callback_toast():
    q = FakeQuery()
    await TeacherCallbackHandler().handle(_update(q), _context(), 'zzz')
    assert any('Неизвестная' in a for a in q.answers)


async def test_show_all_dispatch(monkeypatch):
    called = {}

    async def fake(update, context, page=0):
        called['page'] = page

    monkeypatch.setattr(teacher_menu, 'show_all_teachers', fake)
    q = FakeQuery()
    await TeacherCallbackHandler().handle(_update(q), _context(), 'teacher_show_all')
    assert called['page'] == 0


async def test_pagination_dispatch(monkeypatch):
    called = {}

    async def fake(update, context, page=0):
        called['page'] = page

    monkeypatch.setattr(teacher_menu, 'show_all_teachers', fake)
    q = FakeQuery()
    await TeacherCallbackHandler().handle(_update(q), _context(), 'teacher_show_all_3')
    assert called['page'] == 3


async def test_pagination_invalid_toast():
    q = FakeQuery()
    await TeacherCallbackHandler().handle(_update(q), _context(), 'teacher_show_all_x')
    assert any('Ошибка пагинации' in a for a in q.answers)


async def test_search_pagination_without_query_toast():
    q = FakeQuery()
    await TeacherCallbackHandler().handle(_update(q), _context(), 'teacher_search_page_1')
    assert any('Поисковый запрос не найден' in a for a in q.answers)


async def test_search_pagination_dispatch(monkeypatch):
    called = {}

    async def fake(update, context, query, page=0):
        called['query'] = query
        called['page'] = page

    monkeypatch.setattr(teacher_menu, 'handle_teacher_search_results', fake)
    q = FakeQuery()
    ctx = _context(user_data={'teacher_search_query': 'Ив'})
    await TeacherCallbackHandler().handle(_update(q), ctx, 'teacher_search_page_2')
    assert called == {'query': 'Ив', 'page': 2}


async def test_selection_old_format(monkeypatch):
    called = {}

    async def fake(update, context, teacher_name, schedule_type='today'):
        called['teacher'] = teacher_name
        called['type'] = schedule_type

    monkeypatch.setattr(teacher_menu, 'handle_teacher_selection', fake)
    q = FakeQuery()
    await TeacherCallbackHandler().handle(_update(q), _context(), 'teacher_tomorrow_Иванов')
    assert called == {'teacher': 'Иванов', 'type': 'tomorrow'}


async def test_selection_sidx_resolves_from_state(monkeypatch):
    called = {}

    async def fake(update, context, teacher_name, schedule_type='today'):
        called['teacher'] = teacher_name

    monkeypatch.setattr(teacher_menu, 'handle_teacher_selection', fake)
    q = FakeQuery()
    st = FakeState(lists={'search_teachers': ['Иванов', 'Петров']})
    ctx = _context(bot_data={'state_service': st})
    await TeacherCallbackHandler().handle(_update(q), ctx, 'teacher_today_sidx_1')
    assert called['teacher'] == 'Петров'


async def test_selection_idx_resolves_from_state(monkeypatch):
    called = {}

    async def fake(update, context, teacher_name, schedule_type='today'):
        called['teacher'] = teacher_name

    monkeypatch.setattr(teacher_menu, 'handle_teacher_selection', fake)
    q = FakeQuery()
    st = FakeState(lists={'teachers': ['Иванов', 'Петров']})
    ctx = _context(bot_data={'state_service': st})
    await TeacherCallbackHandler().handle(_update(q), ctx, 'teacher_today_idx_0')
    assert called == {'teacher': 'Иванов'}


async def test_selection_sidx_stale_refreshes_results(monkeypatch):
    called = {}

    async def fake_results(update, context, query, page=0):
        called['refresh'] = (query, page)

    monkeypatch.setattr(teacher_menu, 'handle_teacher_search_results', fake_results)
    q = FakeQuery()
    st = FakeState(lists={'search_teachers': []}, pages={'search_teachers': 4})
    ctx = _context(bot_data={'state_service': st}, user_data={'teacher_search_query': 'Ив'})
    await TeacherCallbackHandler().handle(_update(q), ctx, 'teacher_today_sidx_9')
    assert called['refresh'] == ('Ив', 4)


async def test_selection_idx_stale_refreshes_all(monkeypatch):
    called = {}

    async def fake_all(update, context, page=0):
        called['refresh'] = page

    monkeypatch.setattr(teacher_menu, 'show_all_teachers', fake_all)
    q = FakeQuery()
    st = FakeState(lists={'teachers': []}, pages={'teachers': 2})
    ctx = _context(bot_data={'state_service': st})
    await TeacherCallbackHandler().handle(_update(q), ctx, 'teacher_today_idx_9')
    assert called['refresh'] == 2


async def test_selection_without_state_service_toast():
    q = FakeQuery()
    await TeacherCallbackHandler().handle(_update(q), _context(), 'teacher_today_sidx_0')
    assert any('Сервис состояния не доступен' in a for a in q.answers)


async def test_selection_short_callback_toast():
    q = FakeQuery()
    await TeacherCallbackHandler().handle(_update(q), _context(), 'teacher_today')
    assert any('Ошибка в данных преподавателя' in a for a in q.answers)


async def test_selection_malformed_index_toast():
    q = FakeQuery()
    st = FakeState(lists={'search_teachers': ['Иванов']})
    ctx = _context(bot_data={'state_service': st})
    await TeacherCallbackHandler().handle(_update(q), ctx, 'teacher_today_sidx_abc')
    assert any('Ошибка в данных' in a for a in q.answers)
