# Phase 4 — Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Deliver the five spec §7 features: replacement-removal notifications, next-week/next-lesson queries, lesson reminders, quiet hours + anti-flood, and teacher/room subscriptions.

**Architecture:** New focused services (`subscription_service.py`, `reminder_service.py`) plus extensions to `ExchangeDetector`, `BaseScheduleService`, and `NotificationService`. The reminder loop reuses the existing asyncio `BackgroundUpdater` pattern instead of PTB `JobQueue`.

**Tech Stack:** Python 3.11, python-telegram-bot 20.7, pytest 7.4, ruff.

**Spec:** `docs/superpowers/specs/2026-09-11-quality-and-features-design.md` (§7)

## Global Constraints

- Python 3.11+, ruff line-length 120.
- Tests: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q`; lint: `.venv/bin/ruff check .`.
- Baseline 112 tests; keep green, add regression tests per task.
- Russian strings/comments. **No new third-party dependencies** (so no APScheduler/JobQueue — reminders run on the existing asyncio loop).
- Commit styles: `Feat: ...`, `P2: ...`, `Docs: ...`.
- Do not break Phase 1-3 contracts.

---

### Task 1: Replacement-removal notifications (symmetric diff)

**Files:**
- Modify: `services/exchange_detector.py`
- Modify: `services/notification_service.py`
- Test: `tests/test_exchange_removed.py` (create)

**Interfaces:**
- `ExchangeDetector._compare_class_exchanges` additionally returns removal events for lessons present in `previous` but absent in `current` (or whose `is_cancelled` flipped back).
- Removal event shape: `{'class_name', 'lesson_num', 'removed': True, 'original_subject', 'timestamp'}`.
- `NotificationService._format_exchange_notification` renders a removal line `↩️ {lesson_num}. {subject} — замена снята`.

- [ ] **Step 1: Write failing test**

Create `tests/test_exchange_removed.py`:

```python
"""Симметричный diff: исчезнувшая замена даёт событие «снята»."""
import logging
from datetime import datetime

import pytz

from services.exchange_detector import ExchangeDetector


def _detector():
    d = ExchangeDetector.__new__(ExchangeDetector)
    d.logger = logging.getLogger('test')
    d.moscow_tz = pytz.timezone('Asia/Yekaterinburg')
    d.previous_schedules = {}
    return d


def test_removed_exchange_is_reported():
    d = _detector()
    date = datetime(2026, 9, 11, 12, 0, tzinfo=d.moscow_tz)
    school = {'SUBJECTS': {'1': 'Математика'}, 'TEACHERS': {}, 'ROOMS': {}}
    previous = {'3': {'lesson_num': '3', 'data': {'s': ['1']}, 'is_cancelled': False,
                      'formatted': {'lesson_num': 3, 'original_subject': 'Урок 3'}}}
    current = {}
    events = d._compare_class_exchanges('5А', previous, current, school, date)
    removals = [e for e in events if e.get('removed')]
    assert len(removals) == 1
    assert removals[0]['lesson_num'] == 3
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_exchange_removed.py -q`
Expected: FAIL — `_compare_class_exchanges` only iterates `current`, so no removal event.

- [ ] **Step 3: Implement**

In `_compare_class_exchanges`, after the additions loop add:

```python
        # Симметричный diff: замены, исчезнувшие из текущего состояния
        for lesson_num, previous_exchange in previous.items():
            if lesson_num in current:
                continue
            formatted = previous_exchange.get('formatted') or {}
            new_exchanges.append({
                'class_name': class_name,
                'lesson_num': int(lesson_num),
                'removed': True,
                'original_subject': formatted.get('original_subject', f'Урок {lesson_num}'),
                'new_subject': '', 'new_teacher': '', 'new_room': '',
                'is_cancelled': False,
                'timestamp': date,
            })
        return new_exchanges
```

When storing state, keep the formatted payload so removals can reference it: in `_get_class_exchanges`, store `'formatted'` lazily is hard; instead in `_compare_class_exchanges` additions, attach the formatted dict onto the current exchange entry before it is persisted. Simplest: have `detect_exchanges` store `current_exchanges` where each lesson entry already includes `'formatted'` (format it during `_get_class_exchanges` using `school_data`/`date`). Adjust `_get_class_exchanges` to accept and store `formatted` via `_format_exchange_for_notification` (guarded). Then removal uses the stored formatted original_subject.

(Keep `_is_exchange_changed` behavior.)

- [ ] **Step 4: Render removals in notifications**

In `_format_exchange_notification`, inside the loop:

```python
            if exchange.get('removed'):
                lesson_line = f"↩️ {lesson_num}. {original_subject} — *замена снята*"
                message.append(lesson_line)
                continue
