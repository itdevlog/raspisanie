# web/server.py
"""Запуск FastAPI в event loop бота (один процесс)."""
import asyncio
import logging

import uvicorn

logger = logging.getLogger(__name__)


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
    await server.serve()


async def wait_forever() -> None:
    """Режим без веб-сервера: ждём сигнала завершения."""
    await asyncio.Event().wait()
