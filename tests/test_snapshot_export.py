# tests/test_snapshot_export.py
"""Юнит-тесты публикации снапшота на edge (W4).

Никакой реальной сети: транспорт подменяется фейковым httpx.Client, sleep —
фейковой функцией, время — инъектируемой `timestamp_fn`. Проверяются:
подпись/таймстамп заголовков, лимит размера, gzip больших тел, ретраи с
backoff, best-effort (не бросает) и метрики.
"""
import gzip
import hashlib
import hmac
import logging

import httpx

from services.snapshot import build_snapshot, serialize_snapshot
from services.snapshot_exporter import GZIP_THRESHOLD_BYTES, SnapshotExporter


class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                'err',
                request=httpx.Request('POST', 'https://edge/'),
                response=httpx.Response(self.status_code),
            )


class _RecordingClient:
    """Фейковый httpx.Client: пишет вызовы, отдаёт заданные ответы/ошибки."""

    def __init__(self, responses=None):
        # responses — список: int (статус) | Exception (бросить).
        self.responses = list(responses or [200])
        self.calls: list[dict] = []

    def post(self, url, content=None, headers=None, timeout=None, **kwargs):
        self.calls.append({
            'url': url,
            'content': content,
            'headers': headers,
            'timeout': timeout,
        })
        item = self.responses.pop(0) if self.responses else 200
        if isinstance(item, Exception):
            raise item
        return _FakeResponse(item)


def _config(**overrides):
    """Простой объект-конфиг с полями, которые читает экспортёр."""
    values = {
        'EDGE_INGEST_URL': 'https://edge.example.ru/internal/snapshot',
        'EDGE_INGEST_SECRET': 'topsecret',
        'SNAPSHOT_MAX_BYTES': 20 * 1024 * 1024,
        'SNAPSHOT_MAX_RETRIES': 3,
    }
    values.update(overrides)
    return type('C', (), values)()


def _snapshot(payload_size: int = 0):
    """Снапшот v1; `payload_size` раздувает тело кириллицей при необходимости."""
    filler = 'Ш' * payload_size if payload_size else ''
    return build_snapshot({'s1': {'SCHOOL_NAME': filler}}, {'s1': {'name': 'Школа'}})


def _exporter(client, **overrides):
    sleeps: list[float] = []
    metrics_overrides = overrides.pop('metrics', None)
    now = overrides.pop('now', None)
    exporter = SnapshotExporter(
        config=_config(**overrides),
        client=client,
        metrics=metrics_overrides,
        sleep=sleeps.append,
        timestamp_fn=(lambda: now) if now is not None else None,
    )
    return exporter, sleeps


def test_publish_success_sets_headers_and_signature():
    client = _RecordingClient([200])
    exporter, sleeps = _exporter(client, now=1_700_000_000)
    snapshot = _snapshot()
    body = serialize_snapshot(snapshot)

    assert exporter.publish(snapshot) is True
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call['url'] == 'https://edge.example.ru/internal/snapshot'
    assert call['headers']['X-Snapshot-Timestamp'] == '1700000000'
    # подпись — HMAC-SHA256 именно сырого (несжатого) тела, hex
    expected = hmac.new(b'topsecret', body, hashlib.sha256).hexdigest()
    assert call['headers']['X-Snapshot-Signature'] == expected
    assert call['timeout'] is not None
    assert sleeps == []


def test_publish_sends_raw_body_when_small():
    client = _RecordingClient([200])
    exporter, _ = _exporter(client)
    snapshot = _snapshot()
    body = serialize_snapshot(snapshot)

    assert len(body) <= GZIP_THRESHOLD_BYTES
    assert exporter.publish(snapshot) is True
    call = client.calls[0]
    assert call['content'] == body
    assert 'Content-Encoding' not in call['headers']


def test_publish_gzips_large_body():
    client = _RecordingClient([200])
    exporter, _ = _exporter(client)
    snapshot = _snapshot(payload_size=5000)
    body = serialize_snapshot(snapshot)
    assert len(body) > GZIP_THRESHOLD_BYTES

    assert exporter.publish(snapshot) is True
    call = client.calls[0]
    # тело сжато и декодируется обратно в исходный JSON
    assert gzip.decompress(call['content']) == body
    assert call['headers']['Content-Encoding'] == 'gzip'


