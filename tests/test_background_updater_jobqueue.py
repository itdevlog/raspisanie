# tests/test_background_updater_jobqueue.py
"""Периодические задачи регистрируются в JobQueue, а не в ручных asyncio-циклах."""
import logging
from types import SimpleNamespace

from core.background_updater import BackgroundUpdater


class _FakeJobQueue:
    def __init__(self):
        self.jobs = []

    def run_repeating(self, callback, interval, first, name):
        self.jobs.append({
            'callback': callback,
            'interval': interval,
            'first': first,
            'name': name,
        })


def _updater_with_queue(queue):
    up = BackgroundUpdater.__new__(BackgroundUpdater)
    up.logger = logging.getLogger('test')
    up.application = SimpleNamespace(job_queue=queue, bot_data={}, bot=None)
    up.is_running = False
    up.update_interval = 3600
    return up


def test_start_registers_update_and_reminder_jobs():
    queue = _FakeJobQueue()
    up = _updater_with_queue(queue)

    up.start_periodic_updates()

    assert up.is_running is True
    names = {job['name']: job for job in queue.jobs}
    assert set(names) == {'background_update', 'lesson_reminders'}
    assert names['background_update']['interval'] == 3600
    assert names['background_update']['first'] == 3600
    assert names['lesson_reminders']['interval'] == 60
    assert names['lesson_reminders']['first'] == 60
    assert callable(names['background_update']['callback'])
    assert callable(names['lesson_reminders']['callback'])


def test_start_is_idempotent():
    queue = _FakeJobQueue()
    up = _updater_with_queue(queue)

    up.start_periodic_updates()
    up.start_periodic_updates()

    assert len(queue.jobs) == 2


def test_start_without_job_queue_does_not_mark_running():
    up = BackgroundUpdater.__new__(BackgroundUpdater)
    up.logger = logging.getLogger('test')
    up.application = None
    up.is_running = False
    up.update_interval = 10

    up.start_periodic_updates()

    assert up.is_running is False


async def test_update_job_runs_perform_update():
    queue = _FakeJobQueue()
    up = _updater_with_queue(queue)
    up.start_periodic_updates()
    calls = []

    async def _perform():
        calls.append(1)
        return True

    up._perform_update = _perform

    update_job = next(j for j in queue.jobs if j['name'] == 'background_update')
    await update_job['callback'](None)

    assert calls == [1]


async def test_reminder_job_runs_reminders_and_digests():
    queue = _FakeJobQueue()
    up = _updater_with_queue(queue)
    up.start_periodic_updates()
    calls = []

    async def _reminders():
        calls.append('reminders')

    async def _digests():
        calls.append('digests')

    up._send_reminders = _reminders
    up._send_digests = _digests

    reminder_job = next(j for j in queue.jobs if j['name'] == 'lesson_reminders')
    await reminder_job['callback'](None)

    assert calls == ['reminders', 'digests']


async def test_jobs_noop_when_stopped():
    queue = _FakeJobQueue()
    up = _updater_with_queue(queue)
    up.start_periodic_updates()
    calls = []

    async def _perform():
        calls.append('update')
        return True

    async def _reminders():
        calls.append('reminders')

    async def _digests():
        calls.append('digests')

    up._perform_update = _perform
    up._send_reminders = _reminders
    up._send_digests = _digests

    up.stop()

    for job in queue.jobs:
        await job['callback'](None)

    assert calls == []
