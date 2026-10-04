# tests/test_snapshot_format.py
"""Юнит-тесты формата снапшота (W2): сборка, сериализация, HMAC, атомарная запись."""
import hashlib
import hmac
import json
import logging
import os
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.snapshot import (
    SNAPSHOT_VERSION,
    build_snapshot,
    read_snapshot,
    serialize_snapshot,
    sign_payload,
    verify_signature,
    write_snapshot_atomic,
)

_TZ = ZoneInfo('Asia/Yekaterinburg')


def test_build_snapshot_keys_and_version():
    now = datetime(2026, 10, 2, 12, 0, 0, tzinfo=_TZ)
    snap = build_snapshot({'s1': {'SCHOOL_NAME': 'Школа'}}, {'s1': {'name': 'Школа'}}, now=now)
    assert set(snap.keys()) == {'version', 'generated_at', 'schools', 'schools_config'}
    assert snap['version'] == SNAPSHOT_VERSION == 1
    assert snap['generated_at'] == now.isoformat()
    assert snap['schools'] == {'s1': {'SCHOOL_NAME': 'Школа'}}
    assert snap['schools_config'] == {'s1': {'name': 'Школа'}}


def test_build_snapshot_defaults_now_to_tz_aware():
    snap = build_snapshot({}, {})
    parsed = datetime.fromisoformat(snap['generated_at'])
    assert parsed.tzinfo is not None


def test_serialize_snapshot_is_compact_utf8_and_logs_size(caplog):
    snap = build_snapshot({'s1': {'SCHOOL_NAME': 'Школа'}}, {})
    with caplog.at_level(logging.INFO):
        body = serialize_snapshot(snap)
    assert isinstance(body, bytes)
    # ensure_ascii=False: кириллица кодируется UTF-8, а не \uXXXX
    assert 'Школа'.encode() in body
    assert b'\\u0428' not in body
    # компактно: без пробелов после разделителей
    assert b', ' not in body and b': ' not in body
    assert json.loads(body.decode('utf-8')) == snap
    # размер залогирован
    assert str(len(body)) in caplog.text


def test_sign_payload_is_hmac_sha256_hex():
    body = b'{"version": 1}'
    sig = sign_payload('secret', body)
    assert sig == hmac.new(b'secret', body, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_valid_and_rejects_tampered():
    body = b'{"version": 1}'
    sig = sign_payload('secret', body)
    assert verify_signature('secret', body, sig) is True
    assert verify_signature('secret', body, 'deadbeef') is False
    assert verify_signature('other', body, sig) is False


def test_write_and_read_snapshot_round_trip():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        snap = build_snapshot({'s1': {'SCHOOL_NAME': 'Школа'}}, {'s1': {'name': 'Школа'}})
        write_snapshot_atomic(path, snap)
        assert os.path.exists(path)
        assert read_snapshot(path) == snap
        # временные файлы не остаются
        assert [n for n in os.listdir(d) if n != 'snapshot.json'] == []


def test_write_snapshot_atomic_replaces_previous():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        write_snapshot_atomic(path, build_snapshot({'s1': {}}, {}))
        write_snapshot_atomic(path, build_snapshot({'s2': {}}, {}))
        loaded = read_snapshot(path)
        assert loaded is not None
        assert set(loaded['schools'].keys()) == {'s2'}


def test_read_snapshot_missing_returns_none():
    with tempfile.TemporaryDirectory() as d:
        assert read_snapshot(os.path.join(d, 'nope.json')) is None


def test_read_snapshot_corrupt_returns_none():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('{broken json!!')
        assert read_snapshot(path) is None


def test_write_snapshot_atomic_cleans_tmp_on_failure(monkeypatch):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'snapshot.json')

        def boom(*args, **kwargs):
            raise OSError('replace failed')

        monkeypatch.setattr(os, 'replace', boom)
        with pytest.raises(OSError):
            write_snapshot_atomic(path, build_snapshot({}, {}))
        assert not os.path.exists(path)
        assert [n for n in os.listdir(d) if n.startswith('.snapshot_tmp_')] == []
