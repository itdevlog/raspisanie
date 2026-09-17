# tests/test_status_service.py
"""Поведенческие тесты StatusService: классификация свежести данных школы."""
from datetime import datetime, timedelta

from services.status_service import StatusService, status_icon


def _school(dt: datetime) -> dict:
    return {
        'EXPORT_DATE': dt.strftime('%d.%m.%Y'),
        'EXPORT_TIME': dt.strftime('%H:%M:%S'),
    }


def _svc_with(school_data: dict) -> StatusService:
    return StatusService({'school_133': school_data})


def _exported_hours_ago(svc: StatusService, hours: float) -> dict:
    dt = datetime.now(svc.moscow_tz) - timedelta(hours=hours)
    return _school(dt)


def test_missing_school_not_loaded():
    status = StatusService({}).get_school_status('school_999')
    assert status['loaded'] is False
    assert '❌' in status['status']
    assert status['last_update'] is None


def test_empty_school_data_not_loaded():
    status = StatusService({'school_133': {}}).get_school_status('school_133')
    assert status['loaded'] is False


def test_fresh_data_is_actual():
    svc = _svc_with({})
    svc.schools_data = {'school_133': _exported_hours_ago(svc, 0.5)}
    status = svc.get_school_status('school_133')
    assert status['loaded'] is True
    assert '✅' in status['status']
    assert 'Актуально' in status['status']


def test_data_today_is_warning():
    svc = _svc_with({})
    svc.schools_data = {'school_133': _exported_hours_ago(svc, 5)}
    status = svc.get_school_status('school_133')
    assert '⚠️' in status['status']
    assert 'Сегодня' in status['status']


def test_old_data_is_stale():
    svc = _svc_with({})
    svc.schools_data = {'school_133': _exported_hours_ago(svc, 30)}
    status = svc.get_school_status('school_133')
    assert '🔴' in status['status']
    assert 'Устарело' in status['status']


def test_unparseable_date_is_unknown_but_loaded():
    svc = _svc_with({'EXPORT_DATE': 'мусор', 'EXPORT_TIME': 'мусор'})
    status = svc.get_school_status('school_133')
    assert status['loaded'] is True
    assert '⚠️' in status['status']
    assert 'Неизвестно' in status['status']


def test_time_without_seconds_parsed():
    svc = _svc_with({})
    dt = datetime.now(svc.moscow_tz) - timedelta(minutes=30)
    svc.schools_data = {'school_133': {
        'EXPORT_DATE': dt.strftime('%d.%m.%Y'),
        'EXPORT_TIME': dt.strftime('%H:%M'),
    }}
    status = svc.get_school_status('school_133')
    assert '✅' in status['status']
    assert status['last_update'] == dt.strftime('%d.%m.%Y %H:%M')
    assert status['time_ago'] == '30 мин'


def test_get_all_statuses_covers_all_schools():
    svc = StatusService({
        'school_133': {'EXPORT_DATE': '', 'EXPORT_TIME': ''},
        'school_181': {},
    })
    statuses = svc.get_all_statuses()
    assert set(statuses) == {'school_133', 'school_181'}
    assert statuses['school_181']['loaded'] is False


def test_is_school_data_loaded():
    svc = StatusService({'school_133': {'X': 1}, 'school_181': {}})
    assert svc.is_school_data_loaded('school_133') is True
    assert svc.is_school_data_loaded('school_181') is False
    assert svc.is_school_data_loaded('school_999') is False


def test_get_last_update_time():
    svc = _svc_with({})
    dt = datetime.now(svc.moscow_tz) - timedelta(minutes=10)
    svc.schools_data = {'school_133': _school(dt)}
    last = svc.get_last_update_time('school_133')
    assert last is not None
    assert last.date() == dt.date()


def test_get_last_update_time_missing():
    assert StatusService({}).get_last_update_time('nope') is None


def test_status_icon_extracts_known_icons():
    assert status_icon({'status': '✅ Актуально'}) == '✅'
    assert status_icon({'status': '⚠️ Сегодня'}) == '⚠️'
    assert status_icon({'status': '🔴 Устарело'}) == '🔴'
    assert status_icon({'status': '❌ Не загружено'}) == '❌'


def test_status_icon_default_warning():
    assert status_icon({'status': 'что-то ещё'}) == '⚠️'
    assert status_icon({}) == '⚠️'
