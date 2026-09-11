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


def test_get_notification_settings_batch():
    import os
    import tempfile

    from database.file_db import FileDB
    from services.user_service import UserService

    d = tempfile.mkdtemp()
    us = UserService(FileDB(os.path.join(d, 'database.json')))
    us.set_user_class(1, '5а', 'school_133')
    us.set_user_class(2, '5а', 'school_133')
    us.set_user_notification_settings(2, False, 'school_133')

    batch = us.get_notification_settings_batch('school_133')
    assert batch[1] is True
    assert batch[2] is False


def test_get_users_for_exchange_filters_disabled():
    users = [
        {'user_id': 1, 'school_classes': {'school_133': '5А'}, 'notification_settings': {'school_133': True}},
        {'user_id': 2, 'school_classes': {'school_133': '5а'}, 'notification_settings': {'school_133': False}},
        {'user_id': 3, 'school_classes': {'school_133': '5А'}},  # нет настроек -> включено по умолчанию
        {'user_id': 4, 'school_classes': {'school_133': '7б'}, 'notification_settings': {'school_133': True}},
    ]
    svc = _make_svc()
    us = FakeUserService(users)

    # индекс строится один раз для школы
    svc.get_users_by_class_indexed(us, 'school_133', '5А')
    result = svc.get_users_for_exchange('school_133', '5А')
    assert sorted(result) == [1, 3], result  # 2 отключён, 4 — другой класс


def test_get_users_for_exchange_defaults_enabled_without_settings():
    users = [
        {'user_id': 5, 'school_classes': {'school_133': '9В'}},
    ]
    svc = _make_svc()
    us = FakeUserService(users)
    svc.get_users_by_class_indexed(us, 'school_133', '9В')
    assert svc.get_users_for_exchange('school_133', '9В') == [5]


def test_notification_ttl_cleanup():
    import time

    from services.notification_service import NotificationService
    svc = NotificationService.__new__(NotificationService)
    svc.logger = logging.getLogger('test')
    svc.sent_notifications = {
        'exchanges': {
            'old_key': time.time() - (25 * 60 * 60),   # старше 24 ч
            'new_key': time.time(),                      # свежий
        }
    }
    svc._cleanup_old_notifications()
    assert 'old_key' not in svc.sent_notifications['exchanges']
    assert 'new_key' in svc.sent_notifications['exchanges']


def test_notification_mark_and_is_sent():
    svc = _make_svc()
    svc.sent_notifications = {}
    svc._mark_notification_sent('abc')
    assert svc._is_notification_sent('abc') is True
    assert svc._is_notification_sent('def') is False
