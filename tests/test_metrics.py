"""MetricsService: инкремент, снимок и логирование агрегата."""
import logging

from services.metrics import MetricsService


def test_incr_and_get():
    metrics = MetricsService()

    assert metrics.incr('exchanges_sent') == 1
    assert metrics.incr('exchanges_sent', 5) == 6
    assert metrics.get('exchanges_sent') == 6
    assert metrics.get('missing') == 0


def test_snapshot_is_a_copy():
    metrics = MetricsService()
    metrics.incr('a')

    snapshot = metrics.snapshot()
    metrics.incr('a')

    assert snapshot == {'a': 1}
    assert metrics.snapshot() == {'a': 2}


def test_log_snapshot_logs_counters(caplog):
    metrics = MetricsService()
    metrics.incr('reminders_sent', 2)
    metrics.incr('send_errors')

    with caplog.at_level(logging.INFO, logger='services.metrics'):
        result = metrics.log_snapshot()

    assert result == {'reminders_sent': 2, 'send_errors': 1}
    assert 'reminders_sent=2' in caplog.text
    assert 'send_errors=1' in caplog.text


def test_log_snapshot_empty_does_not_log(caplog):
    metrics = MetricsService()

    with caplog.at_level(logging.INFO, logger='services.metrics'):
        assert metrics.log_snapshot() == {}

    assert caplog.text == ''
