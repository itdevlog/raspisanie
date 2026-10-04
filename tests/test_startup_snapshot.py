# tests/test_startup_snapshot.py
"""W6: регистрация экспортёра снапшота и публикация при старте.

Проверяем четыре требования брифа:
- `setup_services` создаёт `SnapshotExporter` и кладёт его в
  `bot_data['snapshot_exporter']` (ключ читает W5);
- `_post_init` публикует снапшот после первичной загрузки `schools_data`,
  вызывая синхронный `publish` через `asyncio.to_thread`;
- выключенный сервис (`EDGE_INGEST_URL` пуст) логирует info и не публикует;
- ошибка публикации не роняет старт бота.
"""
import asyncio
import logging
import threading
from types import SimpleNamespace
from typing import Any

import bot as bot_module
from bot import ScheduleBot


class _RecordingExporter:
    """Best-effort экспортёр-заглушка: пишет снапшоты и поток вызова."""

    def __init__(self, result: bool = True, error: Exception | None = None,
                 enabled: bool = True):
        self.result = result
        self.error = error
        self.enabled = enabled
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
        self.started = 0

    async def notify_bot_started(self, application) -> None:
        self.started += 1


def _make_post_init_bot(bot_data: dict) -> ScheduleBot:
    b = ScheduleBot.__new__(ScheduleBot)
    b.logger = logging.getLogger('test')
    b.application = SimpleNamespace(  # type: ignore[assignment]
        bot_data=bot_data,
        bot=SimpleNamespace(),
        post_init=None,
    )
    b.config = SimpleNamespace(WEBAPP_URL='')  # type: ignore[assignment]
    b.background_updater = SimpleNamespace(  # type: ignore[assignment]
        start_periodic_updates=lambda: None
    )
    return b


# --- setup_services: регистрация экспортёра ---------------------------------

def test_setup_services_registers_snapshot_exporter(monkeypatch, tmp_path):
    """Экспортёр создаётся по Config и лежит под ключом `snapshot_exporter`."""
    created: list[Any] = []

    class _FakeExporter:
        def __init__(self, config=None, metrics=None):
            created.append((config, metrics))

    monkeypatch.setattr(bot_module, 'SnapshotExporter', _FakeExporter)

    b = ScheduleBot.__new__(ScheduleBot)
    b.logger = logging.getLogger('test')
    b.config = SimpleNamespace(  # type: ignore[assignment]
        DB_PATH=str(tmp_path / 'database.json'),
        WEBAPP_URL='',
        EDGE_INGEST_URL='https://edge.example/ingest',
    )
    b.application = SimpleNamespace(bot_data={})  # type: ignore[assignment]

    b.setup_services()

    assert 'snapshot_exporter' in b.application.bot_data
    assert isinstance(
        b.application.bot_data['snapshot_exporter'], _FakeExporter
    )
    assert created and created[0][0] is b.config  # по Config


# --- _post_init: публикация после загрузки ----------------------------------

def test_post_init_publishes_snapshot_via_to_thread():
    """Снапшот публикуется после загрузки, синхронный publish — в отдельном потоке."""
    schools_data = {'school_133': {'SCHOOL_NAME': 'Школа'}}
    schools_config = {'school_133': {'name': 'Школа'}}
    exporter = _RecordingExporter()
    main_ident = threading.get_ident()
    bot_data = {
        'schools_data': schools_data,
        'schools_config': schools_config,
        'snapshot_exporter': exporter,
    }
    b = _make_post_init_bot(bot_data)

    asyncio.run(b._post_init(b.application))

    assert len(exporter.calls) == 1
    snapshot = exporter.calls[0]
    assert snapshot['version'] == 1
    assert snapshot['schools'] == schools_data
    assert snapshot['schools_config'] == schools_config
    # publish ушёл в рабочий поток (loop не блокируется).
    assert exporter.thread_idents[0] != main_ident


def test_post_init_publishes_even_when_schools_data_empty():
    """Данные пусты — снапшот всё равно собирается и публикуется (без фильтра)."""
    exporter = _RecordingExporter()
    bot_data = {
        'schools_data': {},
        'schools_config': {},
        'snapshot_exporter': exporter,
    }
    b = _make_post_init_bot(bot_data)

    asyncio.run(b._post_init(b.application))

    assert len(exporter.calls) == 1
    assert exporter.calls[0]['schools'] == {}


# --- выключенный сервис ------------------------------------------------------

class _DisabledExporter:
    """Выключенный сервис: `enabled=False`, реальный `publish` логирует info."""

    enabled = False

    def __init__(self) -> None:
        self.calls = 0
        self.logger = logging.getLogger(__name__)

    def publish(self, snapshot: dict[str, Any]) -> bool:
        self.calls += 1
        self.logger.info(
            "Публикация снапшота выключена: EDGE_INGEST_URL не задан"
        )
        return False


def test_disabled_exporter_logs_info_and_does_not_publish(caplog):
    """EDGE_INGEST_URL пуст: info в лог, реальной отправки на edge нет."""
    disabled = _DisabledExporter()
    bot_data = {
        'schools_data': {'s1': {}},
        'schools_config': {},
        'snapshot_exporter': disabled,
    }
    b = _make_post_init_bot(bot_data)

    with caplog.at_level(logging.INFO):
        asyncio.run(b._post_init(b.application))

    assert any(
        'EDGE_INGEST_URL' in rec.message and rec.levelno == logging.INFO
        for rec in caplog.records
    )


# --- ошибка публикации не роняет старт --------------------------------------

def test_post_init_publish_error_does_not_crash_startup(caplog):
    exporter = _RecordingExporter(error=RuntimeError('edge down'))
    bot_data = {
        'schools_data': {'s1': {}},
        'schools_config': {},
        'snapshot_exporter': exporter,
    }
    b = _make_post_init_bot(bot_data)

    with caplog.at_level(logging.ERROR):
        asyncio.run(b._post_init(b.application))  # не должно бросить

    assert len(exporter.calls) == 1
    assert any(rec.levelno == logging.ERROR for rec in caplog.records)


def test_post_init_without_exporter_still_starts():
    """Без экспортёра (нестандартная сборка) старт не падает."""
    b = _make_post_init_bot({'schools_data': {}})
    asyncio.run(b._post_init(b.application))
