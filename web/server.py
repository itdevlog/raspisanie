# web/server.py
"""Запуск FastAPI в event loop бота (один процесс)."""
import asyncio
import contextlib
import logging
import signal
import threading

import uvicorn

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _defer_shutdown_signals():
    """Не даёт uvicorn-у повторно доставленным сигналом убить процесс до очистки.

    ``uvicorn.Server.capture_signals()`` восстанавливает прежние обработчики и
    затем делает ``signal.raise_signal()`` для полученного сигнала. Для SIGTERM
    прежний обработчик — ``SIG_DFL`` (процесс завершается немедленно, exit 143),
    поэтому наш ``finally``-блок очистки не успевает выполниться. Для SIGINT
    прежний обработчик — ``asyncio.Runner._on_sigint``, который отменяет главную
    задачу на первом же ``await`` в очистке.

    На время ``serve()`` подменяем SIGINT/SIGTERM на benign-обработчик: сигнал
    уже обработан uvicorn-ом (``should_exit``), а повторная доставка становится
    безвредной, после чего управление штатно уходит в ``finally``.
    """
    # Сигналы можно слушать только из главного потока.
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = {
        sig: signal.signal(sig, lambda *_: None)
        for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


async def run_webapp(application, config) -> None:
    """Обслуживает Mini App (uvicorn) до SIGINT/SIGTERM (uvicorn ставит should_exit)."""
    from web.api import create_app

    services = {
        'bot_data': application.bot_data,
        'config': config,
    }
    server = uvicorn.Server(uvicorn.Config(
        create_app(services),
        host=config.WEBAPP_HOST,
        port=config.WEBAPP_PORT,
        log_level='warning',
        access_log=False,
    ))
    logger.info(f"🌐 Веб-сервер Mini App: http://{config.WEBAPP_HOST}:{config.WEBAPP_PORT}")
    with _defer_shutdown_signals():
        await server.serve()


async def wait_forever() -> None:
    """Режим без веб-сервера: ждём сигнала завершения."""
    await asyncio.Event().wait()
