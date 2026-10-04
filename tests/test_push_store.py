# tests/test_push_store.py
"""Юнит-тесты хранилища Web Push-подписок `PushSubscriptionStore` (W12).

Проверяем поведение поверх реального `FileDB` во временном файле: upsert
по уникальному `endpoint` (без дублей), удаление по endpoint, выборку по
паре school/kind/name, зачистку «мёртвых» endpoints и устаревших записей,
запись `created_at` и полный набор валидаций входных данных.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from database.file_db import FileDB
from services.push_store import PushSubscriptionStore

_TZ = ZoneInfo('Asia/Yekaterinburg')

_ENDPOINT = 'https://fcm.googleapis.com/fcm/send/abc123'
_ENDPOINT_2 = 'https://fcm.googleapis.com/fcm/send/def456'
_KEYS = {'p256dh': 'public-key', 'auth': 'auth-secret'}


@pytest.fixture
def store(tmp_path) -> PushSubscriptionStore:
    db = FileDB(str(tmp_path / 'push.json'))
    return PushSubscriptionStore(db)


def _sub(endpoint: str = _ENDPOINT, **overrides) -> dict:
    data = {
        'endpoint': endpoint,
        'keys': dict(_KEYS),
        'school_id': 'school_133',
        'kind': 'class',
        'name': '5А',
    }
    data.update(overrides)
    return data


def test_upsert_inserts_once(store):
    assert store.upsert(**_sub()) is True

    docs = store.collection.find()
    assert len(docs) == 1
    assert docs[0]['endpoint'] == _ENDPOINT
    assert docs[0]['keys'] == _KEYS


def test_upsert_update_same_document_no_duplicates(store):
    store.upsert(**_sub(name='5А'))
    store.upsert(**_sub(name='6Б'))

    docs = store.collection.find()
    assert len(docs) == 1
    assert docs[0]['name'] == '6Б'


def test_upsert_refreshes_keys_for_same_endpoint(store):
    store.upsert(**_sub(keys={'p256dh': 'old', 'auth': 'old'}))
    store.upsert(**_sub(keys={'p256dh': 'new', 'auth': 'new'}))

    docs = store.collection.find()
    assert len(docs) == 1
    assert docs[0]['keys'] == {'p256dh': 'new', 'auth': 'new'}


def test_upsert_records_created_at(store):
    assert store.upsert(**_sub()) is True

    created = store.collection.find_one({'endpoint': _ENDPOINT})['created_at']
    assert created is not None
    parsed = datetime.fromisoformat(created)
    assert parsed.tzinfo is not None


def test_remove_by_endpoint(store):
    store.upsert(**_sub(_ENDPOINT))
    store.upsert(**_sub(_ENDPOINT_2))

    assert store.remove_by_endpoint(_ENDPOINT) is True

    remaining = store.collection.find()
    assert [d['endpoint'] for d in remaining] == [_ENDPOINT_2]


def test_remove_by_endpoint_missing_returns_false(store):
    assert store.remove_by_endpoint(_ENDPOINT) is False


def test_find_matching_filters_by_all_three_fields(store):
    store.upsert(**_sub(_ENDPOINT, school_id='school_133', kind='class', name='5А'))
    store.upsert(**_sub(_ENDPOINT_2, school_id='school_134', kind='class', name='5А'))
    store.upsert(**_sub(
        'https://fcm.googleapis.com/fcm/send/ghi789',
        school_id='school_133', kind='teacher', name='5А'))

    result = store.find_matching('school_133', 'class', '5А')

    assert [d['endpoint'] for d in result] == [_ENDPOINT]


def test_find_matching_no_match_returns_empty(store):
    store.upsert(**_sub())
    assert store.find_matching('school_999', 'class', '5А') == []


def test_remove_dead_removes_only_listed(store):
    store.upsert(**_sub(_ENDPOINT))
    store.upsert(**_sub(_ENDPOINT_2))

    store.remove_dead([_ENDPOINT])

    remaining = store.collection.find()
    assert [d['endpoint'] for d in remaining] == [_ENDPOINT_2]


def test_remove_dead_ignores_unknown(store):
    store.upsert(**_sub(_ENDPOINT))
    store.remove_dead([_ENDPOINT, 'https://fcm.googleapis.com/fcm/send/unknown'])
    assert store.collection.find() == []


def test_cleanup_stale_removes_only_older_than(store):
    old = (datetime.now(_TZ) - timedelta(days=10)).isoformat()
    fresh = datetime.now(_TZ).isoformat()
    store.upsert(**_sub(_ENDPOINT))
    store.upsert(**_sub(_ENDPOINT_2))
    # `created_at` пишется самим upsert; для теста зачистки подменяем его напрямую.
    store.collection.update_one({'endpoint': _ENDPOINT}, {'created_at': old})
    store.collection.update_one({'endpoint': _ENDPOINT_2}, {'created_at': fresh})

    removed = store.cleanup_stale(datetime.now(_TZ) - timedelta(days=5))

    assert removed == 1
    assert [d['endpoint'] for d in store.collection.find()] == [_ENDPOINT_2]


def test_cleanup_stale_keeps_equal_boundary(store):
    boundary = datetime.now(_TZ)
    store.upsert(**_sub(_ENDPOINT))
    store.collection.update_one(
        {'endpoint': _ENDPOINT}, {'created_at': boundary.isoformat()})

    assert store.cleanup_stale(boundary) == 0
    assert len(store.collection.find()) == 1


@pytest.mark.parametrize('endpoint', [
    'http://fcm.googleapis.com/fcm/send/abc',        # не https
    'ftp://example.com/x',                            # не https
    'fcm.googleapis.com/fcm/send/abc',                # без схемы
    'https://' + 'a' * 5000,                          # слишком длинный
    '',                                               # пустой
])
def test_upsert_rejects_bad_endpoint(store, endpoint):
    assert store.upsert(**_sub(endpoint)) is False
    assert store.collection.find() == []


@pytest.mark.parametrize('keys', [
    {},                                              # нет полей
    {'p256dh': 'x'},                                 # нет auth
    {'auth': 'y'},                                   # нет p256dh
    {'p256dh': '', 'auth': 'y'},                     # пустой p256dh
    {'p256dh': 'x', 'auth': ''},                     # пустой auth
    None,                                            # нет keys
])
def test_upsert_rejects_bad_keys(store, keys):
    assert store.upsert(**_sub(keys=keys)) is False
    assert store.collection.find() == []


@pytest.mark.parametrize('kind', ['bogus', '', None, 'Class'])
def test_upsert_rejects_bad_kind(store, kind):
    assert store.upsert(**_sub(kind=kind)) is False
    assert store.collection.find() == []


@pytest.mark.parametrize('kind', ['class', 'teacher', 'room'])
def test_upsert_accepts_all_valid_kinds(store, kind):
    assert store.upsert(**_sub(endpoint=_ENDPOINT + kind, kind=kind)) is True
