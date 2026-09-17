# tests/test_web_server.py
"""Тесты web/server.py: отложенные сигналы и wait_forever (без запуска uvicorn)."""
import asyncio
import signal
import threading
from typing import Any

import pytest

from web import server


def test_defer_shutdown_signals_restores_main_thread():
    prev_int = signal.getsignal(signal.SIGINT)
    prev_term = signal.getsignal(signal.SIGTERM)

    with server._defer_shutdown_signals():
        assert signal.getsignal(signal.SIGINT) is not prev_int
        assert signal.getsignal(signal.SIGTERM) is not prev_term
        # Сигнал уже обработан uvicorn-ом; повторная доставка безвредна.
        signal.raise_signal(signal.SIGINT)

    assert signal.getsignal(signal.SIGINT) is prev_int
    assert signal.getsignal(signal.SIGTERM) is prev_term


def test_defer_shutdown_signals_restores_on_exception():
    prev = signal.getsignal(signal.SIGINT)

    with pytest.raises(RuntimeError):
        with server._defer_shutdown_signals():
            raise RuntimeError('boom')

    assert signal.getsignal(signal.SIGINT) is prev


def test_defer_shutdown_signals_non_main_thread_noop():
    observed = {}

    def run():
        prev = signal.getsignal(signal.SIGTERM)
        with server._defer_shutdown_signals():
            observed['same'] = signal.getsignal(signal.SIGTERM) is prev
        observed['restored'] = signal.getsignal(signal.SIGTERM) is prev

    t = threading.Thread(target=run)
    t.start()
    t.join()

    assert observed == {'same': True, 'restored': True}


async def test_wait_forever_cancelled():
    task = asyncio.ensure_future(server.wait_forever())
    await asyncio.sleep(0)
    assert not task.done()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


async def test_run_webapp_wires_server(monkeypatch):
    """run_webapp строит uvicorn.Server из create_app(services) и вызывает serve()."""
    seen: dict[str, Any] = {'served': 0, 'config': None, 'services': None}

    def fake_create_app(services):
        seen['services'] = services
        return 'app-object'

    monkeypatch.setattr('web.api.create_app', fake_create_app)

    class FakeUvicornServer:
        def __init__(self, config):
            seen['config'] = config

        async def serve(self):
            seen['served'] += 1

    monkeypatch.setattr(server.uvicorn, 'Server', FakeUvicornServer)

    class FakeUvicornConfig:
        def __init__(self, app, **kwargs):
            self.app = app
            self.kwargs = kwargs

    monkeypatch.setattr(server.uvicorn, 'Config', FakeUvicornConfig)

    class FakeApplication:
        bot_data = {'user_service': 'u'}

    class FakeConfig:
        WEBAPP_HOST = '127.0.0.1'
        WEBAPP_PORT = 8080

    await server.run_webapp(FakeApplication(), FakeConfig())

    assert seen['served'] == 1
    assert seen['config'].app == 'app-object'
    assert seen['config'].kwargs['host'] == '127.0.0.1'
    assert seen['config'].kwargs['port'] == 8080
    assert seen['services']['bot_data'] == {'user_service': 'u'}
    assert isinstance(seen['services']['config'], FakeConfig)
