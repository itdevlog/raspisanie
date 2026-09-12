"""Настройки обновлений, записанные UI, читаются фоновым апдейтером."""
import os
import tempfile
from types import SimpleNamespace

from core.background_updater import BackgroundUpdater
from database.file_db import FileDB
from services.user_preferences import UserPreferencesService
from services.user_service import UserService


def _make_db() -> FileDB:
    d = tempfile.mkdtemp()
    db = FileDB(os.path.join(d, 'database.json'))
    UserService(db)  # ensure collections
    return db


def test_update_notification_roundtrip():
    db = _make_db()
    prefs = UserPreferencesService(db)
    prefs.enable_update_notifications(1)
    assert UserPreferencesService(db).get_notification_settings(1)['update_notifications'] is True
    prefs.disable_update_notifications(1)
    assert UserPreferencesService(db).get_notification_settings(1)['update_notifications'] is False


def _make_updater(db: FileDB, admin_ids: list[int]) -> BackgroundUpdater:
    updater = object.__new__(BackgroundUpdater)
    updater.logger = SimpleNamespace(error=lambda *a, **k: None)  # type: ignore[assignment]
    updater.application = SimpleNamespace(
        bot_data={
            'user_service': SimpleNamespace(db=db),
            'config': SimpleNamespace(ADMIN_IDS=admin_ids),
        }
    )
    return updater


def test_any_admin_enabled():
    """Хотя бы один админ включил уведомления — фон тоже включён."""
    db = _make_db()
    UserPreferencesService(db).enable_update_notifications(2)
    updater = _make_updater(db, [1, 2])
    assert updater._get_admin_notification_settings()['update_notifications'] is True


def test_all_admins_disabled():
    """Все админы выключили — фон не шлёт уведомления."""
    db = _make_db()
    updater = _make_updater(db, [1, 2])
    assert updater._get_admin_notification_settings()['update_notifications'] is False


def test_no_admins_defaults_disabled():
    db = _make_db()
    updater = _make_updater(db, [])
    assert updater._get_admin_notification_settings()['update_notifications'] is False
