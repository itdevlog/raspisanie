# tests/test_snapshot_e2e.py
"""End-to-end тест контракта origin → edge (W30).

Единственный тест, который прогоняет весь путь публикации целиком, без единого
реального сетевого вызова:

    build_snapshot → serialize_snapshot → SnapshotExporter (HMAC + gzip)
        → MockTransport → real edge app `POST /internal/snapshot`
        → SnapshotStore.apply → отдача расписания edge-приложением

Ключевое решение: транспорт — `httpx.MockTransport`, чей хендлер перекладывает
исходный `httpx.Request` **как есть** (сырое тело + заголовки) в реальный edge
`TestClient`. Так проверяется настоящий контракт: подпись/таймстамп/gzip
формирует production-код экспортёра, а проверяет и применяет их production-код
edge-ингeста. Никакие заголовки/тело не собираются вручную в happy-path, поэтому
рассогласование форматов между origin и edge будет поймано.

Отдельно проверяем пять веток контракта: приём gzip поверх порога, а также
отклонение просроченного timestamp, битой подписи, неподдерживаемой `version`
и тела сверх `SNAPSHOT_MAX_BYTES`. Отказы внутри экспортёра best-effort (он
возвращает `False`, не бросает), поэтому фактический HTTP-статус edge хендлер
запоминает и тесты сверяют и его.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx
from fastapi.testclient import TestClient

import web.edge_ingest as edge_ingest
from services.snapshot import (
    SNAPSHOT_VERSION,
    build_snapshot,
    serialize_snapshot,
)
from services.snapshot_exporter import GZIP_THRESHOLD_BYTES, SnapshotExporter
from services.snapshot_store import SnapshotStore
from web.edge_server import create_edge_app

_SECRET = 'e2e-contract-secret'
_MAX_BYTES = 20 * 1024 * 1024


class _FakeEdgeConfig:
    """Конфиг edge-ингeста для теста: известный секрет и лимит.

    `create_edge_app` собирает ingest-роутер через `Config()` из модуля
    `web.edge_ingest`, поэтому тест подменяет только этот `Config`
    (как в `test_edge_app.py`/`test_edge_ingest.py`).
    """

    EDGE_INGEST_SECRET = _SECRET
    SNAPSHOT_MAX_BYTES = _MAX_BYTES


def _school_data(pad: int = 0) -> dict[str, Any]:
    """Представительные данные школы в формате снапшота (Nikasoft-подобные).

    `pad` раздувает имя школы кириллицей, чтобы перейти порог gzip.
    `CLASS_SCHEDULE['p1']['c1']['101']` — урок 1 в день 1 (понедельник).
    """
    name = 'Школа №1' + ('Ш' * pad if pad else '')
    return {
        'SCHOOL_NAME': name,
        'CLASSES': {'c1': '5а', 'c2': '9б'},
        'TEACHERS': {'t1': 'Иванов', 't2': 'Петрова'},
        'ROOMS': {'r1': '101', 'r2': '202'},
        'SUBJECTS': {'s1': 'Математика', 's2': 'Биология'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['08:55', '09:40']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': [
            'Понедельник', 'Вторник', 'Среда', 'Четверг',
            'Пятница', 'Суббота', 'Воскресенье',
        ],
        'CLASS_SCHEDULE': {
            'p1': {'c1': {
                '101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},
                '102': {'s': ['s2'], 't': ['t2'], 'r': ['r2']},
            }},
        },
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
    }


def _schools_data(pad: int = 0) -> dict[str, Any]:
    """`schools_data` снапшота: карта school_id → данные школы."""
    return {'s1': _school_data(pad)}


def _schools_config(name: str = 'Школа №1') -> dict[str, Any]:
    return {'s1': {'name': name, 'active': True}}


def _store(tmp_path) -> SnapshotStore:
    return SnapshotStore(str(tmp_path / 'snapshot.json'), max_age=7200)


def _edge_app(tmp_path, monkeypatch) -> tuple[TestClient, SnapshotStore]:
    """Собирает реальное edge-приложение с тестовым секретом ingest."""
    monkeypatch.setattr(edge_ingest, 'Config', _FakeEdgeConfig)
    store = _store(tmp_path)
    app = create_edge_app(store, static_dir=str(tmp_path / 'no-static'))
    return TestClient(app), store


class _ForwardingTransport:
    """httpx.MockTransport, перекладывающий запрос в реальное ASGI-приложение.

    Хендлер копирует сырое `content` и все заголовки в `TestClient.post`, то
    есть edge получает ровно то, что отправил `SnapshotExporter`. Фактические
    статусы edge складываются в `statuses` — экспортёр глотает их внутри
    best-effort `publish`, а тестам нужен настоящий код ответа.
    """

    def __init__(self, edge: TestClient) -> None:
        self.edge = edge
        self.statuses: list[int] = []
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        response = self.edge.post(
            request.url.path,
            content=request.content,
            headers=dict(request.headers),
        )
        self.statuses.append(response.status_code)
        return httpx.Response(
            response.status_code,
            content=response.content,
            headers={'content-type': response.headers.get('content-type', '')},
        )


def _exporter(
    transport: _ForwardingTransport,
    *,
    secret: str = _SECRET,
    max_bytes: int = _MAX_BYTES,
    timestamp_fn: Callable[[], float] | None = None,
) -> SnapshotExporter:
    """Настоящий origin-экспортёр поверх фейкового транспорта (реального edge)."""
    config = type('_OriginConfig', (), {
        'EDGE_INGEST_URL': 'http://edge.internal/internal/snapshot',
        'EDGE_INGEST_SECRET': secret,
        'SNAPSHOT_MAX_BYTES': max_bytes,
        'SNAPSHOT_MAX_RETRIES': 1,
    })()
    return SnapshotExporter(
        config=config,
        client=httpx.Client(transport=transport.transport),
        sleep=lambda _seconds: None,
        timestamp_fn=timestamp_fn,
    )


def test_origin_to_edge_happy_path_serves_schedule(tmp_path, monkeypatch):
    """Полный путь: сборка → HMAC → ingest → отдача расписания edge-приложением."""
    edge, store = _edge_app(tmp_path, monkeypatch)
    transport = _ForwardingTransport(edge)
    snapshot = build_snapshot(_schools_data(), _schools_config())

    assert _exporter(transport).publish(snapshot) is True
    assert transport.statuses == [200]

    # ingest реально применил снапшот (in-memory + диск).
    assert dict(store.schools_data) == snapshot['schools']
    assert store.version == SNAPSHOT_VERSION

    # /api/schools отдаёт школу из прошедшего через снапшот конфига.
    schools = edge.get('/api/schools').json()['schools']
    assert schools == [{'id': 's1', 'name': 'Школа №1', 'loaded': True}]

    # Расписание (понедельник 07.09.2026) отдаётся из пришедших данных.
    day = edge.get('/api/s1/schedule/class/5а?date=07.09.2026').json()
    assert day['entity'] == '5а'
    assert day['date'] == '07.09.2026'
    assert [lesson['items'][0]['subject'] for lesson in day['lessons']] == [
        'Математика', 'Биология',
    ]

    # Классы/учителя/кабинеты тоже видны из живого снапшота.
    assert edge.get('/api/s1/classes').json() == {'classes': ['5а', '9б']}
    assert set(edge.get('/api/s1/teachers').json()['teachers']) == {'Иванов', 'Петрова'}


def test_gzip_body_accepted_round_trip(tmp_path, monkeypatch):
    """Тело сверх порога сжимается экспортёром и принимается edge после распаковки."""
    edge, store = _edge_app(tmp_path, monkeypatch)
    transport = _ForwardingTransport(edge)
    data = _schools_data(pad=5000)
    snapshot = build_snapshot(data, _schools_config('Школа №1' + 'Ш' * 5000))

    # Контроль предпосылки: тело реально большое и потому уйдёт gzip'ом.
    assert len(serialize_snapshot(snapshot)) > GZIP_THRESHOLD_BYTES

    # Обёртка транспорта видит заголовок Content-Encoding: gzip на запросе.
    seen: dict[str, str] = {}
    original = transport._handle

    def capture(request: httpx.Request) -> httpx.Response:
        seen['content-encoding'] = request.headers.get('content-encoding', '')
        return original(request)

    transport.transport = httpx.MockTransport(capture)

    assert _exporter(transport).publish(snapshot) is True
    assert seen['content-encoding'] == 'gzip'
    assert transport.statuses == [200]
    assert dict(store.schools_data) == data


def test_stale_timestamp_rejected(tmp_path, monkeypatch):
    """Timestamp старше ±300 с → edge 422, данные НЕ применяются."""
    edge, store = _edge_app(tmp_path, monkeypatch)
    transport = _ForwardingTransport(edge)
    snapshot = build_snapshot(_schools_data(), _schools_config())

    ok = _exporter(transport, timestamp_fn=lambda: time.time() - 301).publish(snapshot)

    assert ok is False
    assert transport.statuses == [422]
    assert dict(store.schools_data) == {}
    assert not (tmp_path / 'snapshot.json').exists()


def test_bad_signature_rejected(tmp_path, monkeypatch):
    """Подпись чужим секретом → edge 401, данные НЕ применяются."""
    edge, store = _edge_app(tmp_path, monkeypatch)
    transport = _ForwardingTransport(edge)
    snapshot = build_snapshot(_schools_data(), _schools_config())

    ok = _exporter(transport, secret='not-the-edge-secret').publish(snapshot)

    assert ok is False
    assert transport.statuses == [401]
    assert dict(store.schools_data) == {}
    assert not (tmp_path / 'snapshot.json').exists()


def test_unsupported_version_rejected(tmp_path, monkeypatch):
    """Чужая `version` → edge 409, данные НЕ применяются."""
    edge, store = _edge_app(tmp_path, monkeypatch)
    transport = _ForwardingTransport(edge)
    snapshot = build_snapshot(_schools_data(), _schools_config())
    snapshot['version'] = SNAPSHOT_VERSION + 1

    ok = _exporter(transport).publish(snapshot)

    assert ok is False
    assert transport.statuses == [409]
    assert dict(store.schools_data) == {}
    assert not (tmp_path / 'snapshot.json').exists()


def test_oversize_body_rejected_413(tmp_path, monkeypatch):
    """Тело сверх `SNAPSHOT_MAX_BYTES` edge → 413, данные НЕ применяются.

    Лимит экспортёра намеренно больше, чтобы тело ушло по проводу и отклонил
    именно edge (проверяем защиту на принимающей стороне).
    """
    monkeypatch.setattr(edge_ingest, 'Config', type('_TinyEdgeConfig', (), {
        'EDGE_INGEST_SECRET': _SECRET,
        'SNAPSHOT_MAX_BYTES': 256,
    }))
    store = _store(tmp_path)
    edge = TestClient(create_edge_app(store, static_dir=str(tmp_path / 'no-static')))
    transport = _ForwardingTransport(edge)
    snapshot = build_snapshot(_schools_data(), _schools_config())

    ok = _exporter(transport, max_bytes=_MAX_BYTES).publish(snapshot)

    assert ok is False
    assert transport.statuses == [413]
    assert dict(store.schools_data) == {}
    assert not (tmp_path / 'snapshot.json').exists()
