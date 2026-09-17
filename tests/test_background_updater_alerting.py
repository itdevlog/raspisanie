"""BackgroundUpdater: алерты при повторяющихся ошибках и метрики цикла."""
import logging
from types import SimpleNamespace

from core.background_updater import BackgroundUpdater
from services.alert_service import AlertService
from services.metrics import MetricsService


class _NotificationStub:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def notify_admins(self, context, message, parse_mode='Markdown'):
        self.messages.append(message)


def _make_updater(alert_service=None, metrics=None):
    bot_data = {}
    if alert_service is not None:
        bot_data['alert_service'] = alert_service
    if metrics is not None:
        bot_data['metrics'] = metrics
    app = SimpleNamespace(bot_data=bot_data, bot=SimpleNamespace())
    updater = BackgroundUpdater(app)
    updater.logger = logging.getLogger('test')
    return updater


class _EmptyLoader:
    def load_all_schools_data(self):
        return {}


class _BoomLoader:
    def load_all_schools_data(self):
        raise RuntimeError('school down')


async def test_repeated_background_error_alerts_once():
    alert = AlertService(threshold=3, window_seconds=300, now=lambda: 0.0)
    notifier = _NotificationStub()
    updater = _make_updater(alert_service=alert)
    updater.application.bot_data['notification_service'] = notifier
    updater.notification_service = notifier

    for _ in range(5):
        await updater._alert_repeated_error(RuntimeError('boom'), 'background_update')

    assert len(notifier.messages) == 1
    assert 'RuntimeError' in notifier.messages[0]


async def test_no_data_cycles_notify_admins_once_per_window():
    alert = AlertService(threshold=3, window_seconds=300, now=lambda: 0.0)
    notifier = _NotificationStub()
    updater = _make_updater(alert_service=alert)
    updater.application.bot_data['notification_service'] = notifier
    updater.data_loader = _EmptyLoader()

    for _ in range(5):
        await updater._perform_update_locked()

    # первый сбой уведомил, повторы в окне подавлены
    assert len(notifier.messages) == 1
    assert 'данные школ' in notifier.messages[0]


async def test_error_cycles_notify_admins_once_per_window(monkeypatch):
    alert = AlertService(threshold=3, window_seconds=300, now=lambda: 0.0)
    notifier = _NotificationStub()
    updater = _make_updater(alert_service=alert)
    updater.application.bot_data['notification_service'] = notifier
    updater.data_loader = _BoomLoader()
    monkeypatch.setattr(
        updater, '_get_admin_notification_settings',
        lambda: {'update_notifications': True})

    for _ in range(5):
        await updater._perform_update_locked()

    assert len(notifier.messages) == 1
    assert 'Ошибка автоматического обновления' in notifier.messages[0]


async def test_no_data_notifies_again_after_window():
    clock = {'t': 0.0}
    alert = AlertService(threshold=3, window_seconds=300, now=lambda: clock['t'])
    notifier = _NotificationStub()
    updater = _make_updater(alert_service=alert)
    updater.application.bot_data['notification_service'] = notifier
    updater.data_loader = _EmptyLoader()

    await updater._perform_update_locked()
    clock['t'] = 400.0
    await updater._perform_update_locked()

    assert len(notifier.messages) == 2


async def test_alert_is_noop_without_alert_service():
    notifier = _NotificationStub()
    updater = _make_updater()
    updater.application.bot_data['notification_service'] = notifier
    updater.notification_service = notifier

    await updater._alert_repeated_error(RuntimeError('boom'), 'background_update')

    assert notifier.messages == []


async def test_update_job_increments_cycle_metric_and_logs(caplog):
    metrics = MetricsService()
    updater = _make_updater(metrics=metrics)
    updater.is_running = True

    async def _perform():
        return True

    updater._perform_update = _perform

    with caplog.at_level(logging.INFO, logger='services.metrics'):
        await updater._update_job(None)

    assert metrics.get('update_cycles') == 1
    assert 'update_cycles=1' in caplog.text
