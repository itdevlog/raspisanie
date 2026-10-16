# tests/test_push_test.py
"""Юнит-тесты операторского CLI `services.push_test` (диагностика Web Push).

Никакой реальной сети: проверяются только (а) логика выбора подписок
(`--all` против school/kind/name) на фейковом in-memory хранилище и
(б) понятный отказ при отсутствии VAPID-ключей. Отправка в тестах не
выполняется.
"""
from config.config import Config
from services import push_test


class FakeStore:
    """In-memory заглушка `PushSubscriptionStore` для тестов выбора."""

    def __init__(self, subscriptions=None):
        self._subscriptions = list(subscriptions or [])
        self.removed: list[list[str]] = []

    def list_all(self):
        return list(self._subscriptions)

    def find_matching(self, school_id, kind, name):
        return [
            s for s in self._subscriptions
            if s.get('school_id') == school_id
            and s.get('kind') == kind
            and s.get('name') == name
        ]

    def remove_dead(self, endpoints):
        endpoints = list(endpoints)
        self.removed.append(endpoints)
        return len(endpoints)


def _sub(endpoint, school_id='school_133', kind='class', name='5А'):
    return {
        'endpoint': endpoint,
        'keys': {'p256dh': 'p', 'auth': 'a'},
        'school_id': school_id,
        'kind': kind,
        'name': name,
        'quiet': True,
        'created_at': '2026-10-16T10:00:00+05:00',
    }


SUBS = [
    _sub('https://fcm.googleapis.com/fcm/send/a', 'school_133', 'class', '5А'),
    _sub('https://fcm.googleapis.com/fcm/send/b', 'school_133', 'class', '6Б'),
    _sub('https://fcm.googleapis.com/fcm/send/c', 'school_133', 'teacher', '5А'),
    _sub('https://fcm.googleapis.com/fcm/send/d', 'school_134', 'class', '5А'),
]


# --- выбор подписок ---------------------------------------------------------

def test_select_all_returns_every_subscription():
    store = FakeStore(SUBS)
    result = push_test.select_subscriptions(store, all_=True)
    assert [s['endpoint'] for s in result] == [s['endpoint'] for s in SUBS]


def test_select_by_school_only():
    store = FakeStore(SUBS)
    result = push_test.select_subscriptions(store, school_id='school_133')
    assert {s['endpoint'] for s in result} == {
        'https://fcm.googleapis.com/fcm/send/a',
        'https://fcm.googleapis.com/fcm/send/b',
        'https://fcm.googleapis.com/fcm/send/c',
    }


def test_select_by_school_and_kind():
    store = FakeStore(SUBS)
    result = push_test.select_subscriptions(
        store, school_id='school_133', kind='class')
    assert {s['endpoint'] for s in result} == {
        'https://fcm.googleapis.com/fcm/send/a',
        'https://fcm.googleapis.com/fcm/send/b',
    }


def test_select_by_school_kind_and_name():
    store = FakeStore(SUBS)
    result = push_test.select_subscriptions(
        store, school_id='school_133', kind='class', name='5А')
    assert [s['endpoint'] for s in result] == ['https://fcm.googleapis.com/fcm/send/a']


def test_select_no_match_returns_empty():
    store = FakeStore(SUBS)
    assert push_test.select_subscriptions(
        store, school_id='school_999', kind='class', name='5А') == []


def test_select_all_makes_school_optional():
    store = FakeStore(SUBS)
    assert len(push_test.select_subscriptions(store, all_=True)) == 4


# --- отказ при отсутствии VAPID-ключей --------------------------------------

def test_send_without_vapid_keys_fails_before_touching_store(monkeypatch, capsys):
    monkeypatch.setattr(Config, 'VAPID_PUBLIC_KEY', '')
    monkeypatch.setattr(Config, 'VAPID_PRIVATE_KEY', '')
    touched = {'n': 0}

    def fake_load_store():
        touched['n'] += 1
        return FakeStore(SUBS)

    monkeypatch.setattr(push_test, '_load_store', fake_load_store)

    code = push_test.main(['--send', '--all'])

    assert code == 1
    captured = capsys.readouterr()
    assert 'VAPID_PUBLIC_KEY' in (captured.out + captured.err)
    # Ключей нет — до хранилища и отправки дело не доходит.
    assert touched['n'] == 0


def test_send_with_public_key_only_fails(monkeypatch, capsys):
    monkeypatch.setattr(Config, 'VAPID_PUBLIC_KEY', 'public')
    monkeypatch.setattr(Config, 'VAPID_PRIVATE_KEY', '')
    monkeypatch.setattr(push_test, '_load_store', lambda: FakeStore(SUBS))

    code = push_test.main(['--send', '--all'])

    assert code == 1
    captured = capsys.readouterr()
    assert 'VAPID' in (captured.out + captured.err)


# --- валидация селектора ----------------------------------------------------

def test_send_requires_selector(monkeypatch, capsys):
    # Нет --all и нет --school: понятная ошибка, без обращения к сети.
    monkeypatch.setattr(push_test, '_load_store', lambda: FakeStore(SUBS))
    code = push_test.main(['--send'])
    assert code == 2
    captured = capsys.readouterr()
    assert '--all' in (captured.out + captured.err)


def test_list_prints_subscriptions(monkeypatch, capsys):
    monkeypatch.setattr(push_test, '_load_store', lambda: FakeStore(SUBS))
    code = push_test.main(['--list'])
    assert code == 0
    out = capsys.readouterr().out
    assert 'school_133' in out
    assert 'class' in out
    assert '6Б' in out
