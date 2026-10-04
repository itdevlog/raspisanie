# services/snapshot_exporter.py
"""Публикация снапшота расписания на edge (W4).

Origin после обновления данных POST-ит подписанный снапшот на
`EDGE_INGEST_URL`. Контракт (см. спеку, §3):

- тело — `serialize_snapshot(snapshot)` (компактный UTF-8 JSON);
- заголовок `X-Snapshot-Signature` — HMAC-SHA256 **сырого** тела, hex;
- заголовок `X-Snapshot-Timestamp` — unix seconds (на edge проверяется ±300 с);
- тело сверх `SNAPSHOT_MAX_BYTES` не публикуется (защита от гигантов);
- большие тела сжимаются gzip, `Content-Encoding: gzip` (edge декомпрессирует;
  подпись при этом считается до сжатия — edge сначала распаковывает);
- ретраи с экспоненциальным backoff (`SNAPSHOT_MAX_RETRIES`), таймаут.

Публикация best-effort: сбой логируется в счётчики/лог, но не бросается —
цикл обновления origin не должен падать из-за edge. `publish` возвращает
`bool`, а метрики `snapshot_published`/`snapshot_publish_errors` копятся в
переданном `MetricsService` (или не считаются, если он не передан).
"""
from __future__ import annotations

import gzip
import logging
import time
from typing import Any, Callable

import httpx

from config.config import Config
from services.metrics import MetricsService
from services.snapshot import serialize_snapshot, sign_payload

logger = logging.getLogger(__name__)

# Сжимать только «большие» тела: у мелких gzip-заголовок и CPU того не стоят.
GZIP_THRESHOLD_BYTES = 1024

# Таймаут одной попытки публикации. Снапшот — холст до 20 МиБ, поэтому с запасом.
PUBLISH_TIMEOUT_SECONDS = 30.0

# База экспоненциального backoff между попытками (1, 2, 4, ... секунд).
BACKOFF_BASE_SECONDS = 1.0


class SnapshotExporter:
    """Best-effort publisher снапшота на edge через `httpx.Client`."""

    def __init__(
        self,
        config: Any | None = None,
        client: httpx.Client | None = None,
        metrics: MetricsService | None = None,
        sleep: Callable[[float], None] | None = None,
        timestamp_fn: Callable[[], float] | None = None,
    ) -> None:
        cfg = config if config is not None else Config()
        self.url: str = cfg.EDGE_INGEST_URL
        self.secret: str = cfg.EDGE_INGEST_SECRET
        self.max_bytes: int = cfg.SNAPSHOT_MAX_BYTES
        self.max_retries: int = cfg.SNAPSHOT_MAX_RETRIES
        self.metrics = metrics
        self.logger = logging.getLogger(__name__)
        # Инъектируемые для тестов: клиент, пауза между попытками, время.
        self._client = client if client is not None else httpx.Client()
        self._owns_client = client is None
        self._sleep = sleep if sleep is not None else time.sleep
        self._timestamp_fn = timestamp_fn if timestamp_fn is not None else time.time

    def close(self) -> None:
        """Закрывает собственный httpx.Client (внедрённый не трогает)."""
        if self._owns_client:
            try:
                self._client.close()
            except Exception as e:  # noqa: BLE001 - best-effort, как у DataLoader
                self.logger.warning("Не удалось закрыть HTTP-клиент экспортёра: %s", e)

    @property
    def enabled(self) -> bool:
        """Публикация включена, только если задан `EDGE_INGEST_URL`."""
        return bool(self.url)

    def publish(self, snapshot: dict[str, Any]) -> bool:
        """Публикует снапшот на edge. Возвращает `True` при успехе, иначе `False`.

        Никогда не бросает: любые ошибки (сеть, HTTP-статус, неожиданный сбой)
        логируются, считается `snapshot_publish_errors` и возвращается `False`.
        """
        if not self.enabled:
            self.logger.info("Публикация снапшота выключена: EDGE_INGEST_URL не задан")
            return False

        body = serialize_snapshot(snapshot)
        if len(body) > self.max_bytes:
            self.logger.error(
                "Снапшот не опубликован: %d байт превышает SNAPSHOT_MAX_BYTES=%d",
                len(body), self.max_bytes,
            )
            self._incr_metric('snapshot_publish_errors')
            return False

        try:
            return self._send(body)
        except Exception as e:  # noqa: BLE001 - best-effort: наружу ничего не уходит
            self.logger.error("Неожиданный сбой публикации снапшота: %s", e)
            self._incr_metric('snapshot_publish_errors')
            return False

    def _send(self, body: bytes) -> bool:
        """Отправляет тело с ретраями/backoff. Подпись — от несжатого `body`."""
        payload, headers = self._build_request(body)
        attempts = max(1, self.max_retries)
        for attempt in range(attempts):
            try:
                response = self._client.post(
                    self.url,
                    content=payload,
                    headers=headers,
                    timeout=PUBLISH_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
            except Exception as e:  # noqa: BLE001 - best-effort: сбой не должен всплывать
                self.logger.warning(
                    "Попытка публикации снапшота %d/%d не удалась: %s",
                    attempt + 1, attempts, e,
                )
                if attempt < attempts - 1:
                    self._sleep(BACKOFF_BASE_SECONDS * (2 ** attempt))
                continue

            self.logger.info("Снапшот опубликован на edge (%d байт)", len(body))
            self._incr_metric('snapshot_published')
            return True

        self.logger.error("Снапшот не опубликован после %d попыток", attempts)
        self._incr_metric('snapshot_publish_errors')
        return False

    def _build_request(self, body: bytes) -> tuple[bytes, dict[str, str]]:
        """Собирает тело и заголовки: gzip для больших, подпись — по сырому телу."""
        if len(body) >= GZIP_THRESHOLD_BYTES:
            payload = gzip.compress(body)
            encoded = 'gzip'
        else:
            payload = body
            encoded = ''
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'X-Snapshot-Signature': sign_payload(self.secret, body),
            'X-Snapshot-Timestamp': str(int(self._timestamp_fn())),
        }
        if encoded:
            headers['Content-Encoding'] = encoded
        return payload, headers

    def _incr_metric(self, name: str) -> None:
        if self.metrics is not None:
            self.metrics.incr(name)
