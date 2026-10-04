# web/edge_server.py
"""Edge-приложение публичного сайта и раннер (W10).

Edge — отдельный от бота процесс: он не ходит в Telegram/БД, а держит
последний снапшот расписания (`SnapshotStore`) и отдаёт публичный API/статику.
Сборка поверх `create_app` (W8):

- `schools_config` и `schools_data` читаются ЖИВО и берутся из снапшота;
  ingest-эндпоинт (W9) подменяет снапшот в том же процессе, поэтому
  `/api/schools` должен видеть новые данные без перезапуска;
- telegram-маршруты выключены (`/api/me`, `/api/widget` — это origin);
- статика — собранный фронтенд (`frontend/dist`);
- ingest-роутер включается ДО статики `/` (иначе `POST /internal/snapshot`
  перехватил бы `StaticFiles` и вернул 405);
- доверенный прокси — ровно `127.0.0.1` (Caddy); входящий `X-Forwarded-For`
  НЕ доверяется, поэтому IP клиента берётся только из заголовка,
  проставленного локальным Caddy.

`python -m web.edge_server` поднимает uvicorn на `EDGE_HOST:EDGE_PORT`.
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable, Iterator, Mapping
from typing import Any

import uvicorn
from fastapi import FastAPI

from config.config import Config
from services.snapshot_store import SnapshotStore
from web.api import create_app
from web.edge_ingest import create_ingest_router
from web.server import _defer_shutdown_signals

logger = logging.getLogger(__name__)

# Литеральный адрес локального reverse-proxy (Caddy). W8: точное совпадение,
# без CIDR — при другом значении XFF молча игнорируется и лимит схлопывается.
DEFAULT_TRUSTED_PROXY = '127.0.0.1'


class _LiveMapping(Mapping[str, Any]):
    """Только для чтения вид на текущее значение из источника.

    `SnapshotStore.schools_data`/`schools_config` возвращают новый
    `MappingProxyType` на каждый доступ, а `create_app` захватывает переданный
    объект один раз. Чтобы после `store.apply` маршруты видели новые данные,
    отдаём объект, который делегирует чтение источнику при каждом вызове.
    """

    def __init__(self, source: Callable[[], Mapping[str, Any]]) -> None:
        self._source = source

    def __getitem__(self, key: str) -> Any:
        return self._source()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._source())

    def __len__(self) -> int:
        return len(self._source())


class _LiveBotData:
    """`bot_data`-совместимый вид для edge: `schools_data` берётся из store.

    Маршруты `create_app` читают `services['bot_data'].get('schools_data')` на
    каждом запросе; возвращаем живой Mapping, чтобы ingest был виден сразу.
    """

    def __init__(self, store: SnapshotStore) -> None:
        self._store = store

    def get(self, key: str, default: Any = None) -> Any:
        if key == 'schools_data':
            return _LiveMapping(lambda: self._store.schools_data)
        return default


def _built_frontend_dir() -> str:
    """Каталог собранного фронтенда: `<repo>/frontend/dist`."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, 'frontend', 'dist')


def create_edge_app(store: SnapshotStore, *, static_dir: str | None = None,
                    trusted_proxies: tuple[str, ...] = (DEFAULT_TRUSTED_PROXY,)
                    ) -> FastAPI:
    """Собирает FastAPI edge-приложения поверх `create_app` (W8).

    `store` — `SnapshotStore`; `schools_config`/`schools_data` отдаются живыми
    видами, чтобы `store.apply` из ingest был виден маршрутам сразу. Статика по
    умолчанию — `frontend/dist`; ingest-роутер включается до mount `/`.
    """
    services = {
        'bot_data': _LiveBotData(store),
        'schools_config': _LiveMapping(lambda: store.schools_config),
        'config': Config,
    }
    if static_dir is None:
        static_dir = _built_frontend_dir()
    return create_app(
        services,
        static_dir=static_dir,
        enable_telegram_routes=False,
        trusted_proxies=trusted_proxies,
        extra_router=create_ingest_router(store),
    )


async def run_edge_server(config) -> None:
    """Обслуживает edge-сайт (uvicorn) до SIGINT/SIGTERM."""
    store = SnapshotStore(config.SNAPSHOT_PATH, config.SNAPSHOT_MAX_AGE)
    server = uvicorn.Server(uvicorn.Config(
        create_edge_app(store),
        host=config.EDGE_HOST,
        port=config.EDGE_PORT,
        log_level='warning',
        access_log=False,
    ))
    logger.info(f"🌐 Edge-сервер публичного сайта: http://{config.EDGE_HOST}:{config.EDGE_PORT}")
    with _defer_shutdown_signals():
        await server.serve()


def main() -> None:
    logging.basicConfig(level=Config.LOG_LEVEL)
    asyncio.run(run_edge_server(Config))


if __name__ == '__main__':
    main()
