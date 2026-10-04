# tests/test_snapshot_store.py
"""Юнит-тесты хранилища снапшота на edge (W3).

Проверяем: загрузку с диска при создании, атомарное применение только
совпадающей версии формата (v1), вычисление возраста/устаревания и
потокобезопасность под `threading.RLock`.
"""
import json
import os
import tempfile
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from services.snapshot import SNAPSHOT_VERSION, build_snapshot, write_snapshot_atomic
from services.snapshot_store import SnapshotStore

_TZ = ZoneInfo('Asia/Yekaterinburg')


def _write(path: str, *, version: int = SNAPSHOT_VERSION, now: datetime | None = None) -> dict:
    snap = build_snapshot({'s1': {'SCHOOL_NAME': 'Школа'}}, {'s1': {'name': 'Школа'}}, now=now)
    snap['version'] = version
    write_snapshot_atomic(path, snap)
    return snap


def test_loads_existing_snapshot_from_disk_at_construction():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        now = datetime(2026, 10, 2, 12, 0, 0, tzinfo=_TZ)
        _write(path, now=now)

        store = SnapshotStore(path, max_age=7200)

        assert store.version == SNAPSHOT_VERSION
        assert store.generated_at == now.isoformat()
        assert store.schools_data == {'s1': {'SCHOOL_NAME': 'Школа'}}
        assert store.schools_config == {'s1': {'name': 'Школа'}}


def test_starts_empty_when_file_missing():
    with tempfile.TemporaryDirectory() as d:
        store = SnapshotStore(os.path.join(d, 'nope.json'), max_age=7200)

        assert store.schools_data == {}
        assert store.schools_config == {}
        assert store.generated_at is None
        assert store.version is None


def test_starts_empty_when_file_corrupt():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('{broken json!!')

        store = SnapshotStore(path, max_age=7200)

        assert store.schools_data == {}
        assert store.version is None


def test_apply_replaces_data_and_persists_to_disk():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        store = SnapshotStore(path, max_age=7200)
        now = datetime(2026, 10, 2, 12, 0, 0, tzinfo=_TZ)
        payload = build_snapshot({'s2': {'SCHOOL_NAME': 'Другая'}}, {'s2': {'name': 'Другая'}}, now=now)

        assert store.apply(payload) is True

        assert store.version == SNAPSHOT_VERSION
        assert store.generated_at == now.isoformat()
        assert store.schools_data == {'s2': {'SCHOOL_NAME': 'Другая'}}
        assert store.schools_config == {'s2': {'name': 'Другая'}}
        # применённое состояние сохранено на диск
        with open(path, encoding='utf-8') as f:
            assert json.load(f)['schools'] == {'s2': {'SCHOOL_NAME': 'Другая'}}


def test_apply_rejects_unsupported_version_without_clobbering():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        _write(path)
        store = SnapshotStore(path, max_age=7200)
        before = (store.schools_data, store.generated_at, store.version)

        payload = build_snapshot({'s9': {'SCHOOL_NAME': 'Чужая'}}, {})
        payload['version'] = SNAPSHOT_VERSION + 1
        assert store.apply(payload) is False

        assert (store.schools_data, store.generated_at, store.version) == before
        # данные на диске тоже не затёрты
        with open(path, encoding='utf-8') as f:
            assert json.load(f)['version'] == SNAPSHOT_VERSION


def test_apply_rejects_missing_version():
    with tempfile.TemporaryDirectory() as d:
        store = SnapshotStore(os.path.join(d, 'snapshot.json'), max_age=7200)

        assert store.apply({'schools': {'s1': {}}, 'schools_config': {}}) is False
        assert store.schools_data == {}


def test_age_seconds_none_without_data():
    with tempfile.TemporaryDirectory() as d:
        store = SnapshotStore(os.path.join(d, 'nope.json'), max_age=7200)
        assert store.age_seconds() is None


def test_age_seconds_uses_generated_at():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        generated = datetime(2026, 10, 2, 12, 0, 0, tzinfo=_TZ)
        _write(path, now=generated)
        store = SnapshotStore(path, max_age=7200)

        now = generated + timedelta(seconds=100)
        assert store.age_seconds(now=now) == 100.0


def test_is_stale_true_without_data():
    with tempfile.TemporaryDirectory() as d:
        store = SnapshotStore(os.path.join(d, 'nope.json'), max_age=7200)
        assert store.is_stale is True


def test_age_seconds_boundary_is_exact():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        generated = datetime(2026, 10, 2, 12, 0, 0, tzinfo=_TZ)
        _write(path, now=generated)
        store = SnapshotStore(path, max_age=100)

        # ровно на границе возраст равен max_age — is_stale=False (строго >)
        assert store.age_seconds(now=generated + timedelta(seconds=100)) == 100.0
        assert store.age_seconds(now=generated + timedelta(seconds=101)) == 101.0


def test_is_stale_fresh_and_stale():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        store = SnapshotStore(path, max_age=100)

        # заведомо свежий (10с при пороге 100с)
        store.apply(build_snapshot(
            {'s1': {}}, {}, now=datetime.now(_TZ) - timedelta(seconds=10)))
        assert store.is_stale is False

        # заведомо устаревший (10000с при пороге 100с)
        store.apply(build_snapshot(
            {'s1': {}}, {}, now=datetime.now(_TZ) - timedelta(seconds=10000)))
        assert store.is_stale is True


def test_apply_is_thread_safe():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        store = SnapshotStore(path, max_age=7200)
        errors: list[BaseException] = []

        def writer(n: int) -> None:
            try:
                payload = build_snapshot({f's{n}': {'SCHOOL_NAME': str(n)}}, {})
                assert store.apply(payload) is True
            except BaseException as e:  # pragma: no cover - только для диагностики
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        # состояние согласовано: одна из записанных школ, ровно одна
        assert len(store.schools_data) == 1
        assert list(store.schools_data)[0] in {f's{n}' for n in range(8)}


def test_schools_data_is_read_only():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        _write(path)
        store = SnapshotStore(path, max_age=7200)

        with pytest.raises(TypeError):
            store.schools_data['new'] = {}  # type: ignore[index]
        with pytest.raises(TypeError):
            store.schools_config['new'] = {}  # type: ignore[index]
        # попытка мутации не изменила состояние
        assert 'new' not in store.schools_data


def test_apply_payload_mutation_does_not_affect_store():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        store = SnapshotStore(path, max_age=7200)
        payload = build_snapshot(
            {'s1': {'SCHOOL_NAME': 'Школа'}}, {'s1': {'name': 'Школа'}})

        assert store.apply(payload) is True
        # ingest мутирует свой payload ПОСЛЕ применения — хранилище не должно это видеть
        payload['schools']['s1']['SCHOOL_NAME'] = 'Подменено'
        payload['schools']['s2'] = {'SCHOOL_NAME': 'Лишняя'}
        payload['schools_config'].clear()

        assert store.schools_data == {'s1': {'SCHOOL_NAME': 'Школа'}}
        assert store.schools_config == {'s1': {'name': 'Школа'}}
