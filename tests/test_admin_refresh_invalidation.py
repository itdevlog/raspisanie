"""Регрессия: ручной refresh вызывает _on_data_replaced() и публикует снапшот (W7)."""
import threading
from types import SimpleNamespace
from typing import Any

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


class _RecordingExporter:
    """Best-effort экспортёр-заглушка: пишет снапшоты и id потока вызова."""

    def __init__(self, result: bool = True, error: Exception | None = None):
        self.result = result
        self.error = error
        self.enabled = True
        self.calls: list[dict] = []
        self.thread_idents: list[int] = []

    def publish(self, snapshot: dict) -> bool:
        self.calls.append(snapshot)
        self.thread_idents.append(threading.get_ident())
        if self.error is not None:
            raise self.error
        return self.result


async def test_refresh_school_invalidates(monkeypatch):
    called = {'n': 0}
    updater = SimpleNamespace(_on_data_replaced=lambda: called.__setitem__('n', called['n'] + 1))
    monkeypatch.setattr(ac, 'DataLoader', lambda: _Loader())

    h = ac.AdminCallbackHandler()
    query = _Query()
    update: Any = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=1),
    )
    context: Any = SimpleNamespace(
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
    update: Any = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=None,
    )
    context: Any = SimpleNamespace(
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
    update: Any = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=None,
    )
    context: Any = SimpleNamespace(
        bot_data={'background_updater': updater, 'config': SimpleNamespace(ADMIN_IDS=[1])},
        bot=SimpleNamespace(),
    )

    async def _show(u, c, text=None, **k):
        messages.append(text)

    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._force_update(update, context)
    assert "⏳ Обновление уже выполняется" in messages[-1]


def _refresh_all_context(exporter):
    updater = SimpleNamespace(_on_data_replaced=lambda: None)
    return SimpleNamespace(
        bot_data={
            'background_updater': updater,
            'schools_data': {'school_133': {'CLASSES': {}}},
            'schools_config': {'school_133': {'name': 'Школа'}},
            'snapshot_exporter': exporter,
            'config': SimpleNamespace(ADMIN_IDS=[1]),
        },
        bot=SimpleNamespace(),
    )


async def test_refresh_all_publishes_snapshot(monkeypatch):
    """Успешный admin-refresh всех школ публикует снапшот (W7)."""
    monkeypatch.setattr(ac, 'DataLoader', lambda: _Loader())
    exporter = _RecordingExporter()

    h = ac.AdminCallbackHandler()
    query = _Query()
    update: Any = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=None,
    )
    context = _refresh_all_context(exporter)

    async def _show(*a, **k):
        pass

    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._refresh_all_schools(update, context)

    assert len(exporter.calls) == 1
    snapshot = exporter.calls[0]
    assert snapshot['version'] == 1
    # Свежий schools_data/schools_config — из bot_data.
    assert snapshot['schools'] == context.bot_data['schools_data']
    assert snapshot['schools_config'] == {'school_133': {'name': 'Школа'}}
    # Синхронный publish уходит в worker-поток, loop не блокируется.
    assert exporter.thread_idents[0] != threading.get_ident()


async def test_refresh_school_publishes_snapshot(monkeypatch):
    """Успешный admin-refresh одной школы тоже публикует снапшот (W7)."""
    monkeypatch.setattr(ac, 'DataLoader', lambda: _Loader())
    exporter = _RecordingExporter()

    h = ac.AdminCallbackHandler()
    query = _Query()
    update: Any = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=None,
    )
    context = _refresh_all_context(exporter)

    async def _show(*a, **k):
        pass

    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._refresh_school(update, context, 'school_133')

    assert len(exporter.calls) == 1
    assert exporter.calls[0]['schools']['school_133'] == {'CLASSES': {}}
    assert exporter.thread_idents[0] != threading.get_ident()


async def test_refresh_all_without_exporter_is_safe(monkeypatch):
    """Без экспортёра в bot_data refresh работает как раньше, без ошибок."""
    monkeypatch.setattr(ac, 'DataLoader', lambda: _Loader())

    h = ac.AdminCallbackHandler()
    query = _Query()
    update: Any = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=None,
    )
    context = _refresh_all_context(None)
    context.bot_data['snapshot_exporter'] = None

    async def _show(*a, **k):
        pass

    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._refresh_all_schools(update, context)
    assert context.bot_data['schools_data']['school_133'] == {'CLASSES': {}}


async def test_refresh_all_disabled_exporter_is_safe(monkeypatch):
    """Выключенный экспортёр (нет EDGE_INGEST_URL) не ломает refresh."""
    monkeypatch.setattr(ac, 'DataLoader', lambda: _Loader())
    exporter = _RecordingExporter(result=False)
    exporter.enabled = False

    h = ac.AdminCallbackHandler()
    query = _Query()
    update: Any = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=None,
    )
    context = _refresh_all_context(exporter)

    async def _show(*a, **k):
        pass

    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._refresh_all_schools(update, context)
    assert context.bot_data['schools_data']['school_133'] == {'CLASSES': {}}


async def test_refresh_all_publish_error_does_not_break(monkeypatch):
    """Ошибка publish не всплывает и не отменяет успешный refresh."""
    monkeypatch.setattr(ac, 'DataLoader', lambda: _Loader())
    exporter = _RecordingExporter(error=RuntimeError('edge down'))

    h = ac.AdminCallbackHandler()
    query = _Query()
    update: Any = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=None,
    )
    context = _refresh_all_context(exporter)

    async def _show(*a, **k):
        pass

    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._refresh_all_schools(update, context)

    assert len(exporter.calls) == 1  # публикация реально вызывалась
    assert context.bot_data['schools_data']['school_133'] == {'CLASSES': {}}


async def test_force_update_does_not_publish_itself(monkeypatch):
    """_force_update не публикует сам: это покрывает W5 в _perform_update."""
    exporter = _RecordingExporter()

    async def _performed():
        return True

    updater = SimpleNamespace(
        _perform_update=_performed,
        _on_data_replaced=lambda: None,
    )
    h = ac.AdminCallbackHandler()
    query = _Query()
    update: Any = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=None,
    )
    context: Any = SimpleNamespace(
        bot_data={
            'background_updater': updater,
            'schools_data': {},
            'schools_config': {},
            'snapshot_exporter': exporter,
            'config': SimpleNamespace(ADMIN_IDS=[1]),
        },
        bot=SimpleNamespace(),
    )

    async def _show(*a, **k):
        pass

    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._force_update(update, context)

    assert exporter.calls == []
