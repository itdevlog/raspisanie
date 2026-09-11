# tests/test_user_service.py
"""Юнит-тесты UserService: смена школы не теряет настройки."""
import os
import tempfile

from database.file_db import FileDB
from services.user_service import UserService


def _service():
    d = tempfile.mkdtemp()
    return UserService(FileDB(os.path.join(d, 'database.json')))


def test_set_user_school_keeps_notification_settings():
    us = _service()
    us.set_user_notification_settings(1, False, 'school_133')
    assert us.set_user_school(1, 'school_181') is True
    # Настройка для прежней школы должна сохраниться
    assert us.get_user_notification_settings(1, 'school_133') is False
    assert us.get_user_school(1) == 'school_181'


def test_set_user_school_rejects_unknown():
    us = _service()
    assert us.set_user_school(1, 'no_such_school') is False
