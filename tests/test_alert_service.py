"""AlertService: порог, окно, антиспам, подмена времени, очистка."""
from services.alert_service import AlertService


class _Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def _svc(clock: _Clock, **kwargs) -> AlertService:
    kwargs.setdefault('threshold', 3)
    kwargs.setdefault('window_seconds', 300)
    return AlertService(now=clock, **kwargs)


def test_record_counts_errors_within_window():
    clock = _Clock()
    svc = _svc(clock)

    assert svc.record(RuntimeError('boom'), 'update') == 1
    assert svc.record(RuntimeError('boom'), 'update') == 2
    assert svc.record(RuntimeError('boom'), 'update') == 3


def test_record_separates_keys_by_source_and_type():
    clock = _Clock()
    svc = _svc(clock)

    svc.record(RuntimeError('boom'), 'update')
    svc.record(ValueError('boom'), 'update')

    assert svc.record(RuntimeError('boom'), 'background') == 1


def test_should_alert_at_threshold_then_anti_spam():
    clock = _Clock()
    svc = _svc(clock)
    key = AlertService.error_key(RuntimeError('boom'), 'update')

    for _ in range(3):
        svc.record(RuntimeError('boom'), 'update')

    assert svc.should_alert(key) is True
    # Повтор в том же окне не алертит (антиспам)
    svc.record(RuntimeError('boom'), 'update')
    assert svc.should_alert(key) is False


def test_should_alert_below_threshold_is_false():
    clock = _Clock()
    svc = _svc(clock)
    key = AlertService.error_key(RuntimeError('boom'), 'update')

    svc.record(RuntimeError('boom'), 'update')
    svc.record(RuntimeError('boom'), 'update')

    assert svc.should_alert(key) is False


def test_window_expiry_resets_count_and_allows_alert_again():
    clock = _Clock()
    svc = _svc(clock)
    key = AlertService.error_key(RuntimeError('boom'), 'update')

    for _ in range(3):
        svc.record(RuntimeError('boom'), 'update')
    assert svc.should_alert(key) is True

    clock.t = 400.0
    for _ in range(3):
        svc.record(RuntimeError('boom'), 'update')

    assert svc.should_alert(key) is True


def test_stale_keys_do_not_grow_unbounded():
    clock = _Clock()
    svc = _svc(clock, max_keys=10)

    for i in range(50):
        svc.record(RuntimeError(f'err-{i}'), 'update')

    assert len(svc.active_keys()) <= 10


def test_error_key_is_bounded_and_compact():
    key = AlertService.error_key(RuntimeError('x' * 500), 'update')

    assert key.startswith('update:RuntimeError:')
    assert len(key) < 200


def test_error_key_handles_none():
    assert AlertService.error_key(None, 'update').startswith('update:UnknownError:')
