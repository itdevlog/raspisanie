# tests/test_room_callbacks.py
"""Поведенческие тесты RoomCallbackHandler: роутинг, пагинация, выбор кабинета."""
from types import SimpleNamespace

import handlers.rooms.room_schedule as room_schedule
from handlers.callbacks.room_callbacks import RoomCallbackHandler


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
    await RoomCallbackHandler().handle(_update(q), _context(), 'room_pages_info')
    assert any('навигации' in a for a in q.answers)


async def test_unknown_callback_toast():
    q = FakeQuery()
    await RoomCallbackHandler().handle(_update(q), _context(), 'zzz')
    assert any('Неизвестная' in a for a in q.answers)


async def test_show_all_dispatch(monkeypatch):
    called = {}

    async def fake(update, context, page=0):
        called['page'] = page

    monkeypatch.setattr(room_schedule, 'show_all_rooms', fake)
    q = FakeQuery()
    await RoomCallbackHandler().handle(_update(q), _context(), 'room_show_all')
    assert called['page'] == 0


async def test_pagination_dispatch(monkeypatch):
    called = {}

    async def fake(update, context, page=0):
        called['page'] = page

    monkeypatch.setattr(room_schedule, 'show_all_rooms', fake)
    q = FakeQuery()
    await RoomCallbackHandler().handle(_update(q), _context(), 'room_show_all_2')
    assert called['page'] == 2


async def test_pagination_invalid_toast(monkeypatch):
    q = FakeQuery()
    await RoomCallbackHandler().handle(_update(q), _context(), 'room_show_all_x')
    assert any('Ошибка пагинации' in a for a in q.answers)


async def test_search_pagination_without_query_toast(monkeypatch):
    q = FakeQuery()
    await RoomCallbackHandler().handle(_update(q), _context(), 'room_search_page_1')
    assert any('Поисковый запрос не найден' in a for a in q.answers)


async def test_search_pagination_dispatch(monkeypatch):
    called = {}

    async def fake(update, context, query, page=0):
        called['query'] = query
        called['page'] = page

    monkeypatch.setattr(room_schedule, 'handle_room_search_results', fake)
    q = FakeQuery()
    ctx = _context(user_data={'room_search_query': '10'})
    await RoomCallbackHandler().handle(_update(q), ctx, 'room_search_page_1')
    assert called == {'query': '10', 'page': 1}


async def test_selection_old_format(monkeypatch):
    called = {}

    async def fake(update, context, room_name, schedule_type='today'):
        called['room'] = room_name
        called['type'] = schedule_type

    monkeypatch.setattr(room_schedule, 'handle_room_selection', fake)
    q = FakeQuery()
    await RoomCallbackHandler().handle(_update(q), _context(), 'room_today_101')
    assert called == {'room': '101', 'type': 'today'}


async def test_selection_sidx_resolves_from_state(monkeypatch):
    called = {}

    async def fake(update, context, room_name, schedule_type='today'):
        called['room'] = room_name

    monkeypatch.setattr(room_schedule, 'handle_room_selection', fake)
    q = FakeQuery()
    st = FakeState(lists={'search_rooms': ['101', '102']})
    ctx = _context(bot_data={'state_service': st})
    await RoomCallbackHandler().handle(_update(q), ctx, 'room_today_sidx_1')
    assert called['room'] == '102'


async def test_selection_idx_resolves_from_state(monkeypatch):
    called = {}

    async def fake(update, context, room_name, schedule_type='today'):
        called['room'] = room_name

    monkeypatch.setattr(room_schedule, 'handle_room_selection', fake)
    q = FakeQuery()
    st = FakeState(lists={'rooms': ['101', '102']})
    ctx = _context(bot_data={'state_service': st})
    await RoomCallbackHandler().handle(_update(q), ctx, 'room_week_idx_0')
    assert called == {'room': '101'}


async def test_selection_sidx_stale_refreshes_results(monkeypatch):
    called = {}

    async def fake_results(update, context, query, page=0):
        called['refresh'] = (query, page)

    monkeypatch.setattr(room_schedule, 'handle_room_search_results', fake_results)
    q = FakeQuery()
    st = FakeState(lists={'search_rooms': []}, pages={'search_rooms': 3})
    ctx = _context(bot_data={'state_service': st}, user_data={'room_search_query': '10'})
    await RoomCallbackHandler().handle(_update(q), ctx, 'room_today_sidx_9')
    assert called['refresh'] == ('10', 3)


async def test_selection_idx_stale_refreshes_all(monkeypatch):
    called = {}

    async def fake_all(update, context, page=0):
        called['refresh'] = page

    monkeypatch.setattr(room_schedule, 'show_all_rooms', fake_all)
    q = FakeQuery()
    st = FakeState(lists={'rooms': []}, pages={'rooms': 2})
    ctx = _context(bot_data={'state_service': st})
    await RoomCallbackHandler().handle(_update(q), ctx, 'room_today_idx_9')
    assert called['refresh'] == 2


async def test_selection_without_state_service_toast():
    q = FakeQuery()
    await RoomCallbackHandler().handle(_update(q), _context(), 'room_today_sidx_0')
    assert any('Сервис состояния не доступен' in a for a in q.answers)


async def test_selection_short_callback_toast():
    q = FakeQuery()
    await RoomCallbackHandler().handle(_update(q), _context(), 'room_today')
    assert any('Ошибка в данных кабинета' in a for a in q.answers)


async def test_selection_malformed_index_toast():
    q = FakeQuery()
    st = FakeState(lists={'search_rooms': ['101']})
    ctx = _context(bot_data={'state_service': st})
    await RoomCallbackHandler().handle(_update(q), ctx, 'room_today_sidx_abc')
    assert any('Ошибка в данных' in a for a in q.answers)
