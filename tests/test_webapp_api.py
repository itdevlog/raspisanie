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


def _school_with_metadata(**overrides):
    """Школа с полями метаданных (W32) для `/api/schools`."""
    school = _school()
    school.update({
        'CITY_NAME': 'Пермь',
        'EXPORT_DATE': '04.10.2026',
        'EXPORT_TIME': '20:45:13',
        'HOMEPAGE_URL': 'https://school.example/',
    })
    school.update(overrides)
    return school


class _FakeUserService:
    def get_user_school(self, uid):
        return 'school_133'

    def get_user_class(self, uid, school_id=None):
        return '5а'


def _client(monkeypatch):
    bot_data = {'schools_data': {'school_133': _school()}, 'user_service': _FakeUserService()}
    app = create_app({'bot_data': bot_data})
    return TestClient(app)


def _client_with(**kwargs):
    bot_data = {'schools_data': {'school_133': _school()}, 'user_service': _FakeUserService()}
    return TestClient(create_app({'bot_data': bot_data}, **kwargs))


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


def _entry_for(school, schools_config=None):
    """Возвращает запись `/api/schools` для school_133."""
    bot_data = {'schools_data': {'school_133': school}, 'user_service': _FakeUserService()}
    services = {'bot_data': bot_data}
    if schools_config is not None:
        services['schools_config'] = schools_config
    r = TestClient(create_app(services)).get('/api/schools')
    assert r.status_code == 200
    return r.json()['schools'][0]


def test_schools_metadata_present_when_loaded():
    """Загруженная школа отдаёт city/updated/homepage_url/features (W32)."""
    entry = _entry_for(
        _school_with_metadata(),
        schools_config={'school_133': {'name': 'Школа', 'city': 'Москва', 'active': True}},
    )
    assert entry['id'] == 'school_133'
    assert entry['loaded'] is True
    # city из SCHOOLS_CONFIG имеет приоритет над CITY_NAME.
    assert entry['city'] == 'Москва'
    assert entry['updated'] == '04.10.2026 20:45:13'
    assert entry['homepage_url'] == 'https://school.example/'
    assert entry['features'] == {
        'teachers': True, 'classrooms': True, 'rooms': True, 'homepage': True,
    }


def test_schools_city_falls_back_to_city_name():
    """Нет city в конфиге — берём CITY_NAME из данных школы."""
    entry = _entry_for(
        _school_with_metadata(),
        schools_config={'school_133': {'name': 'Школа', 'active': True}},
    )
    assert entry['city'] == 'Пермь'


def test_schools_features_false_when_flags_false():
    """Ложные флаги SHOW_*/USEROOMS/HOMEPAGE_BTN выключают features."""
    school = _school_with_metadata(
        SHOW_TEACHERS=False, SHOW_CLASSROOMS=False, USEROOMS=False, HOMEPAGE_BTN=False,
    )
    entry = _entry_for(school)
    assert entry['features'] == {
        'teachers': False, 'classrooms': False, 'rooms': False, 'homepage': False,
    }


def test_schools_features_default_true_when_flags_absent():
    """Отсутствующие флаги считаются включёнными (default True)."""
    entry = _entry_for(_school_with_metadata())
    assert entry['features'] == {
        'teachers': True, 'classrooms': True, 'rooms': True, 'homepage': True,
    }


def test_schools_metadata_defaults_when_not_loaded():
    """Школа без данных: метаданные None, features по умолчанию True."""
    bot_data = {'schools_data': {}, 'user_service': _FakeUserService()}
    services = {
        'bot_data': bot_data,
        'schools_config': {'school_133': {'name': 'Школа', 'active': True}},
    }
    r = TestClient(create_app(services)).get('/api/schools')
    assert r.status_code == 200
    entry = r.json()['schools'][0]
    assert entry['loaded'] is False
    assert entry['city'] is None
    assert entry['updated'] is None
    assert entry['homepage_url'] is None
    assert entry['features'] == {
        'teachers': True, 'classrooms': True, 'rooms': True, 'homepage': True,
    }


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


def test_schools_config_from_services_overrides_default():
    """schools_config из services переопределяет модульный SCHOOLS_CONFIG."""
    custom = {'school_133': {'name': 'Своя школа', 'active': True}}
    bot_data = {'schools_data': {'school_133': _school()}, 'user_service': _FakeUserService()}
    services = {'bot_data': bot_data, 'schools_config': custom}
    r = TestClient(create_app(services)).get('/api/schools')
    assert r.status_code == 200
    entry = r.json()['schools'][0]
    # W32 добавляет метаданные аддитивно; базовый контракт сохраняется.
    assert entry['id'] == 'school_133'
    assert entry['name'] == 'Своя школа'
    assert entry['loaded'] is True


def test_schools_config_falls_back_to_module_default():
    """Без services['schools_config'] используется модульный SCHOOLS_CONFIG."""
    bot_data = {'schools_data': {'school_133': _school()}, 'user_service': _FakeUserService()}
    r = TestClient(create_app({'bot_data': bot_data})).get('/api/schools')
    schools = {s['id']: s for s in r.json()['schools']}
    entry = schools['school_133']
    assert entry['id'] == 'school_133'
    assert entry['name'] == 'МАОУ СОШ №133'
    assert entry['loaded'] is True


def test_static_dir_override(tmp_path):
    """static_dir монтирует статику из переданного каталога."""
    (tmp_path / 'index.html').write_text('<html>edge</html>', encoding='utf-8')
    client = _client_with(static_dir=str(tmp_path))
    r = client.get('/')
    assert r.status_code == 200
    assert 'edge' in r.text


def test_telegram_routes_enabled_by_default():
    """По умолчанию /api/me и /api/widget зарегистрированы (origin)."""
    client = _client(None)
    assert client.get('/api/me').status_code == 200
    assert client.get('/api/widget/1').status_code in (403, 200)


def test_telegram_routes_absent_when_disabled():
    """enable_telegram_routes=False убирает /api/me и /api/widget (edge)."""
    client = _client_with(enable_telegram_routes=False)
    assert client.get('/api/me').status_code == 404
    assert client.get('/api/widget/1').status_code == 404
    # Публичные маршруты остаются доступны.
    assert client.get('/api/schools').status_code == 200


def test_health_provider_adds_fields():
    """health_provider добавляет поля в /healthz."""
    client = _client_with(health_provider=lambda: {'snapshot_age_seconds': 42})
    body = client.get('/healthz').json()
    assert body == {'status': 'ok', 'snapshot_age_seconds': 42}


def test_health_provider_overrides_status():
    """health_provider может переопределить status."""
    client = _client_with(health_provider=lambda: {'status': 'stale', 'grade': 1})
    body = client.get('/healthz').json()
    assert body == {'status': 'stale', 'grade': 1}
