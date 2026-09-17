# tests/test_subscription_ui.py
"""UI-интеграция подписок: разбор callback и переключатель настроек."""
from types import SimpleNamespace
from typing import Any

from handlers.common.entity_menu import EntityConfig, EntityMenuHandler
from handlers.common.settings import unsubscribe_by_callback


class _FakeQuery:
    def __init__(self):
        self.answers = []
        self.edits = []

    async def answer(self, text=None, **kwargs):
        self.answers.append(text)

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)


class _FakeState:
    def __init__(self, store):
        self.store = store

    def get_user_list(self, user_id, key):
        return self.store.get(key)


class _FakeSubscriptions:
    def __init__(self):
        self.subscribed = set()

    def is_subscribed(self, user_id, school_id, kind, name):
        return (user_id, school_id, kind, name) in self.subscribed

    def subscribe(self, user_id, school_id, kind, name):
        self.subscribed.add((user_id, school_id, kind, name))
        return True

    def unsubscribe(self, user_id, school_id, kind, name):
        self.subscribed.discard((user_id, school_id, kind, name))
        return True

    def get_subscriptions(self, user_id, school_id):
        return [(k, n) for (u, s, k, n) in self.subscribed if u == user_id and s == school_id]


def _handler():
    return EntityMenuHandler(EntityConfig(
        entity='teacher',
        label_singular='преподаватель',
        label_plural='преподавателей',
        icon='👨‍🏫',
        menu_title='Поиск',
        search_input_hint='hint',
        search_example='eg',
        empty_data_msg='нет',
        button_truncate=20,
        state_full_key='teachers',
        state_search_key='search_teachers',
        search_query_key='teacher_search_query',
    ))


def _context(subscriptions):
    return SimpleNamespace(
        bot_data={
            'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
            'subscription_service': subscriptions,
            'state_service': _FakeState({'teachers': ['Иванов И.']}),
        },
        user_data={},
    )


async def test_toggle_callback_subscribes_entity(monkeypatch):
    query = _FakeQuery()
    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=query)
    subs = _FakeSubscriptions()
    context = _context(subs)

    handler = _handler()
    redraws = []

    async def _fake_select(update, context, entity_name, schedule_type, **kwargs):
        redraws.append((entity_name, schedule_type))

    monkeypatch.setattr(handler, 'select', _fake_select)

    await handler.handle_subscription_callback(update, context, 'teacher_subscribe_today_idx_0')

    assert ('teacher', 'Иванов И.') in {(k, n) for _, _, k, n in subs.subscribed}
    assert redraws == [('Иванов И.', 'today')]
    assert any('подписались' in (a or '') for a in query.answers)


async def test_toggle_callback_unsubscribes_when_already_subscribed(monkeypatch):
    query = _FakeQuery()
    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=query)
    subs = _FakeSubscriptions()
    subs.subscribed.add((1, 'school_133', 'teacher', 'Иванов И.'))
    context = _context(subs)

    handler = _handler()
    monkeypatch.setattr(handler, 'select', lambda *a, **k: _noop())

    await handler.handle_subscription_callback(update, context, 'teacher_subscribe_today_idx_0')

    assert subs.subscribed == set()
    assert any('отключена' in (a or '') for a in query.answers)


async def test_settings_unsubscribe_removes_subscription():
    query = _FakeQuery()
    update: Any = SimpleNamespace(effective_user=SimpleNamespace(id=1), callback_query=query)

    class _Svc:
        def __init__(self):
            self.removed = []

        def get_subscriptions(self, user_id, school_id):
            return [('room', '101')]

        def unsubscribe(self, user_id, school_id, kind, name):
            self.removed.append((user_id, school_id, kind, name))

    svc = _Svc()
    context: Any = SimpleNamespace(
        bot_data={
            'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
            'subscription_service': svc,
        },
    )

    # settings_handler вызывается после отписки — подменим на пустышку
    import handlers.common.settings as settings_module
    orig = settings_module.settings_handler

    async def _fake_settings(update, context):
        return None

    settings_module.settings_handler = _fake_settings
    try:
        await unsubscribe_by_callback(update, context, 'room_0')
    finally:
        settings_module.settings_handler = orig

    assert svc.removed == [(1, 'school_133', 'room', '101')]
    assert any('Отписка' in (a or '') for a in query.answers)


async def _noop():
    return None
