"""API Mini App через FastAPI TestClient."""
from fastapi.testclient import TestClient

from web.api import create_app


def _school():
    return {
        'SCHOOL_NAME': 'Тест',
        'CLASSES': {'c1': '5а'},
        'TEACHERS': {'t1': 'Иванов'},
        'ROOMS': {'r1': '101', 'r2': '202'},
        'SUBJECTS': {'s1': 'Математика'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
        'CLASS_SCHEDULE': {'p1': {'c1': {'101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}}}},
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
    }


class _FakeUserService:
    def get_user_school(self, uid):
        return 'school_133'

    def get_user_class(self, uid, school_id=None):
        return '5а'


def _client(monkeypatch):
    bot_data = {'schools_data': {'school_133': _school()}, 'user_service': _FakeUserService()}
    app = create_app({'bot_data': bot_data})
    return TestClient(app)


def test_healthz():
    client = _client(None)
    assert client.get('/healthz').status_code == 200
    assert client.get('/healthz').json() == {'status': 'ok'}


def test_schools_list():
    r = _client(None).get('/api/schools')
    assert r.status_code == 200
    body = r.json()['schools']
    assert body[0]['id'] == 'school_133'
    assert body[0]['loaded'] is True


def test_schools_today_format():
    import re

    r = _client(None).get('/api/schools')
    assert r.status_code == 200
    assert re.fullmatch(r'\d{2}\.\d{2}\.\d{4}', r.json()['today'])


def test_classes_list():
    r = _client(None).get('/api/school_133/classes')
    assert r.json()['classes'] == ['5а']


def test_schedule_day_with_date():
    r = _client(None).get('/api/school_133/schedule/class/5а?date=07.09.2026')
    assert r.status_code == 200
    day = r.json()
    assert day['entity'] == '5а'
    assert day['lessons'][0]['items'][0]['subject'] == 'Математика'


def test_schedule_week():
    r = _client(None).get('/api/school_133/schedule/class/5а/week?offset=1')
    assert r.status_code == 200
    assert len(r.json()['days']) == 5


def test_schedule_week_out_of_period_returns_payloads():
    school = _school()
    school['PERIODS'] = {}
    bot_data = {'schools_data': {'school_133': school}, 'user_service': _FakeUserService()}
    client = TestClient(create_app({'bot_data': bot_data}))
    r = client.get('/api/school_133/schedule/class/5а/week?offset=0')
    assert r.status_code == 200
    days = r.json()['days']
    assert len(days) == 5
    assert all(d['no_period'] is True for d in days)


def test_schedule_day_out_of_period_422():
    school = _school()
    school['PERIODS'] = {}
    bot_data = {'schools_data': {'school_133': school}, 'user_service': _FakeUserService()}
    client = TestClient(create_app({'bot_data': bot_data}))
    r = client.get('/api/school_133/schedule/class/5а?date=07.09.2026')
    assert r.status_code == 422


def test_schedule_unknown_entity_404():
    r = _client(None).get('/api/school_133/schedule/class/11ю?date=07.09.2026')
    assert r.status_code == 404


def test_unknown_school_404():
    r = _client(None).get('/api/school_999/classes')
    assert r.status_code == 404


def test_search():
    r = _client(None).get('/api/school_133/search?q=ив')
    assert r.status_code == 200
    assert 'Иванов' in r.json()['teachers']


def test_free_rooms():
    r = _client(None).get('/api/school_133/free-rooms?date=07.09.2026&lesson=1')
    assert r.status_code == 200
    assert '202' in r.json()['free_rooms']
    assert '101' not in r.json()['free_rooms']


def test_me_anonymous():
    r = _client(None).get('/api/me')
    assert r.status_code == 200
    body = r.json()
    assert body['user'] is None
    assert body['school_id'] is None
    assert body['class_name'] is None
