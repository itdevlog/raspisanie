# tests/test_startup_web_healthz.py
"""Веб-сервер поднимается до завершения первичной загрузки расписания.

Регрессия деплой-сбоя: раньше `ScheduleBot.__init__` синхронно грузил
расписание (`load_schools_data`) до старта event loop, а uvicorn/`/healthz`
поднимался только после этого. При недоступном хосте школы старт занимал
~30 с > `HEALTH_TIMEOUT`, healthcheck падал, и `manage.sh update` откатывал
деплой.

Теперь веб-сервер запускается первым (в отдельной задаче), `/healthz`
отвечает за секунды, а первичная загрузка идёт параллельно и не блокирует
готовность сервиса.
"""
import asyncio
import contextlib
import logging
import threading
from types import SimpleNamespace

import bot as bot_module
from bot import ScheduleBot


class _FakeUpdater:
    async def start_polling(self):
        pass

    async def stop(self):
        pass


class _FakeApplication:
    def __init__(self, bot_data):
        self.bot_data = bot_data
        self.updater = _FakeUpdater()
        self.post_init = None
        self.bot = SimpleNamespace()

    async def initialize(self):
        pass

    async def start(self):
        pass

    async def stop(self):
        pass

    async def shutdown(self):
        pass


def _bare_bot(bot_data, *, webapp_port) -> ScheduleBot:
    b = ScheduleBot.__new__(ScheduleBot)
    b.logger = logging.getLogger('test')
    b.config = SimpleNamespace(WEBAPP_PORT=webapp_port)
    b.application = _FakeApplication(bot_data)
    b.background_updater = SimpleNamespace(
        start_periodic_updates=lambda: None,
        stop=lambda: None,
    )
    b.setup_handlers = lambda: None
    return b


async def _wait_for(event: threading.Event, timeout: float = 5.0) -> bool:
    """Ждёт установки threading.Event, не блокируя event loop."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not event.is_set():
        if loop.time() > deadline:
            return False
        await asyncio.sleep(0.01)
    return True


async def test_web_server_starts_before_initial_load_finishes(monkeypatch):
    """`run_async` поднимает веб до того, как первичная загрузка завершится."""
    web_started = threading.Event()
    load_started = threading.Event()
    load_release = threading.Event()
    load_finished = threading.Event()
    shutdown = threading.Event()

    async def fake_run_webapp(application, config):
        web_started.set()
        # Держим сервер «живым» до конца теста.
        await asyncio.to_thread(shutdown.wait)

    def slow_load(self):
        load_started.set()
        load_release.wait(timeout=5)
        load_finished.set()
        self.application.bot_data['schools_data'] = {}

    monkeypatch.setattr(bot_module, 'run_webapp', fake_run_webapp)

    b = _bare_bot({'snapshot_exporter': None}, webapp_port=8000)
    b.load_schools_data = lambda: slow_load(b)

    task = asyncio.ensure_future(b.run_async())
    try:
        assert await _wait_for(web_started), 'веб-сервер не поднялся'
        # Загрузка должна уже идти параллельно, но ещё не завершиться —
        # значит /healthz успел ответить до готовности данных.
        assert await _wait_for(load_started), 'первичная загрузка не запустилась'
        assert not load_finished.is_set(), 'веб не должен ждать загрузку'
    finally:
        load_release.set()
        shutdown.set()
        try:
            await asyncio.wait_for(task, timeout=5)
        except asyncio.TimeoutError:  # pragma: no cover - защита от зависания
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def test_load_runs_without_web_server(monkeypatch):
    """Без WEBAPP_PORT загрузка всё равно выполняется, затем wait_forever."""
    load_started = threading.Event()
    waiter_started = threading.Event()
    shutdown = threading.Event()

    async def fake_wait_forever():
        waiter_started.set()
        await asyncio.to_thread(shutdown.wait)

    def slow_load(self):
        load_started.set()
        self.application.bot_data['schools_data'] = {'school_1': {}}

    monkeypatch.setattr(bot_module, 'wait_forever', fake_wait_forever)

    b = _bare_bot({'snapshot_exporter': None}, webapp_port=0)
    b.load_schools_data = lambda: slow_load(b)

    task = asyncio.ensure_future(b.run_async())
    try:
        assert await _wait_for(waiter_started), 'wait_forever не запустился'
        assert await _wait_for(load_started), 'первичная загрузка не запустилась'
    finally:
        shutdown.set()
        try:
            await asyncio.wait_for(task, timeout=5)
        except asyncio.TimeoutError:  # pragma: no cover - защита от зависания
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
