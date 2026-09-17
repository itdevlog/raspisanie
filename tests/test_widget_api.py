# tests/test_widget_api.py
"""Тесты API виджета PWA."""
import hashlib
import hmac
import json
import time
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import quote

from fastapi.testclient import TestClient

from config.config import get_timezone
from web.auth import generate_widget_token, validate_widget_token

BOT_TOKEN = '123456:ABC-DEF_token'
SECRET = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()


def _make_init_data(user_id: int, sign: bool = True) -> str:
    params = {'user': json.dumps({'id': user_id}), 'auth_date': str(int(time.time()))}
    pairs = sorted(params.items())
    data_check_string = '\n'.join(f'{k}={v}' for k, v in pairs)
    if sign:
        sig = hmac.new(SECRET, data_check_string.encode(), hashlib.sha256).hexdigest()
        pairs.append(('hash', sig))
    return '&'.join(f'{k}={quote(str(v))}' for k, v in pairs)


def _school():
    return {
        'SCHOOL_NAME': 'Тест',
        'CLASSES': {'c1': '5А'},
        'TEACHERS': {'t1': 'Иванов'},
        'ROOMS': {'r1': '101', 'r2': '202'},
        'SUBJECTS': {'s1': 'Математика', 's2': 'Физика'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['09:00', '09:45']},
        'LESSONSINDAY': 6,
        'CLASS_SCHEDULE': {
            'p1': {'c1': {
                '101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},
                '102': {'s': ['s2'], 't': ['t1'], 'r': ['r2']},
            }}
        },
        'CLASS_EXCHANGE': {},
    }


class FakeUserService:
    def __init__(self, school='school_133', class_name='5А'):
        self._school = school
        self._class = class_name

    def get_user_school(self, uid):
        return self._school

    def get_user_class(self, uid, sid):
        return self._class


def _client(user_service=None, config=None):
    from web.api import create_app

    services = {
        'bot_data': {
            'user_service': user_service or FakeUserService(),
            'schools_data': {'school_133': _school()},
        },
        'config': config or SimpleNamespace(TELEGRAM_TOKEN=BOT_TOKEN),
    }
    return TestClient(create_app(services))


def _auth(user_id: int):
    return {'X-Telegram-Init-Data': _make_init_data(user_id)}


def test_widget_endpoint_requires_valid_user_id():
    """Widget endpoint требует валидный user_id (int)."""
    response = _client().get('/api/widget/abc', headers=_auth(1))
    assert response.status_code == 422


def test_widget_returns_schedule_values(monkeypatch):
    """Widget возвращает непустые значения времени/предмета/кабинета."""
    import web.api as api_module

    fixed_now = datetime(2026, 12, 7, 7, 30, tzinfo=get_timezone())
    monkeypatch.setattr(api_module, '_now', lambda: fixed_now)

    response = _client().get('/api/widget/123456?date=07.12.2026', headers=_auth(123456))
    assert response.status_code == 200

    data = response.json()
    assert data['class'] == '5А'
    assert data['date'] == '2026-12-07'
    assert data['exchanges_count'] == 0

    assert isinstance(data['lessons'], list)
    assert len(data['lessons']) == 2
    first = data['lessons'][0]
    assert first['num'] == 1
    assert first['time'] == '08:00-08:45'
    assert first['subject'] == 'Математика'
    assert first['room'] == '101'

    assert data['next_lesson'] is not None
    assert data['next_lesson']['num'] == 1
    assert data['next_lesson']['time'] == '08:00-08:45'
    assert data['next_lesson']['subject'] == 'Математика'
    assert data['next_lesson']['room'] == '101'
    assert data['next_lesson']['in_minutes'] == 30


def test_widget_next_lesson_skips_cancelled_and_past(monkeypatch):
    """Следующим считается ближайший будущий непотменённый урок."""
    import web.api as api_module

    fixed_now = datetime(2026, 12, 7, 8, 30, tzinfo=get_timezone())
    monkeypatch.setattr(api_module, '_now', lambda: fixed_now)

    response = _client().get('/api/widget/123456?date=07.12.2026', headers=_auth(123456))
    assert response.status_code == 200
    nxt = response.json()['next_lesson']
    assert nxt is not None
    assert nxt['num'] == 2
    assert nxt['subject'] == 'Физика'
    assert nxt['room'] == '202'


