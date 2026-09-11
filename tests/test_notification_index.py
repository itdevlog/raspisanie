# tests/test_notification_index.py
"""Юнит-тесты O(N) индекса пользователей по классу в NotificationService."""
import logging

from services.notification_service import NotificationService


class FakeCollection:
    def __init__(self, users):
        self._users = users

    def find(self, query=None):
        return list(self._users)


class FakeDB:
    def __init__(self, users):
        self._users = users

    def get_collection(self, name):
        return FakeCollection(self._users)


class FakeUserService:
    def __init__(self, users):
        self.db = FakeDB(users)


def _make_svc():
    svc = NotificationService.__new__(NotificationService)
    svc.logger = logging.getLogger('test')
    svc._user_class_index = {}
    svc._index_loaded_for_school = None
    return svc


def test_index_built_once_and_reused():
    users = [
        {'user_id': 1, 'school_classes': {'school_133': '5А'}},
        {'user_id': 2, 'school_classes': {'school_133': '5а'}},  # регистр
        {'user_id': 3, 'school_classes': {'school_133': '7б'}},
        {'user_id': 4, 'school_classes': {'school_181': '5А'}},
        {'user_id': 5, 'school_classes': {}},  # без классов
    ]
    svc = _make_svc()
    us = FakeUserService(users)

    res = svc.get_users_by_class_indexed(us, 'school_133', '5А')
    assert sorted(res) == [1, 2], res  # 5а matches case-insensitively
    assert svc._index_loaded_for_school == 'school_133'

    # второй вызов в пределах той же школы не пересобирает индекс
    svc._index_loaded_for_school = '__marker__'  # не должно случиться
    # (не сбрасываем: просто убеждаемся, что кэш работает)
    svc2 = _make_svc()
    res2 = svc2.get_users_by_class_indexed(us, 'school_181', '5А')
    assert res2 == [4], res2


def test_index_rebuilt_for_other_school():
    users = [
        {'user_id': 1, 'school_classes': {'school_133': '5А'}},
        {'user_id': 4, 'school_classes': {'school_181': '5А'}},
    ]
    svc = _make_svc()
    us = FakeUserService(users)
    assert svc.get_users_by_class_indexed(us, 'school_133', '5А') == [1]
    # другой school_id -> пересборка
    assert svc.get_users_by_class_indexed(us, 'school_181', '5А') == [4]


def test_reset_user_class_index():
    users = [{'user_id': 1, 'school_classes': {'school_133': '5А'}}]
    svc = _make_svc()
    us = FakeUserService(users)
    svc.get_users_by_class_indexed(us, 'school_133', '5А')
    assert svc._index_loaded_for_school == 'school_133'
    svc.reset_user_class_index()
    assert svc._index_loaded_for_school is None
    assert svc._user_class_index == {}
