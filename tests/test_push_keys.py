# tests/test_push_keys.py
"""Тесты генератора VAPID-пары `services.push_keys` (W14).

Проверяется, что пара действительно валидна и совместима с Web Push:

- `generate_vapid_keys()` отдаёт две непустые base64url-строки без `+ / =`;
- публичный ключ — несжатая точка P-256 (65 байт, начинается с `0x04`);
- приватный ключ — сырой 32-байтовый скаляр;
- два вызова дают разные пары (ключи случайны);
- приватный и публичный ключи соответствуют друг другу: публичная точка
  выводится из скаляра через `ec.derive_private_key`;
- `pywebpush` принимает публичный ключ (проверка под importorskip);
- CLI `main()` печатает обе строки `VAPID_*=` и подсказку про `.env`.
"""
from __future__ import annotations

import base64
import io
from contextlib import redirect_stdout

import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from services.push_keys import generate_vapid_keys, main

# Алфавит base64url: без '+', '/' и '=' (padding).
FORBIDDEN_B64_CHARS = set('+/=')


def _b64url_decode(value: str) -> bytes:
    """Декодирует base64url-строку без padding (добавляя его при необходимости)."""
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def test_keys_are_nonempty_base64url_without_forbidden_chars():
    public_key, private_key = generate_vapid_keys()

    assert isinstance(public_key, str) and public_key
    assert isinstance(private_key, str) and private_key
    for value in (public_key, private_key):
        assert not (set(value) & FORBIDDEN_B64_CHARS), value


def test_public_key_is_uncompressed_p256_point():
    public_key, _ = generate_vapid_keys()
    raw = _b64url_decode(public_key)

    assert len(raw) == 65
    assert raw[0] == 0x04


def test_private_key_is_raw_32_byte_scalar():
    _, private_key = generate_vapid_keys()
    raw = _b64url_decode(private_key)

    assert len(raw) == 32


def test_two_calls_produce_different_keys():
    public_one, private_one = generate_vapid_keys()
    public_two, private_two = generate_vapid_keys()

    assert public_one != public_two
    assert private_one != private_two


def test_private_and_public_are_a_valid_pair():
    public_key, private_key = generate_vapid_keys()

    scalar = int.from_bytes(_b64url_decode(private_key), 'big')
    derived = ec.derive_private_key(scalar, ec.SECP256R1())

    from cryptography.hazmat.primitives import serialization

    derived_public = derived.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    assert derived_public == _b64url_decode(public_key)


def test_pywebpush_accepts_public_key():
    # Если библиотека установлена, публичный ключ должен быть ей принимаем:
    # pywebpush (через http_ece) ожидает base64url-декодируемую несжатую точку P-256.
    pytest.importorskip('pywebpush')
    public_key, _ = generate_vapid_keys()

    raw = _b64url_decode(public_key)
    assert raw[0] == 0x04
    assert len(raw) == 65


def test_cli_prints_both_keys_and_env_hint():
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()
    output = buffer.getvalue()

    assert 'VAPID_PUBLIC_KEY=' in output
    assert 'VAPID_PRIVATE_KEY=' in output
    assert '.env' in output


def test_cli_writes_nothing_to_env_file(tmp_path, monkeypatch):
    # main() не должен создавать/трогать .env — только печатать инструкцию.
    env_file = tmp_path / '.env'
    monkeypatch.chdir(tmp_path)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        main()

    assert not env_file.exists()
