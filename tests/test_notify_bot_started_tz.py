"""Регрессия: приветствие бота показывает время по часовому поясу приложения.

Раньше использовался `datetime.now()` без tz — на хосте в UTC это давало
время на 5 часов раньше екатеринбургского.
"""
import types
from datetime import datetime

from services.notification_service import NotificationService


class _FakeDatetime:
    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return datetime(2026, 10, 12, 8, 8)
        return datetime(2026, 10, 12, 13, 8, tzinfo=tz)


async def test_notify_bot_started_uses_app_timezone(monkeypatch):
    import services.notification_service as ns

    monkeypatch.setattr(ns, 'datetime', _FakeDatetime)

    svc = NotificationService()
    captured = {}

    async def fake_notify_admins(context, message):
        captured['message'] = message

    monkeypatch.setattr(svc, 'notify_admins', fake_notify_admins)

    context = types.SimpleNamespace(
        bot_data={
            'schools_data': {'school_1': {'SCHOOL_NAME': 'МАОУ СОШ №1'}},
            'schools_config': {
                'school_1': {
                    'id': 'school_1',
                    'name': 'МАОУ СОШ №1',
                    'city': 'Екатеринбург',
                    'active': True,
                }
            },
        }
    )

    await svc.notify_bot_started(context)  # type: ignore[arg-type]

    message = captured['message']
    assert '12.10.2026 13:08' in message
    assert '08:08' not in message