def test_publish_signature_is_over_uncompressed_body():
    """Edge проверяет подпись после gzip-декомпрессии — подпись всегда от сырого тела."""
    client = _RecordingClient([200])
    exporter, _ = _exporter(client)
    snapshot = _snapshot(payload_size=5000)
    body = serialize_snapshot(snapshot)

    assert exporter.publish(snapshot) is True
    call = client.calls[0]
    expected = hmac.new(b'topsecret', body, hashlib.sha256).hexdigest()
    assert call['headers']['X-Snapshot-Signature'] == expected


def test_publish_rejects_oversized_body_without_request(caplog):
    client = _RecordingClient([200])
    exporter, _ = _exporter(client, SNAPSHOT_MAX_BYTES=512)
    snapshot = _snapshot(payload_size=5000)

    with caplog.at_level(logging.ERROR, logger='services.snapshot_exporter'):
        assert exporter.publish(snapshot) is False
    assert client.calls == []  # ничего не отправлено
    assert 'SNAPSHOT_MAX_BYTES' in caplog.text


def test_publish_retries_then_succeeds_with_backoff():
    client = _RecordingClient([httpx.ConnectError('boom'), 500, 200])
    exporter, sleeps = _exporter(client, SNAPSHOT_MAX_RETRIES=3)

    assert exporter.publish(_snapshot()) is True
    assert len(client.calls) == 3
    # экспоненциальный backoff: 1, 2 между тремя попытками
    assert sleeps == [1.0, 2.0]


def test_publish_returns_false_after_exhausting_retries():
    client = _RecordingClient([500, 500, 500])
    exporter, sleeps = _exporter(client, SNAPSHOT_MAX_RETRIES=3)

    assert exporter.publish(_snapshot()) is False
    assert len(client.calls) == 3
    assert sleeps == [1.0, 2.0]  # между попытками, не после последней


def test_publish_never_raises_on_unexpected_error():
    class _Exploding:
        def post(self, *args, **kwargs):
            raise RuntimeError('totally unexpected')

    exporter, _ = _exporter(_Exploding())
    assert exporter.publish(_snapshot()) is False


def test_publish_never_raises_when_header_build_fails():
    """Ошибка вне сетевого цикла (например, сломанные часы) тоже не всплывает."""
    class _BrokenClock:
        def __call__(self):
            raise RuntimeError('no clock')

    client = _RecordingClient([200])
    exporter = SnapshotExporter(
        config=_config(),
        client=client,  # type: ignore[arg-type]
        sleep=lambda _s: None,
        timestamp_fn=_BrokenClock(),
    )
    assert exporter.publish(_snapshot()) is False
    assert client.calls == []


def test_publish_records_metrics_on_success_and_failure():
    from services.metrics import MetricsService

    metrics = MetricsService()
    client = _RecordingClient([200])
    exporter, _ = _exporter(client, metrics=metrics)
    assert exporter.publish(_snapshot()) is True
    assert metrics.get('snapshot_published') == 1
    assert metrics.get('snapshot_publish_errors') == 0

    failing, _ = _exporter(_RecordingClient([500, 500, 500]),
                           metrics=metrics, SNAPSHOT_MAX_RETRIES=3)
    assert failing.publish(_snapshot()) is False
    assert metrics.get('snapshot_publish_errors') == 1
    assert metrics.get('snapshot_published') == 1

    # превышение размера — тоже провал публикации (запрос не уходит)
    oversized, _ = _exporter(_RecordingClient([200]), metrics=metrics, SNAPSHOT_MAX_BYTES=512)
    assert oversized.publish(_snapshot(payload_size=5000)) is False
    assert metrics.get('snapshot_publish_errors') == 2
    assert metrics.get('snapshot_published') == 1


def test_publish_disabled_when_url_empty(caplog):
    client = _RecordingClient([200])
    exporter, _ = _exporter(client, EDGE_INGEST_URL='')

    with caplog.at_level(logging.INFO, logger='services.snapshot_exporter'):
        assert exporter.publish(_snapshot()) is False
    assert client.calls == []
    assert 'выключена' in caplog.text