def test_widget_rejects_missing_init_data():
    """Без X-Telegram-Init-Data — 403."""
    response = _client().get('/api/widget/123456')
    assert response.status_code == 403


def test_widget_rejects_invalid_init_data():
    """Невалидная подпись initData (свежий auth_date, битый hash) — 403."""
    fresh = _make_init_data(123456, sign=False) + '&hash=deadbeef'
    response = _client().get('/api/widget/123456',
                             headers={'X-Telegram-Init-Data': fresh})
    assert response.status_code == 403


def test_widget_rejects_mismatched_user():
    """Подпись валидна, но user_id другой — 403 (закрытие IDOR)."""
    response = _client().get('/api/widget/43', headers=_auth(42))
    assert response.status_code == 403


def test_widget_accepts_valid_token_header():
    """Валидный widget-токен в X-Widget-Token — 200."""
    token = generate_widget_token(123456, BOT_TOKEN)
    response = _client().get('/api/widget/123456',
                             headers={'X-Widget-Token': token})
    assert response.status_code == 200
    assert response.json()['class'] == '5А'


def test_widget_accepts_valid_token_query():
    """Валидный widget-токен в query-параметре token — 200."""
    token = generate_widget_token(123456, BOT_TOKEN)
    response = _client().get(f'/api/widget/123456?token={token}')
    assert response.status_code == 200


def test_widget_rejects_wrong_token():
    """Битый widget-токен — 403."""
    response = _client().get('/api/widget/123456',
                             headers={'X-Widget-Token': 'nonsense'})
    assert response.status_code == 403


def test_widget_rejects_expired_token():
    """Просроченный widget-токен — 403."""
    token = generate_widget_token(123456, BOT_TOKEN, ttl=-1)
    response = _client().get('/api/widget/123456',
                             headers={'X-Widget-Token': token})
    assert response.status_code == 403


def test_widget_rejects_token_for_other_user():
    """Токен, выписанный на другого пользователя — 403."""
    token = generate_widget_token(42, BOT_TOKEN)
    response = _client().get('/api/widget/123456',
                             headers={'X-Widget-Token': token})
    assert response.status_code == 403


def test_widget_handles_empty_items(monkeypatch):
    """Урок без items не падает; subject/room пустые."""
    import web.api as api_module
    from services.schedule_service import ScheduleService

    monkeypatch.setattr(api_module, '_now',
                        lambda: datetime(2026, 12, 7, 7, 0, tzinfo=get_timezone()))

    def _fake_get_day(self, class_name, date):
        return {
            'lessons': [
                {'num': 1, 'start': '08:00', 'end': '08:45', 'items': [],
                 'has_exchange': False, 'is_cancelled': False},
            ],
            'vacation': False, 'weekend': False,
        }

    monkeypatch.setattr(ScheduleService, 'get_day', _fake_get_day)

    token = generate_widget_token(123456, BOT_TOKEN)
    response = _client().get('/api/widget/123456',
                             headers={'X-Widget-Token': token})
    assert response.status_code == 200
    lesson = response.json()['lessons'][0]
    assert lesson['subject'] == ''
    assert lesson['room'] == ''
    assert lesson['time'] == '08:00-08:45'


def test_widget_user_not_found():
    """Widget возвращает 404 для неизвестного пользователя."""
    user_service = FakeUserService(school=None, class_name=None)
    response = _client(user_service=user_service).get('/api/widget/999999',
                                                      headers=_auth(999999))
    assert response.status_code == 404


def test_generate_and_validate_widget_token_roundtrip():
    token = generate_widget_token(7, BOT_TOKEN, now=1000)
    assert validate_widget_token(token, 7, BOT_TOKEN, now=1001) is True


def test_validate_widget_token_rejects_malformed():
    assert validate_widget_token('no-dot', 7, BOT_TOKEN) is False
    assert validate_widget_token('abc.def', 7, BOT_TOKEN) is False
    assert validate_widget_token('', 7, BOT_TOKEN) is False


def test_validate_widget_token_rejects_expired_and_other_user():
    token = generate_widget_token(7, BOT_TOKEN, ttl=10, now=1000)
    assert validate_widget_token(token, 7, BOT_TOKEN, now=1011) is False
    assert validate_widget_token(token, 8, BOT_TOKEN, now=1001) is False
    assert validate_widget_token(token, 7, 'other-token', now=1001) is False

