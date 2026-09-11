from datetime import timedelta

from services.base_schedule_service import find_class_id, format_time_ago


def test_format_time_ago():
    assert format_time_ago(timedelta(seconds=10)) == 'только что'
    assert format_time_ago(timedelta(minutes=5)) == '5 мин'
    assert format_time_ago(timedelta(hours=3)) == '3 ч'
    assert format_time_ago(timedelta(days=2)) == '2 дн'


def test_find_class_id_module_helper():
    school_data = {'CLASSES': {'c5a': '5а', 'c10a': '10Б'}}
    assert find_class_id(school_data, '5а') == 'c5a'
    assert find_class_id(school_data, '10Б') == 'c10a'
    assert find_class_id(school_data, '5') is None
    assert find_class_id(school_data, 'NOPE') is None
    assert find_class_id(school_data, '') is None
