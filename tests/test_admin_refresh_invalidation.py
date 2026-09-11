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
