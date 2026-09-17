# tests/test_state_service.py
"""Поведенческие тесты UserStateService (кэш временного состояния пользователей)."""
import pytest

from services.cache_service import CacheService
from services.state_service import UserStateService


@pytest.fixture
def svc():
    return UserStateService(CacheService(ttl=300))


def test_missing_list_returns_none(svc):
    assert svc.get_user_list(1, 'teachers') is None


def test_set_get_list(svc):
    svc.set_user_list(1, 'teachers', ['Иванов', 'Петров'])
    assert svc.get_user_list(1, 'teachers') == ['Иванов', 'Петров']


def test_lists_isolated_by_user(svc):
    svc.set_user_list(1, 'teachers', ['A'])
    svc.set_user_list(2, 'teachers', ['B'])
    assert svc.get_user_list(1, 'teachers') == ['A']
    assert svc.get_user_list(2, 'teachers') == ['B']


def test_lists_isolated_by_type(svc):
    svc.set_user_list(1, 'teachers', ['A'])
    svc.set_user_list(1, 'rooms', ['101'])
    assert svc.get_user_list(1, 'teachers') == ['A']
    assert svc.get_user_list(1, 'rooms') == ['101']


def test_empty_list_roundtrip(svc):
    """Пустой список возвращается как есть (не None)."""
    svc.set_user_list(1, 'teachers', [])
    assert svc.get_user_list(1, 'teachers') == []


def test_page_missing_returns_default(svc):
    assert svc.get_user_page(1, 'teachers') == 0
    assert svc.get_user_page(1, 'teachers', default=3) == 3


def test_page_roundtrip(svc):
    svc.set_user_page(1, 'teachers', 2)
    assert svc.get_user_page(1, 'teachers') == 2


def test_page_zero_is_indistinguishable_from_missing(svc):
    """Известный баг: `cache.get(key) or default` — сохранённый 0 неотличим от отсутствия.

    Документируем текущее поведение: установка страницы 0 с непустым default
    возвращает default, а не сохранённый 0. Публичный контракт сохранён (default=0
    для вызывающих скрывает разницу), production-фикс вне рамок U12.
    """
    svc.set_user_page(1, 'teachers', 0)
    assert svc.get_user_page(1, 'teachers', default=5) == 5


def test_ttl_expiry(svc):
    """После истечения TTL список и страница недоступны."""
    short = UserStateService(CacheService(ttl=0))
    short.set_user_list(1, 'teachers', ['A'])
    short.set_user_page(1, 'teachers', 1)
    assert short.get_user_list(1, 'teachers') is None
    assert short.get_user_page(1, 'teachers') == 0


def test_clear_specific_type(svc):
    svc.set_user_list(1, 'teachers', ['A'])
    svc.set_user_page(1, 'teachers', 1)
    svc.set_user_list(1, 'rooms', ['101'])

    svc.clear_user_state(1, 'teachers')

    assert svc.get_user_list(1, 'teachers') is None
    assert svc.get_user_page(1, 'teachers') == 0
    assert svc.get_user_list(1, 'rooms') == ['101']


def test_clear_all_state(svc):
    svc.set_user_list(1, 'teachers', ['A'])
    svc.set_user_list(1, 'rooms', ['101'])
    svc.set_user_list(2, 'teachers', ['B'])

    svc.clear_user_state(1)

    assert svc.get_user_list(1, 'teachers') is None
    assert svc.get_user_list(1, 'rooms') is None
    assert svc.get_user_list(2, 'teachers') == ['B']


def test_teacher_index(svc):
    svc.set_user_list(1, 'teachers', ['Иванов', 'Петров'])
    assert svc.get_teacher_index(1, 'Петров') == 1
    assert svc.get_teacher_index(1, 'Сидоров') is None
    assert svc.get_teacher_index(99, 'Иванов') is None


def test_room_index(svc):
    svc.set_user_list(1, 'rooms', ['101', '102'])
    assert svc.get_room_index(1, '102') == 1
    assert svc.get_room_index(1, '999') is None