```

- [ ] **Step 5: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_exchange_removed.py tests/test_exchange_detector.py tests/test_exchange_detector_dates.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/exchange_detector.py services/notification_service.py tests/test_exchange_removed.py
git commit -m "Feat: notify when a replacement is removed"
```

---

### Task 2: Next-week navigation and current/next lesson

**Files:**
- Modify: `services/base_schedule_service.py`
- Modify: `services/schedule_service.py`
- Test: `tests/test_week_offset_next_lesson.py` (create)

**Interfaces:**
- `BaseScheduleService._get_week_schedule(..., week_offset: int = 0)` — offset weeks from current Monday.
- `ScheduleService.get_class_schedule_week(class_name, week_offset: int = 0)`.
- `BaseScheduleService.get_next_lesson(schedule_data: list[dict], date, now=None) -> dict | None` — returns the current-or-next lesson by `LESSON_TIMES`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_week_offset_next_lesson.py`:

```python
from datetime import datetime

import pytz

from services.schedule_service import ScheduleService

TZ = pytz.timezone('Asia/Yekaterinburg')


def _svc():
    school = {
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['09:00', '09:45']},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSONSINDAY': 12,
        'CLASSES': {'c1': '5а'},
        'CLASS_SCHEDULE': {},
        'SUBJECTS': {}, 'TEACHERS': {}, 'ROOMS': {}, 'DAY_NAMES': [],
    }
    return ScheduleService(school, school_id='s')


def test_get_next_lesson_picks_upcoming():
    svc = _svc()
    date = datetime(2026, 9, 11, 8, 30, tzinfo=TZ)  # между уроком 1 и 2
    data = [
        {'lesson_num': 1, 'data': {'s': ['x'], 't': [], 'r': []}, 'has_exchange': False, 'is_cancelled': False},
        {'lesson_num': 2, 'data': {'s': ['y'], 't': [], 'r': []}, 'has_exchange': False, 'is_cancelled': False},
    ]
    nxt = svc.get_next_lesson(data, date, now=date)
    assert nxt is not None
    assert nxt['lesson_num'] == 2


def test_week_schedule_accepts_offset():
    svc = _svc()
    # offset 1 не должен падать и не совпадать с текущей неделей
    out = svc.get_class_schedule_week('5а', week_offset=1)
    assert isinstance(out, str)
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_week_offset_next_lesson.py -q`
Expected: FAIL — no `week_offset`, no `get_next_lesson`.

- [ ] **Step 3: Implement**

`_get_week_schedule`: add `week_offset: int = 0` and compute `current_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)`; header dates derive from it.

`get_next_lesson`:

```python
    def get_next_lesson(self, schedule_data: list[dict], date: datetime, now: datetime | None = None) -> dict | None:
        """Возвращает текущий или следующий урок по времени LESSON_TIMES."""
        if not schedule_data:
            return None
        now = now or datetime.now(self.moscow_tz)
        for lesson in sorted(schedule_data, key=lambda x: x['lesson_num']):
            times = self._get_lesson_times(lesson['lesson_num'])
            if len(times) < 2 or times[0] == '?':
                continue
            try:
                start = now.replace(hour=int(times[0][:2]), minute=int(times[0][3:5]), second=0, microsecond=0)
            except (ValueError, IndexError):
                continue
            end = start.replace(hour=int(times[1][:2]), minute=int(times[1][3:5]))
            if now <= end:
                return lesson
        return None
```

`ScheduleService.get_class_schedule_week(class_name, week_offset=0)` passes offset through.

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_week_offset_next_lesson.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/base_schedule_service.py services/schedule_service.py tests/test_week_offset_next_lesson.py
git commit -m "Feat: week offset and current/next lesson helper"
```

---

### Task 3: Teacher/room subscriptions

**Files:**
- Create: `services/subscription_service.py`
- Modify: `services/notification_service.py`
- Modify: `handlers/common/settings.py` (menu entry point)
- Modify: `handlers/common/entity_menu.py` (subscribe button after opening a teacher/room schedule)
- Test: `tests/test_subscriptions.py` (create)

**Interfaces:**
- `SubscriptionService(db)`: `subscribe(user_id, school_id, kind, name) -> bool`, `unsubscribe(...) -> bool`, `get_subscriptions(user_id, school_id) -> list[tuple[str,str]]`, `get_subscribers(school_id, kind, name) -> list[int]`.
  - `kind` ∈ `{'teacher','room'}`; stored in collection `subscriptions` keyed `{user_id, school_id}` with a list of `{kind, name}`.
