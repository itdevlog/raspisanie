# tests/test_background_updater_snapshot.py
"""W5: публикация снапшота из фонового цикла обновления.

Проверяем шесть требований брифа:
- publish вызывается, только если свежие `new_schools_data` непусты;
- свежие `schools_data` + `schools_config` берутся из `bot_data`;
- синхронный `publish` уходит в `asyncio.to_thread` (loop не блокируется);
- publish происходит **после** выхода из `_update_lock`;
- ошибка публикации не ломает цикл обновления;
- повторяющиеся сбои алерят через `_alert_repeated_error` (антиспам).
"""
import logging
import threading
from types import SimpleNamespace
from typing import Any

from core.background_updater import BackgroundUpdater
from services.alert_service import AlertService


class _FakeLoader:
    def __init__(self, data):
        self._data = data

    def load_all_schools_data(self):
        return self._data


class _RecordingExporter:
    """Best-effort экспортёр-заглушка: пишет снапшоты и контекст вызова."""

    def __init__(self, result: bool = True, error: Exception | None = None):
        self.result = result
        self.error = error
        self.enabled = True
        self.calls: list[dict] = []
        self.thread_idents: list[int] = []

    def publish(self, snapshot: dict[str, Any]) -> bool:
        self.calls.append(snapshot)
        self.thread_idents.append(threading.get_ident())
        if self.error is not None:
            raise self.error
        return self.result


class _NotificationStub:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def notify_admins(self, context, message, parse_mode='Markdown'):
        self.messages.append(message)


def _make_updater(bot_data=None):
    """Реальный updater с фейковым application; data_loader подменяем в тестах."""
    app = SimpleNamespace(bot_data=dict(bot_data or {}), bot=SimpleNamespace())
    updater = BackgroundUpdater(app)
    updater.logger = logging.getLogger('test')
    return updater, app


def _stub_locked_side_effects(updater):
    """Убирает сеть/админ-рассылку из `_perform_update_locked`."""

    async def _noop(*a, **k):
        return None

    updater._check_exchange_updates = _noop
    updater._get_admin_notification_settings = lambda: {'update_notifications': False}


async def test_publish_called_when_data_non_empty():
    updater, app = _make_updater({'schools_config': {'s1': {'name': 'Школа'}}})
    updater.data_loader = _FakeLoader({'s1': {'SCHOOL_NAME': 'Школа'}})
    _stub_locked_side_effects(updater)
    exporter = _RecordingExporter()
    app.bot_data['snapshot_exporter'] = exporter

    assert await updater._perform_update() is True

    assert len(exporter.calls) == 1
    snapshot = exporter.calls[0]
    assert snapshot['version'] == 1
    # Свежий (смерженный) schools_data и schools_config — из bot_data.
    assert snapshot['schools'] == app.bot_data['schools_data']
    assert snapshot['schools_config'] == {'s1': {'name': 'Школа'}}


async def test_publish_not_called_when_data_empty():
    updater, app = _make_updater({'schools_config': {}})
    updater.data_loader = _FakeLoader({})
    _stub_locked_side_effects(updater)
    exporter = _RecordingExporter()
    app.bot_data['snapshot_exporter'] = exporter

    assert await updater._perform_update() is True

    assert exporter.calls == []


async def test_publish_runs_in_worker_thread_and_after_lock_released():
    updater, app = _make_updater({})
    updater.data_loader = _FakeLoader({'s1': {'v': 1}})
    _stub_locked_side_effects(updater)
    exporter = _RecordingExporter()
    app.bot_data['snapshot_exporter'] = exporter

    lock_state: list[bool] = []

    original_publish = exporter.publish

    def _capture(snapshot):
        # Вызов обязан идти вне критической секции.
        lock_state.append(updater._update_lock.locked())
        return original_publish(snapshot)

    exporter.publish = _capture  # type: ignore[method-assign]

    await updater._perform_update()

    assert exporter.thread_idents[0] != threading.get_ident()  # to_thread
    assert lock_state == [False]  # publish после выхода из _update_lock


async def test_publish_uses_fresh_merged_data_not_stale():
    # last-known-good s2 сохраняется мержем и тоже попадает в снапшот.
    updater, app = _make_updater(
        {'schools_data': {'s1': {'v': 1}, 's2': {'v': 2}}})
    updater.data_loader = _FakeLoader({'s1': {'v': 9}})
    _stub_locked_side_effects(updater)
    exporter = _RecordingExporter()
    app.bot_data['snapshot_exporter'] = exporter

    await updater._perform_update()

    assert exporter.calls[0]['schools'] == {'s1': {'v': 9}, 's2': {'v': 2}}


async def test_publish_error_does_not_break_update_cycle():
    updater, app = _make_updater({})
    updater.data_loader = _FakeLoader({'s1': {'v': 1}})
    _stub_locked_side_effects(updater)
    exporter = _RecordingExporter(error=RuntimeError('edge down'))
    app.bot_data['snapshot_exporter'] = exporter

    # Исключение публикации не всплывает и не отменяет обновление данных.
    assert await updater._perform_update() is True
    assert len(exporter.calls) == 1  # публикация реально вызывалась
    assert app.bot_data['schools_data'] == {'s1': {'v': 1}}


async def test_failed_publish_return_alerts_once_via_antispam():
    alert = AlertService(threshold=3, window_seconds=300, now=lambda: 0.0)
    notifier = _NotificationStub()
    updater, app = _make_updater({'alert_service': alert})
    updater.data_loader = _FakeLoader({'s1': {'v': 1}})
    _stub_locked_side_effects(updater)
    app.bot_data['notification_service'] = notifier
    app.bot_data['snapshot_exporter'] = _RecordingExporter(result=False)

    for _ in range(5):
        assert await updater._perform_update() is True

    assert len(notifier.messages) == 1
    assert 'snapshot_publish' in notifier.messages[0]


async def test_disabled_exporter_failure_does_not_alert():
    alert = AlertService(threshold=3, window_seconds=300, now=lambda: 0.0)
    notifier = _NotificationStub()
    updater, app = _make_updater({'alert_service': alert})
    updater.data_loader = _FakeLoader({'s1': {'v': 1}})
    _stub_locked_side_effects(updater)
    app.bot_data['notification_service'] = notifier
    disabled = _RecordingExporter(result=False)
    disabled.enabled = False  # сервис выключен (EDGE_INGEST_URL пуст) — не сбой
    app.bot_data['snapshot_exporter'] = disabled

    for _ in range(5):
        assert await updater._perform_update() is True

    assert notifier.messages == []


async def test_repeated_publish_errors_alert_once_via_antispam():
    alert = AlertService(threshold=3, window_seconds=300, now=lambda: 0.0)
    notifier = _NotificationStub()
    updater, app = _make_updater({'alert_service': alert})
    updater.data_loader = _FakeLoader({'s1': {'v': 1}})
    _stub_locked_side_effects(updater)
    app.bot_data['notification_service'] = notifier
    app.bot_data['snapshot_exporter'] = _RecordingExporter(error=RuntimeError('edge down'))

    for _ in range(5):
        assert await updater._perform_update() is True

    assert len(notifier.messages) == 1
    assert 'RuntimeError' in notifier.messages[0]
    assert 'snapshot_publish' in notifier.messages[0]


async def test_no_publish_error_when_exporter_absent():
    updater, app = _make_updater({})
    updater.data_loader = _FakeLoader({'s1': {'v': 1}})
    _stub_locked_side_effects(updater)

    # Без экспортёра в bot_data цикл работает как раньше, без ошибок.
    assert await updater._perform_update() is True
