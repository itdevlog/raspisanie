# tests/test_user_repository.py
"""Юнит-тесты слоя доступа к пользователям `UserRepository`."""
import logging

from services.notification_service import NotificationService
from services.user_repository import UserRepository
from services.user_service import UserService


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
    """Лёгкий сервис без `get_users_with_classes` — репозиторий читает коллекцию."""

    def __init__(self, users):
        self.db = FakeDB(users)


def _make_svc(users):
    svc = NotificationService.__new__(NotificationService)
    svc.logger = logging.getLogger('test')
    svc._user_class_index = {}
    svc._index_loaded_for_school = None
    svc._settings_for_school = {}
    return svc, FakeUserService(users)


def test_get_users_by_class_filters_school_class_and_settings():
    users = [
        {'user_id': 1, 'school_classes': {'school_133': '5А'},
         'notification_settings': {'school_133': True}},
        {'user_id': 2, 'school_classes': {'school_133': '5а'},
         'notification_settings': {'school_133': False}},  # выключено
        {'user_id': 3, 'school_classes': {'school_133': '5А'}},  # дефолт -> вкл
        {'user_id': 4, 'school_classes': {'school_181': '5А'}},  # другая школа
        {'user_id': 5, 'school_classes': {'school_133': '7б'}},  # другой класс
    ]
    repo = UserRepository(FakeUserService(users))
    assert sorted(repo.get_users_by_class('school_133', '5А')) == [1, 3]


def test_iter_users_with_classes_skips_users_without_classes():
    users = [
        {'user_id': 1, 'school_classes': {'school_133': '5А'}},
        {'user_id': 2, 'school_classes': {}},
        {'user_id': 3},
    ]
    repo = UserRepository(FakeUserService(users))
    assert [u['user_id'] for u in repo.iter_users_with_classes()] == [1]


def test_notification_index_uses_repository_without_direct_db_access():
    users = [
        {'user_id': 1, 'school_classes': {'school_133': '5А'},
         'notification_settings': {'school_133': True}},
        {'user_id': 2, 'school_classes': {'school_133': '5а'},
         'notification_settings': {'school_133': False}},
    ]
    svc, us = _make_svc(users)
    res = svc.get_users_by_class_indexed(us, 'school_133', '5А')
    assert sorted(res) == [1, 2]
    assert svc.get_users_for_exchange('school_133', '5А') == [1]
    assert svc._settings_for_school == {1: True, 2: False}


def test_preferences_delegates_to_user_preferences_service(make_db):
    from services.user_preferences import UserPreferencesService

    db = make_db()
    us = UserService(db)
    UserPreferencesService(db).set_notification_settings(1, {'lesson_reminders': True})

    repo = UserRepository(us)
    assert repo.preferences is repo.preferences  # ленивый кэш
    assert repo.get_notification_settings(1)['lesson_reminders'] is True
    assert repo.get_settings_map()[1]['lesson_reminders'] is True
