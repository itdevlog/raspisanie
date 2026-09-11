"""Регрессия: ручной refresh вызывает _on_data_replaced()."""
from types import SimpleNamespace

import handlers.callbacks.admin_callbacks as ac


class _Query:
    def __init__(self):
        self.edits = []

    async def answer(self, *a, **k):
        pass

    async def edit_message_text(self, text, **k):
        self.edits.append(text)


class _Loader:
    def load_school_data(self, cfg, max_retries=None):
        return {'CLASSES': {}}

    def load_all_schools_data(self):
        return {'school_133': {'CLASSES': {}}}


async def test_refresh_school_invalidates(monkeypatch):
    called = {'n': 0}
    updater = SimpleNamespace(_on_data_replaced=lambda: called.__setitem__('n', called['n'] + 1))
    monkeypatch.setattr(ac, 'DataLoader', lambda: _Loader())

    h = ac.AdminCallbackHandler()
    query = _Query()
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=1),
    )
    context = SimpleNamespace(
        bot_data={'background_updater': updater, 'config': SimpleNamespace(ADMIN_IDS=[1])},
        bot=SimpleNamespace(),
    )

    async def _show(*a, **k):
        pass

    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._refresh_school(update, context, 'school_133')
    assert called['n'] == 1


async def test_refresh_all_merges_failed_school(monkeypatch):
    """Ручной refresh всех школ мёржит fresh-данные поверх last-known-good.

    Школа, чья загрузка не удалась, не должна исчезнуть.
    """
    from core.background_updater import BackgroundUpdater

    class _PartialLoader:
        def load_all_schools_data(self):
            return {'school_133': {'CLASSES': {'fresh': True}}}

    monkeypatch.setattr(ac, 'DataLoader', lambda: _PartialLoader())

    replaced = {'n': 0}
    updater = SimpleNamespace(
        _merge_schools_data=BackgroundUpdater._merge_schools_data,
        _on_data_replaced=lambda: replaced.__setitem__('n', replaced['n'] + 1),
    )

    h = ac.AdminCallbackHandler()
    query = _Query()
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=None,
    )
    context = SimpleNamespace(
        bot_data={
            'background_updater': updater,
            'schools_data': {
                'school_133': {'CLASSES': {'old': True}},
                'school_999': {'CLASSES': {'keep': True}},
            },
            'config': SimpleNamespace(ADMIN_IDS=[1]),
        },
        bot=SimpleNamespace(),
    )

    async def _show(*a, **k):
        pass

    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._refresh_all_schools(update, context)

    assert context.bot_data['schools_data']['school_133'] == {'CLASSES': {'fresh': True}}
    assert context.bot_data['schools_data']['school_999'] == {'CLASSES': {'keep': True}}
    assert replaced['n'] == 1


async def test_force_update_reports_skip_when_locked(monkeypatch):
    """_perform_update() == False -> панель сообщает, что обновление уже идёт в фоне."""
    messages = []

    async def _skipped():
        return False

    updater = SimpleNamespace(_perform_update=_skipped)
    h = ac.AdminCallbackHandler()
    query = _Query()
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=None,
    )
    context = SimpleNamespace(
        bot_data={'background_updater': updater, 'config': SimpleNamespace(ADMIN_IDS=[1])},
        bot=SimpleNamespace(),
    )

    async def _show(u, c, text=None, **k):
        messages.append(text)

    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._force_update(update, context)
    assert "⏳ Обновление уже выполняется" in messages[-1]
