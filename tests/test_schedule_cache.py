# tests/test_schedule_cache.py
"""Регрессия: кэш расписания не пересекается между школами."""
from datetime import datetime

import pytz

from services.cache_service import CacheService
from services.schedule_service import ScheduleService

TZ = pytz.timezone('Asia/Yekaterinburg')


class _Stub(ScheduleService):
    """Считает вызовы и отдаёт маркер школы вместо реального расписания."""

    def __init__(self, school_id, cache, calls):
        super().__init__({}, cache, school_id)
        self._calls = calls

    def _get_class_schedule_for_date(self, class_name, date, include_header=False):
        self._calls.append(class_name)
        return f"data-{self.school_id}"


def test_schedule_cache_isolated_by_school():
    cache = CacheService(ttl=300)
    calls: list[str] = []
    a = _Stub('school_a', cache, calls)
    b = _Stub('school_b', cache, calls)

    assert a.get_class_schedule_today('5и') == 'data-school_a'
    assert b.get_class_schedule_today('5и') == 'data-school_b'
    # Повторный вызов школы A отдаётся из кэша, вычисления не повторяются
    assert a.get_class_schedule_today('5и') == 'data-school_a'
    assert calls == ['5и', '5и']


def test_cache_key_contains_school():
    cache = CacheService(ttl=300)
    a = ScheduleService({}, cache, 'school_a')
    b = ScheduleService({}, cache, 'school_b')
    date = datetime(2026, 9, 11, 12, 0, tzinfo=TZ)
    assert a._cache_key('today', '5и', date) != b._cache_key('today', '5и', date)