- `NotificationService.notify_subscribers(context, school_id, kind, name, text) -> int` — sends to subscribers via `_send_message`.

- [ ] **Step 1: Write failing test**

Create `tests/test_subscriptions.py`:

```python
import os, tempfile

from database.file_db import FileDB
from services.subscription_service import SubscriptionService


def _svc():
    d = tempfile.mkdtemp()
    return SubscriptionService(FileDB(os.path.join(d, 'database.json')))


def test_subscribe_and_get():
    s = _svc()
    assert s.subscribe(1, 'school_133', 'teacher', 'Иванов') is True
    assert s.get_subscriptions(1, 'school_133') == [('teacher', 'Иванов')]
    assert s.get_subscribers('school_133', 'teacher', 'Иванов') == [1]


def test_unsubscribe():
    s = _svc()
    s.subscribe(1, 'school_133', 'room', '101')
    assert s.unsubscribe(1, 'school_133', 'room', '101') is True
    assert s.get_subscriptions(1, 'school_133') == []


def test_idempotent_subscribe():
    s = _svc()
    s.subscribe(1, 'school_133', 'teacher', 'Иванов')
    s.subscribe(1, 'school_133', 'teacher', 'Иванов')
    assert s.get_subscribers('school_133', 'teacher', 'Иванов') == [1]
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_subscriptions.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `SubscriptionService`**

Store one document per user/school: `{'user_id', 'school_id', 'items': [{'kind','name'}]}`. Implement the four methods over `FileDB`. `get_subscribers` scans the collection filtering by school + item membership (acceptable at this scale).

- [ ] **Step 4: Wire notifications (minimal)**

In `NotificationService`, add `notify_subscribers(context, school_id, kind, name, text)` using `_send_message`. Hook it in `BackgroundUpdater._check_exchange_updates`: when a class exchange is detected, if the changed subject's teacher is known, notify teacher/room subscribers. Given complexity, the minimum viable hook: when an exchange for class `C` includes a `new_teacher`/`new_room`, notify subscribers of that teacher/room with the exchange text. Implement `_notify_entity_subscribers` in `BackgroundUpdater` best-effort (wrapped in try/except).

In `entity_menu.select`, after showing a teacher/room schedule, add a button `{p}_subscribe_{schedule_type}_{suffix}` — but keep it simple: add a `🔔 Подписаться` button whose callback calls `SubscriptionService.subscribe`. Register the callback in the router under the teacher/room prefix. (Minimum: a working subscribe/unsubscribe toggle.)

- [ ] **Step 5: Settings UI**

In `settings.py`, show the user's current subscriptions (teacher/room) for the current school with an unsubscribe button. Keep the existing notification toggle.

- [ ] **Step 6: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_subscriptions.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add services/subscription_service.py services/notification_service.py handlers/common/settings.py handlers/common/entity_menu.py handlers/callbacks/*.py core/background_updater.py tests/test_subscriptions.py
git commit -m "Feat: teacher/room subscriptions with notifications"
```

---

### Task 4: Lesson reminders (asyncio loop, no new deps)

**Files:**
- Create: `services/reminder_service.py`
- Modify: `core/background_updater.py` (start reminder loop)
- Modify: `handlers/common/settings.py` (toggle `lesson_reminders`)
- Modify: `services/user_preferences.py` (already stores `lesson_reminders`)
- Test: `tests/test_reminders.py` (create)

**Interfaces:**
- `ReminderService.get_due_reminders(schools_data, now) -> list[tuple[int, str]]` — pure function: for each user with `lesson_reminders` enabled and a saved class, if a lesson starts within the reminder window (e.g. 10 min), return `(user_id, text)`. Sending is driven by a loop.
- `BackgroundUpdater._reminder_loop()` runs every 60s alongside the update loop.

- [ ] **Step 1: Write failing test**

Create `tests/test_reminders.py`:

