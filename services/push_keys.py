# services/push_keys.py
"""Генерация VAPID-пары для Web Push (W14).

Печатает свежую пару ключей в формате, который ожидает ``pywebpush``
(и стандарт Web Push VAPID):

- **публичный ключ** — несжатая точка P-256 (65 байт, префикс ``0x04``),
  закодированная base64url **без** padding (`-`/`_`);
- **приватный ключ** — сырой 32-байтовый скаляр P-256 в base64url без padding.

Запуск как CLI::

    python -m services.push_keys

Модуль только печатает готовые строки ``VAPID_PUBLIC_KEY=...`` /
``VAPID_PRIVATE_KEY=...`` и подсказывает записать их в ``.env`` — сам файл
не изменяет. Приватный ключ нигде больше не логируется.
"""
from __future__ import annotations

import base64
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

# P-256 (prime256v1 / secp256r1) — кривая, требуемая Web Push VAPID.
_VAPID_CURVE = ec.SECP256R1()


def _b64url_encode(data: bytes) -> str:
    """base64url без padding (`-`/`_`; ни `+`, ни `/`, ни `=`)."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def generate_vapid_keys() -> tuple[str, str]:
    """Возвращает пару ``(public_key, private_key)`` в base64url.

    Публичный — несжатая точка P-256 (65 байт, ``0x04`` + X + Y),
    приватный — сырой 32-байтовый скаляр. Оба без padding — формат,
    ожидаемый ``pywebpush``.
    """
    private_key = ec.generate_private_key(_VAPID_CURVE)
    public_point = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    private_scalar = private_key.private_numbers().private_value.to_bytes(
        32, 'big')

    return _b64url_encode(public_point), _b64url_encode(private_scalar)


def main() -> None:
    """CLI: печатает VAPID-пару и безопасную инструкцию по ``.env``."""
    public_key, private_key = generate_vapid_keys()

    print('VAPID-пара сгенерирована. Добавьте строки в ваш .env:')
    print()
    print(f'VAPID_PUBLIC_KEY={public_key}')
    print(f'VAPID_PRIVATE_KEY={private_key}')
    print()
    print('VAPID_SUBJECT=mailto:admin@example.ru')
    print()
    print('Затем перезапустите бота: ./manage.sh restart')
    print('Приватный ключ никуда не отправляйте и не коммитьте.')


if __name__ == '__main__':
    main()
    sys.exit(0)
