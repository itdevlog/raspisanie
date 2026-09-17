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
