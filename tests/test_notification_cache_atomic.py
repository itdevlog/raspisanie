# tests/test_notification_cache_atomic.py
"""Регрессия: запись notifications_cache.json атомарна (tmp + os.replace).

Крах в момент записи не должен рвать существующий кэш: иначе следующий
запуск сбросит его и разошлёт массовые дубли уведомлений.
"""
import json
import logging
import os

from services.notification_service import NotificationService


def _make_svc(path: str) -> NotificationService:
    svc = NotificationService.__new__(NotificationService)
    svc.logger = logging.getLogger('test')
    svc.sent_notifications = {}
    svc.notifications_cache_file = path
    return svc


def test_save_is_atomic_and_keeps_old_cache_on_crash(tmp_path, monkeypatch):
    path = str(tmp_path / 'notifications_cache.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'exchanges': {'old': 1.0}}, f)
    svc = _make_svc(path)
    svc.sent_notifications = {'exchanges': {'new': 2.0}}

    def _boom(*args, **kwargs):
        raise RuntimeError('crash mid-write')

    monkeypatch.setattr('services.notification_service.json.dump', _boom)
    svc.save_notifications_cache()

    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    assert data == {'exchanges': {'old': 1.0}}


def test_save_writes_sets_as_lists_and_replaces(tmp_path):
    path = str(tmp_path / 'notifications_cache.json')
    svc = _make_svc(path)
    svc.sent_notifications = {'exchanges': {'k': 1.0}, 'old': {'a', 'b'}}  # type: ignore[dict-item]
    svc.save_notifications_cache()

    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    assert data['exchanges'] == {'k': 1.0}
    assert sorted(data['old']) == ['a', 'b']
    assert not os.path.exists(path + '.tmp')
