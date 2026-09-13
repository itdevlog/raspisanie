# tests/test_exchange_detector_dates.py
"""Регрессии: кэш замен разделён по датам, запись атомарна, persist управляем."""
import json
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.exchange_detector import ExchangeDetector

TZ = ZoneInfo('Asia/Yekaterinburg')


def _detector(tmp_path):
    d = ExchangeDetector.__new__(ExchangeDetector)
    d.logger = logging.getLogger('test')
    d.moscow_tz = TZ
    d.previous_schedules = {}
    d.cache_file = str(tmp_path / 'exchange_cache.json')
    return d


def _school_data(date_str):
    return {
        'CLASSES': {'c1': '5А'},
        'CLASS_EXCHANGE': {'c1': {date_str: {'1': {'s': '1', 't': 'Т1', 'r': '101'}}}},
        'SUBJECTS': {'1': 'Математика'},
        'TEACHERS': {'Т1': 'Иванов'},
        'ROOMS': {'101': '101'},
    }


def test_dates_do_not_overwrite_each_other(tmp_path):
    d = _detector(tmp_path)
    today = datetime(2026, 9, 11, 12, 0, tzinfo=TZ)
    tomorrow = today + timedelta(days=1)

    sd_today = _school_data('11.09.2026')
    assert len(d.detect_exchanges('s', sd_today, today, persist=False)) == 1
    # Проверка «завтра» не должна затирать baseline «сегодня»
    d.detect_exchanges('s', _school_data('12.09.2026'), tomorrow, persist=False)

    assert '11.09.2026' in d.previous_schedules['s']
    # Повторный прогон «сегодня» не находит новых замен
    assert d.detect_exchanges('s', sd_today, today, persist=False) == []


def test_persist_flag_controls_disk_write(tmp_path):
    d = _detector(tmp_path)
    today = datetime(2026, 9, 11, 12, 0, tzinfo=TZ)
    d.detect_exchanges('s', _school_data('11.09.2026'), today, persist=False)
    assert not os.path.exists(d.cache_file)

    d.save_cache()
    assert os.path.exists(d.cache_file)
    with open(d.cache_file, encoding='utf-8') as f:
        assert '11.09.2026' in json.load(f)['s']


def test_legacy_cache_is_discarded(tmp_path):
    d = _detector(tmp_path)
    with open(d.cache_file, 'w', encoding='utf-8') as f:
        json.dump({'s': {'5А': {'1': {}}}}, f)  # старый плоский формат

    d.load_cache()
    assert d.previous_schedules == {}


def test_old_dates_are_pruned(tmp_path):
    d = _detector(tmp_path)
    d.previous_schedules = {'s': {'01.01.2020': {'5А': {}}}}
    d.save_cache()
    assert d.previous_schedules == {}