```python
from datetime import datetime, timedelta

import pytz

from services.reminder_service import ReminderService

TZ = pytz.timezone('Asia/Yekaterinburg')


def test_due_reminder_within_window():
    now = datetime(2026, 9, 11, 7, 55, tzinfo=TZ)
    school_data = {
        'CLASSES': {'c1': '5а'},
        'LESSON_TIMES': {'1': ['08:00', '08:45']},
        'CLASS_SCHEDULE': {'p1': {'c1': {'501': {'s': ['1'], 't': [], 'r': []}}}},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'SUBJECTS': {'1': 'Математика'},
    }
    svc = ReminderService()
    out = svc.get_due_reminders(
        {'school_133': school_data},
        {'user_1': ('school_133', '5а')},
        now=now,
        window_minutes=10,
    )
    assert out and out[0][1].lower().startswith('через')
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_reminders.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

`ReminderService.get_due_reminders(schools_data, user_classes, now, window_minutes=10)` computes the next lesson for each user's class using `LESSON_TIMES` and returns reminder texts. Build the service on `ScheduleService` internally or compute directly from `school_data`.

Wire `BackgroundUpdater._reminder_loop` to gather `(user, class)` from `UserService` + `UserPreferencesService`, call `get_due_reminders`, and `_send_message` each — with 24h dedup keyed by `(user, school, class, lesson, date)`.

Add `lesson_reminders` toggle to `settings.py` (admin? no — all users), reading/writing `UserPreferencesService`.

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_reminders.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/reminder_service.py core/background_updater.py handlers/common/settings.py tests/test_reminders.py
git commit -m "Feat: lesson reminders via asyncio loop"
```

---

### Task 5: Quiet hours and anti-flood

**Files:**
- Modify: `services/notification_service.py`
- Modify: `services/user_preferences.py`
- Modify: `handlers/common/settings.py`
- Test: `tests/test_quiet_hours.py` (create)

**Interfaces:**
- `UserPreferencesService.get_notification_settings` defaults gain `quiet_hours: {'enabled': False, 'start': 22, 'end': 7}`.
- `NotificationService._is_quiet_hours(settings, now) -> bool`.
- `notify_exchange_updates`/reminders skip sending when quiet hours active (but still mark sent).
- Anti-flood: `NotificationService._send_message` gains a per-chat minimum interval (e.g. 0.05s already present); add a simple per-user token bucket `_last_sent_at` to drop sends within 1s of each other.

- [ ] **Step 1: Write failing test**

Create `tests/test_quiet_hours.py`:

```python
from datetime import datetime

import pytz

from services.notification_service import NotificationService

TZ = pytz.timezone('Asia/Yekaterinburg')


def test_quiet_hours_detection():
    svc = NotificationService.__new__(NotificationService)
    settings = {'quiet_hours': {'enabled': True, 'start': 22, 'end': 7}}
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 23, 0, tzinfo=TZ)) is True
    assert svc._is_quiet_hours(settings, datetime(2026, 9, 11, 12, 0, tzinfo=TZ)) is False
    assert svc._is_quiet_hours({'quiet_hours': {'enabled': False}}, datetime(2026, 9, 11, 23, 0, tzinfo=TZ)) is False
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_quiet_hours.py -q`
Expected: FAIL — method missing.

- [ ] **Step 3: Implement**

`_is_quiet_hours(settings, now)`: parse start/end hours; handle wrap-around (start > end). In `notify_exchange_updates`, after computing recipients but before sending, if quiet hours for a user, skip (treat as sent for dedup). Add the settings toggles in `settings.py`.

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_quiet_hours.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/notification_service.py services/user_preferences.py handlers/common/settings.py tests/test_quiet_hours.py
git commit -m "Feat: quiet hours and anti-flood guard"
```

---

### Task 6: Phase 4 docs sync

**Files:** `roadmap.md`, `CHANGELOG.md`, `README.md`, `WIKI.md`.

- [ ] **Step 1:** full suite + ruff; record counts.
- [ ] **Step 2:** add `### Фаза 4 — новый функционал` to CHANGELOG; roadmap marks Phase 4 done; README/WIKI list new commands/features and the test count.
- [ ] **Step 3:** commit `Docs: sync roadmap/changelog/README/WIKI after Phase 4`.

---

## Self-Review

**Spec coverage:** §7.1 reminders → T4; §7.2 subscriptions → T3; §7.3 removal notifications → T1; §7.4 next week/next lesson → T2; §7.5 quiet hours/antiflood → T5.
**Ruling (no new deps):** PTB `JobQueue` requires APScheduler; the no-new-deps Global Constraint wins, so reminders run on the existing asyncio loop. Recorded in the ledger.
**Placeholders:** none; each task carries concrete tests/code. Some features (subscription UI hooks, reminder loop wiring) are described as minimal-viable integration points with exact method names.
**Type consistency:** `SubscriptionService` methods defined+consumed in T3; `get_next_lesson` defined+used in T2; `_is_quiet_hours` defined+used in T5; `get_due_reminders` defined+used in T4.
