# Phase 1 — Critical Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the P0 defects that corrupt notifications, leak cross-school schedules, lose user settings, block the event loop and crash ordinary user flows.

**Architecture:** Targeted, backward-compatible edits to existing modules. The exchange-detector cache gains a date dimension; the schedule cache key gains a school dimension; user updates merge instead of whitelisting; synchronous exchange work moves off the event loop. No new subsystems.

**Tech Stack:** Python 3.11, python-telegram-bot 20.7, pytest 7.4 + pytest-asyncio (`asyncio_mode = auto`), ruff.

**Spec:** `docs/superpowers/specs/2026-09-11-quality-and-features-design.md`

## Global Constraints

- Python 3.11+, ruff `line-length = 120`, `target-version = "py311"`.
- Run lint with `.venv/bin/ruff check .` and tests with `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q`.
- Baseline is **64 passing tests**; every task must leave the suite green and add at least one regression test for the bug it fixes.
- Commit style follows `git log`: `Fix: ...`, `Tests: ...`, `P2: ...`.
- Use `pytz` timezone via `config.config.get_timezone()`; never a naive `datetime.now()` for schedule data.
- Do not introduce new third-party dependencies.
- Russian is used for all user-facing strings and code comments in this repo.

---

### Task 1: `set_user_school` preserves the whole user document

**Files:**
- Modify: `services/user_service.py:18-48`
- Test: `tests/test_user_service.py` (create)

**Interfaces:**
- Consumes: `FileDB` (`database/file_db.py`), `UserService(db)`.
- Produces: `UserService.set_user_school(user_id: int, school_id: str) -> bool` — merges into the existing document, preserving `notification_settings` and any other fields; returns `False` for unknown/inactive schools.

- [ ] **Step 1: Write the failing test**

Create `tests/test_user_service.py`:

```python
# tests/test_user_service.py
"""Юнит-тесты UserService: смена школы не теряет настройки."""
import os
import tempfile

from database.file_db import FileDB
from services.user_service import UserService


def _service():
    d = tempfile.mkdtemp()
    return UserService(FileDB(os.path.join(d, 'database.json')))


def test_set_user_school_keeps_notification_settings():
    us = _service()
    us.set_user_notification_settings(1, False, 'school_133')
    assert us.set_user_school(1, 'school_181') is True
    # Настройка для прежней школы должна сохраниться
    assert us.get_user_notification_settings(1, 'school_133') is False
    assert us.get_user_school(1) == 'school_181'


def test_set_user_school_rejects_unknown():
    us = _service()
    assert us.set_user_school(1, 'no_such_school') is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_user_service.py -q`
Expected: FAIL on `test_set_user_school_keeps_notification_settings` — the `notification_settings` key is dropped, so `get_user_notification_settings` falls back to `True`, not `False`.

- [ ] **Step 3: Rewrite the method to merge**

Replace the body of `set_user_school` (`services/user_service.py:18-48`) with:

```python
    def set_user_school(self, user_id: int, school_id: str) -> bool:
        """Устанавливает школу для пользователя, сохраняя остальные поля.

        Раньше документ пересобирался по white-list (user_id, current_school,
        school_classes, created_at), из-за чего терялись notification_settings
        и любые будущие поля. Теперь — merge поверх существующего документа.
        """
        from config.schools import SCHOOLS_CONFIG
        school = SCHOOLS_CONFIG.get(school_id)
        if not school or not school.get('active', True):
            return False

        user = self.users_collection.find_one({'user_id': user_id})
        if user:
            user_data = user.copy()
        else:
            user_data = {
                'user_id': user_id,
                'school_classes': {},
                'created_at': datetime.now().isoformat(),
            }

        user_data['current_school'] = school_id
        user_data['updated_at'] = datetime.now().isoformat()

        self.users_collection.update_one(
            {'user_id': user_id},
            user_data,
            upsert=True
        )
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_user_service.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add services/user_service.py tests/test_user_service.py
git commit -m "Fix: set_user_school preserves notification_settings and other fields"
```

---

### Task 2: Fix `KeyError` on long teacher-search input

**Files:**
- Modify: `handlers/common/class_schedule.py:17-25`
- Test: `tests/test_class_schedule_search.py` (create)

**Interfaces:**
- Consumes: `class_schedule_handler(update, context)`.
- Produces: no API change; the over-length guard must remove whichever `waiting_for_*` flag is present without raising.

- [ ] **Step 1: Write the failing test**

Create `tests/test_class_schedule_search.py`:

```python
# tests/test_class_schedule_search.py
"""Регрессия: длинный запрос в поиске учителя не падает с KeyError."""
from types import SimpleNamespace

from handlers.common.class_schedule import class_schedule_handler


async def test_long_teacher_search_does_not_keyerror():
    replies = []

    async def reply_text(text, **kwargs):
        replies.append(text)

    message = SimpleNamespace(text='x' * 81, reply_text=reply_text)
    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), message=message)
    context = SimpleNamespace(
        bot_data={},
        user_data={'waiting_for_teacher_search': True},
    )

    await class_schedule_handler(update, context)

    assert any('Слишком длинный' in r for r in replies)
    assert 'waiting_for_teacher_search' not in context.user_data
    assert 'waiting_for_room_search' not in context.user_data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_class_schedule_search.py -q`
Expected: FAIL with `KeyError: 'waiting_for_room_search'`.

- [ ] **Step 3: Use `.pop` for both flags**

Replace `handlers/common/class_schedule.py:20-21`:

```python
        del context.user_data['waiting_for_room_search']
        context.user_data.pop('waiting_for_teacher_search', None)
```

with:

```python
        context.user_data.pop('waiting_for_room_search', None)
        context.user_data.pop('waiting_for_teacher_search', None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_class_schedule_search.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add handlers/common/class_schedule.py tests/test_class_schedule_search.py
git commit -m "Fix: long teacher search no longer raises KeyError"
```

---

### Task 3: `entity_menu.search_results` must not touch `update.message` on callbacks

**Files:**
- Modify: `handlers/common/entity_menu.py:345-346`
- Test: `tests/test_entity_menu_state.py` (create)

**Interfaces:**
- Consumes: `EntityMenuHandler(EntityConfig(...))`, `EntityMenuHandler.search_results(update, context, search_query, page=0)`.
- Produces: no API change; the missing-`state_service` branch uses `_edit_or_reply` so callback updates work.

- [ ] **Step 1: Write the failing test**

Create `tests/test_entity_menu_state.py`:

```python
# tests/test_entity_menu_state.py
"""Регрессия: search_results на callback не дёргает None.message."""
from types import SimpleNamespace

from handlers.common.entity_menu import EntityConfig, EntityMenuHandler


class _FakeQuery:
    def __init__(self):
        self.edits = []

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)


class _StubService:
    def __init__(self, school_data):
        pass

    def search_teachers(self, query):
        return ['Иванов И.']


def _handler():
    return EntityMenuHandler(EntityConfig(
        entity='teacher',
        label_singular='преподаватель',
        label_plural='преподавателей',
        icon='👨‍🏫',
        menu_title='Поиск преподавателя',
        search_input_hint='Введите фамилию',
        search_example='Иванов',
        empty_data_msg='нет',
        button_truncate=20,
        state_full_key='teachers',
        state_search_key='search_teachers',
        search_query_key='teacher_search_query',
        service_factory=_StubService,
        get_all_method='get_available_teachers',
        search_method='search_teachers',
    ))


async def test_search_results_callback_without_state_service():
    query = _FakeQuery()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        callback_query=query,
        message=None,
    )
    context = SimpleNamespace(
        bot_data={
            'user_service': SimpleNamespace(get_user_school=lambda uid: 'school_133'),
            'schools_data': {'school_133': {'TEACHERS': {}}},
            'state_service': None,
        },
        user_data={},
    )

    await _handler().search_results(update, context, 'Иванов', 0)

    assert query.edits
    assert 'не доступен' in query.edits[-1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_entity_menu_state.py -q`
Expected: FAIL with `AttributeError: 'NoneType' object has no attribute 'reply_text'`.

- [ ] **Step 3: Route through `_edit_or_reply`**

Replace `handlers/common/entity_menu.py:345-346`:

```python
            if not state_service:
                return await update.message.reply_text("❌ Сервис временно не доступен")
```

with:

```python
            if not state_service:
                return await self._edit_or_reply(update, context, "❌ Сервис временно не доступен")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_entity_menu_state.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add handlers/common/entity_menu.py tests/test_entity_menu_state.py
git commit -m "Fix: entity search_results works on callback updates"
```

---

### Task 4: Isolate the schedule cache by school

**Files:**
- Modify: `services/schedule_service.py:10-74`
- Modify: `handlers/callbacks/class_callbacks.py:70`
- Modify: `handlers/common/class_schedule.py:85`
- Modify: `handlers/common/callback_handler.py:106`
- Modify: `handlers/common/callback_handler.py:259`
- Modify: `handlers/common/week_command.py:15`
- Test: `tests/test_schedule_cache.py` (create)

**Interfaces:**
- Consumes: `CacheService`, `ScheduleService(school_data, cache_service=None, school_id="")`.
- Produces: `ScheduleService.school_id: str`; `ScheduleService._cache_key(kind: str, class_name: str, date: datetime) -> str`. All cache keys are namespaced `{school_id}:{kind}:{class_name}:{YYYYMMDD}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_schedule_cache.py`:

```python
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
    calls = []
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_schedule_cache.py -q`
Expected: FAIL — `ScheduleService.__init__` rejects the third positional argument / `_cache_key` does not exist.

- [ ] **Step 3: Add `school_id` and `_cache_key`, use it in all three getters**

Replace `services/schedule_service.py:10-12`:

```python
    def __init__(self, school_data: dict, cache_service=None):
        super().__init__(school_data)
        self.cache_service = cache_service
```

with:

```python
    def __init__(self, school_data: dict, cache_service=None, school_id: str = ""):
        super().__init__(school_data)
        self.cache_service = cache_service
        self.school_id = school_id

    def _cache_key(self, kind: str, class_name: str, date: datetime) -> str:
        """Ключ кэша с префиксом школы — иначе классы-тёзки (5и, 8б) в разных
        школах перетирали бы друг друга в общем CacheService."""
        return f"{self.school_id}:{kind}:{class_name}:{date.strftime('%Y%m%d')}"
```

Replace the cache-key lines in the three getters:
- `get_class_schedule_today`: both occurrences of
  `cache_key = f"today_{class_name}_{datetime.now(self.moscow_tz).strftime('%Y%m%d')}"`
  become `cache_key = self._cache_key("today", class_name, datetime.now(self.moscow_tz))`
- `get_class_schedule_tomorrow`: both occurrences of
  `cache_key = f"tomorrow_{class_name}_{tomorrow.strftime('%Y%m%d')}"`
  become `cache_key = self._cache_key("tomorrow", class_name, tomorrow)`
- `get_class_schedule_week`: both occurrences of
  `cache_key = f"week_{class_name}_{current_monday.strftime('%Y%m%d')}"`
  become `cache_key = self._cache_key("week", class_name, current_monday)`

- [ ] **Step 4: Pass `school_id` at every construction site**

Apply these edits:

`handlers/callbacks/class_callbacks.py:70`:
```python
            schedule_service = ScheduleService(school_data, cache_service, current_school_id)
```

`handlers/common/class_schedule.py:85`:
```python
    schedule_service = ScheduleService(school_data, school_id=current_school_id)
```

`handlers/common/callback_handler.py:106` and `:259` (both occurrences):
```python
        schedule_service = ScheduleService(school_data, school_id=current_school_id)
```

`handlers/common/week_command.py:15`:
```python
    schedule_service = ScheduleService(school_data, school_id=context.current_school_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_schedule_cache.py -q`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the full suite to catch signature regressions**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q`
Expected: PASS (all tests, now 68).

- [ ] **Step 7: Commit**

```bash
git add services/schedule_service.py handlers/callbacks/class_callbacks.py handlers/common/class_schedule.py handlers/common/callback_handler.py handlers/common/week_command.py tests/test_schedule_cache.py
git commit -m "Fix: scope schedule cache keys by school_id"
```

---

### Task 5: Date-scoped, atomic exchange cache

**Files:**
- Modify: `services/exchange_detector.py:1-103`
- Test: `tests/test_exchange_detector_dates.py` (create)

**Interfaces:**
- Consumes: `ExchangeDetector`, `detect_exchanges(school_id, school_data, date, persist=True)`.
- Produces:
  - `previous_schedules: dict[str, dict[str, dict]]` shaped `{school_id: {date_str: {class_name: {lesson: exchange}}}}`.
  - `detect_exchanges(school_id: str, school_data: dict, date: datetime, persist: bool = True) -> list[dict]` — when `persist=False` it does not touch disk.
  - `save_cache() -> None` — prunes dates older than 3 days and writes atomically (temp + `os.replace`).
  - `load_cache() -> None` — discards legacy flat caches.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_exchange_detector_dates.py`:

```python
# tests/test_exchange_detector_dates.py
"""Регрессии: кэш замен разделён по датам, запись атомарна, persist управляем."""
import json
import logging
import os
from datetime import datetime, timedelta

import pytz

from services.exchange_detector import ExchangeDetector

TZ = pytz.timezone('Asia/Yekaterinburg')


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_exchange_detector_dates.py -q`
Expected: FAIL — `detect_exchanges` has no `persist` parameter and stores state flat by school.

- [ ] **Step 3: Implement date scoping, legacy reset, atomic save and pruning**

In `services/exchange_detector.py`:

Change the import line `from datetime import datetime` to:
```python
from datetime import datetime, timedelta
```

Replace `load_cache` (`services/exchange_detector.py:28-39`) with:
```python
    def load_cache(self):
        """Загружает кэш замен. Старый (плоский) формат сбрасывается."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, encoding='utf-8') as f:
                    data = json.load(f)
                if self._is_legacy_cache(data):
                    self.logger.warning(
                        "Обнаружен старый формат кэша замен — сбрасываю (нужен сброс после смены схемы)")
                    self.previous_schedules = {}
                else:
                    self.previous_schedules = data
                    self.logger.info(
                        f"Загружен кэш замен из {self.cache_file}, школ: {len(self.previous_schedules)}")
            else:
                self.logger.info("Файл кэша замен не найден, используется пустой кэш")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки кэша замен: {e}")
            self.previous_schedules = {}

    @staticmethod
    def _is_legacy_cache(data: dict) -> bool:
        """True, если структура не соответствует {school: {date: {...}}}."""
        import re
        date_re = re.compile(r'^\d{2}\.\d{2}\.\d{4}$')
        if not isinstance(data, dict):
            return True
        for _school, by_date in data.items():
            if not isinstance(by_date, dict):
                return True
            for key in by_date:
                if not date_re.match(str(key)):
                    return True
        return False
```

Replace `save_cache` (`:41-51`) with:
```python
    def save_cache(self):
        """Атомарно сохраняет кэш; даты старше 3 суток удаляются."""
        try:
            self._prune_old_dates()
            os.makedirs(os.path.dirname(self.cache_file) or '.', exist_ok=True)
            tmp = f"{self.cache_file}.tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.previous_schedules, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.cache_file)
            self.logger.info(f"Кэш замен сохранен в {self.cache_file}")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения кэша замен: {e}")

    def _prune_old_dates(self):
        """Удаляет даты старше 3 суток, чтобы кэш не рос бесконечно."""
        cutoff = datetime.now(self.moscow_tz).date() - timedelta(days=3)
        for school_id in list(self.previous_schedules.keys()):
            by_date = self.previous_schedules[school_id]
            for date_str in list(by_date.keys()):
                try:
                    d = datetime.strptime(date_str, '%d.%m.%Y').date()
                except ValueError:
                    del by_date[date_str]
                    continue
                if d < cutoff:
                    del by_date[date_str]
            if not by_date:
                del self.previous_schedules[school_id]
```

Replace the signature and body of `detect_exchanges` (`:64-103`) with:
```python
    def detect_exchanges(self, school_id: str, school_data: dict, date: datetime,
                         persist: bool = True) -> list[dict]:
        """
        Обнаруживает новые замены для всех классов школы на конкретную дату.
        Состояние хранится отдельно для каждой даты, иначе проверка «завтра»
        перетирала бы baseline «сегодня». persist=False — не писать на диск
        (вызывающий делает один общий save_cache за цикл).
        """
        try:
            date_str = date.strftime('%d.%m.%Y')
            self.logger.info(f"Начало обнаружения замен для школы {school_id} на дату {date_str}")
            current_exchanges = self._get_current_exchanges(school_data, date)
            by_date = self.previous_schedules.get(school_id, {})
            previous_exchanges = by_date.get(date_str, {})

            self.logger.info(f"Найдено {len(current_exchanges)} классов с текущими заменами")

            new_exchanges = []
            for class_name, current_class_exchanges in current_exchanges.items():
                previous_class_exchanges = previous_exchanges.get(class_name, {})
                class_new_exchanges = self._compare_class_exchanges(
                    class_name, previous_class_exchanges, current_class_exchanges,
                    school_data, date
                )
                new_exchanges.extend(class_new_exchanges)

            # Сохраняем текущее состояние только для этой даты
            by_date[date_str] = current_exchanges
            self.previous_schedules[school_id] = by_date

            if persist:
                self.save_cache()

            self.logger.info(f"Обнаружено {len(new_exchanges)} новых замен всего для школы {school_id}")
            return new_exchanges

        except Exception as e:
            self.logger.error(f"Error detecting exchanges for school {school_id}: {e}")
            return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_exchange_detector_dates.py tests/test_exchange_detector.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add services/exchange_detector.py tests/test_exchange_detector_dates.py
git commit -m "Fix: date-scope exchange detector cache with atomic writes"
```

---

### Task 6: Offload exchange detection and flush the cache once per cycle

**Files:**
- Modify: `core/background_updater.py:198-266`
- Test: `tests/test_background_updater_exchanges.py` (create)

**Interfaces:**
- Consumes: `BackgroundUpdater(application)`, `_check_exchange_updates(old_schools_data, new_schools_data)`, `ExchangeDetector.detect_exchanges(..., persist=False)`, `ExchangeDetector.save_cache()`.
- Produces: `_check_exchange_updates` calls `detect_exchanges` via `asyncio.to_thread` with `persist=False` and calls `save_cache()` exactly once at the end; `log_update_activity` runs via `asyncio.to_thread`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_background_updater_exchanges.py`:

```python
# tests/test_background_updater_exchanges.py
"""Регрессия: детектор замен не пишет кэш на каждый вызов и не блокирует loop."""
from types import SimpleNamespace

import pytz

from core.background_updater import BackgroundUpdater


class _FakeDetector:
    def __init__(self):
        self.calls = 0
        self.saved = 0
        self.moscow_tz = pytz.timezone('Asia/Yekaterinburg')

    def detect_exchanges(self, school_id, school_data, date, persist=True):
        self.calls += 1
        assert persist is False, "цикл должен сохранять кэш один раз в конце"
        return []

    def save_cache(self):
        self.saved += 1


async def test_check_exchange_updates_flushes_once(monkeypatch):
    app = SimpleNamespace(bot_data={}, bot=None)
    updater = BackgroundUpdater(app)
    detector = _FakeDetector()
    app.bot_data['exchange_detector'] = detector
    app.bot_data['notification_service'] = SimpleNamespace()
    monkeypatch.setattr(updater, 'log_update_activity', lambda message: None)

    await updater._check_exchange_updates({}, {'school_133': {'CLASSES': {}}})

    # сегодня + завтра
    assert detector.calls == 2
    # один общий flush за цикл, а не запись на каждый вызов
    assert detector.saved == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_background_updater_exchanges.py -q`
Expected: FAIL — `saved == 0` (or an assertion about `persist`).

- [ ] **Step 3: Apply the edits in `_check_exchange_updates`**

In `core/background_updater.py`:

Replace line `:232`:
```python
                        new_exchanges = exchange_detector.detect_exchanges(school_id, school_data, today)
```
with:
```python
                        new_exchanges = await asyncio.to_thread(
                            exchange_detector.detect_exchanges, school_id, school_data, today, False
                        )
```

Insert a single cache flush **outside** the `for today in dates:` loop (so it runs once per cycle after both dates are processed) but **inside** the outer `try`, i.e. after the loop's last line (`:263`, the `self.logger.error(...)` inside the per-school `except`) and before the outer `except Exception as e:` at `:265`. Add this block, matching the surrounding 8-space indentation:

```python
            # Один общий flush кэша замен за цикл (а не запись на каждую школу/дату)
            try:
                await asyncio.to_thread(exchange_detector.save_cache)
            except Exception as e:
                self.logger.error(f"Ошибка сохранения кэша замен: {e}")
```

The resulting structure is:

```python
            for today in dates:
                for school_id, school_data in new_schools_data.items():
                    ...
            # <-- flush here, still inside the outer try, outside both loops
        except Exception as e:
            ...
```

Replace the synchronous write inside `log_update_activity` (`:189-196`) so the caller can offload it — keep the method synchronous, but change its call site at `:260` from:
```python
                                self.log_update_activity(f"Отправлено {len(class_exchanges)} уведомлений для класса {class_name} в школе {school_id} на {date_str}, результат: {result}")
```
to:
```python
                                await asyncio.to_thread(
                                    self.log_update_activity,
                                    f"Отправлено {len(class_exchanges)} уведомлений для класса {class_name} в школе {school_id} на {date_str}, результат: {result}",
                                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_background_updater_exchanges.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add core/background_updater.py tests/test_background_updater_exchanges.py
git commit -m "Fix: offload exchange detection and flush exchange cache once per cycle"
```

---

### Task 7: Class-list pagination keeps its schedule type

**Files:**
- Modify: `handlers/common/callback_handler.py:291-301` and add `parse_all_classes_page`
- Modify: `handlers/callbacks/navigation_callbacks.py:89-100`
- Test: `tests/test_all_classes_pagination.py` (create)

**Interfaces:**
- Consumes: `parse_all_classes_page(callback_data: str)`, `handle_show_all_classes(update, context, schedule_type, page)`.
- Produces: `parse_all_classes_page(callback_data: str) -> tuple[str, int] | None` parsing `all_classes_page_{today|tomorrow|week}_{page}`; pagination buttons carry the schedule type.

- [ ] **Step 1: Write the failing test**

Create `tests/test_all_classes_pagination.py`:

```python
# tests/test_all_classes_pagination.py
"""Регрессия: пагинация «Все классы» сохраняет тип расписания."""
from handlers.common.callback_handler import parse_all_classes_page


def test_parse_valid():
    assert parse_all_classes_page('all_classes_page_week_2') == ('week', 2)
    assert parse_all_classes_page('all_classes_page_today_0') == ('today', 0)


def test_parse_invalid():
    assert parse_all_classes_page('all_classes_page_2') is None
    assert parse_all_classes_page('all_classes_page_week_x') is None
    assert parse_all_classes_page('show_all_week') is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_all_classes_pagination.py -q`
Expected: FAIL with `ImportError: cannot import name 'parse_all_classes_page'`.

- [ ] **Step 3: Add the parser and encode the type in the buttons**

Add this function near the top of `handlers/common/callback_handler.py` (after the imports, before `callback_handler`):

```python
def parse_all_classes_page(callback_data: str):
    """Разбирает 'all_classes_page_{type}_{page}' -> (schedule_type, page).

    Раньше пагинация теряла тип расписания, и после первой страницы
    список классов молча переключался на «сегодня». Теперь тип кодируется
    в callback_data.
    """
    prefix = 'all_classes_page_'
    if not callback_data.startswith(prefix):
        return None
    rest = callback_data[len(prefix):]
    schedule_type, sep, page_str = rest.rpartition('_')
    if not sep or schedule_type not in ('today', 'tomorrow', 'week'):
        return None
    try:
        return schedule_type, int(page_str)
    except ValueError:
        return None
```

In `handle_show_all_classes`, replace the pagination button lines (`:296` and `:299`):
```python
            pagination_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"all_classes_page_{page-1}"))
```
```python
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"all_classes_page_{page+1}"))
```
with:
```python
            pagination_buttons.append(InlineKeyboardButton(
                "◀️ Назад", callback_data=f"all_classes_page_{back_schedule}_{page-1}"))
```
```python
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton(
                "Вперёд ▶️", callback_data=f"all_classes_page_{back_schedule}_{page+1}"))
```

Note: `back_schedule` is defined at `:304`; move its definition above the pagination block so it is available. Replace the line `back_schedule = schedule_type or "today"` position — define it right after `page, classes_on_page = paginate(...)` (`:268`), and remove the later duplicate at `:304`.

- [ ] **Step 4: Update the navigation handler**

Replace `handlers/callbacks/navigation_callbacks.py:89-100`:

```python
    async def _handle_show_all_classes(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает показ всех классов"""
        from handlers.common.callback_handler import handle_show_all_classes
        try:
            if callback_data.startswith("all_classes_page_"):
                page = int(callback_data.replace("all_classes_page_", ""))
                await handle_show_all_classes(update, context, None, page)
            else:
                schedule_type = callback_data.replace("show_all_", "")
                await handle_show_all_classes(update, context, schedule_type, 0)
        except ValueError:
            await update.callback_query.answer("❌ Ошибка страницы")
```

with:

```python
    async def _handle_show_all_classes(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает показ всех классов (с сохранением типа расписания)."""
        from handlers.common.callback_handler import (
            handle_show_all_classes,
            parse_all_classes_page,
        )
        if callback_data.startswith("all_classes_page_"):
            parsed = parse_all_classes_page(callback_data)
            if parsed is None:
                await update.callback_query.answer("❌ Ошибка страницы")
                return
            schedule_type, page = parsed
        else:
            schedule_type = callback_data.replace("show_all_", "")
            page = 0
        await handle_show_all_classes(update, context, schedule_type, page)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_all_classes_pagination.py tests/test_callback_router.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add handlers/common/callback_handler.py handlers/callbacks/navigation_callbacks.py tests/test_all_classes_pagination.py
git commit -m "Fix: class-list pagination preserves schedule type"
```

---

### Task 8: Validate school selection and reset search state

**Files:**
- Modify: `handlers/schools/school_selection.py:73-97`
- Test: `tests/test_school_selection.py` (create)

**Interfaces:**
- Consumes: `handle_school_selection(update, context, school_id)`, `UserService.set_user_school(...) -> bool`, `clear_search_flags(context)`.
- Produces: on failure the query is answered and an error message is edited in; on success search flags and `class_digit` are cleared before showing the main menu.

- [ ] **Step 1: Write the failing test**

Create `tests/test_school_selection.py`:

```python
# tests/test_school_selection.py
"""Регрессия: выбор несуществующей школы не показывает успех и чистит флаги."""
from types import SimpleNamespace

import handlers.common.main_menu as main_menu_module
from handlers.schools import school_selection


class _Query:
    def __init__(self):
        self.answers = []
        self.edits = []

    async def answer(self, *args, **kwargs):
        self.answers.append(args[0] if args else '')

    async def edit_message_text(self, text, **kwargs):
        self.edits.append(text)


def _update(query):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        callback_query=query,
        message=None,
    )


async def test_invalid_school(monkeypatch):
    called = {'main': False}

    async def fake_main(update, context):
        called['main'] = True

    monkeypatch.setattr(main_menu_module, 'main_menu_handler', fake_main)

    query = _Query()
    user_service = SimpleNamespace(set_user_school=lambda uid, sid: False)
    context = SimpleNamespace(
        bot_data={'user_service': user_service},
        user_data={'waiting_for_teacher_search': True, 'class_digit': '5'},
    )

    await school_selection.handle_school_selection(_update(query), context, 'no_such')

    assert called['main'] is False
    assert any('недоступна' in e for e in query.edits)


async def test_valid_school_clears_flags(monkeypatch):
    called = {'main': False}

    async def fake_main(update, context):
        called['main'] = True

    monkeypatch.setattr(main_menu_module, 'main_menu_handler', fake_main)

    query = _Query()
    user_service = SimpleNamespace(set_user_school=lambda uid, sid: True)
    context = SimpleNamespace(
        bot_data={'user_service': user_service},
        user_data={'waiting_for_teacher_search': True, 'class_digit': '5'},
    )

    await school_selection.handle_school_selection(_update(query), context, 'school_181')

    assert called['main'] is True
    assert 'waiting_for_teacher_search' not in context.user_data
    assert 'class_digit' not in context.user_data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_school_selection.py -q`
Expected: FAIL — the invalid-school case still calls `main_menu_handler`, and the teacher flag is not cleared.

- [ ] **Step 3: Validate the result and clear flags**

In `handlers/schools/school_selection.py`, add the import at the top:
```python
from handlers.common.messaging import clear_search_flags
```

Replace `handlers/schools/school_selection.py:85-90`:
```python
    # Сохраняем выбранную школу для пользователя
    user_service.set_user_school(user_id, school_id)

    # Сбрасываем выбранную цифру класса — иначе при новой школе останется старый
    # class_digit и список букв может оказаться пустым/чужим
    context.user_data.pop('class_digit', None)
```

with:
```python
    # Сохраняем выбранную школу для пользователя
    if not user_service.set_user_school(user_id, school_id):
        await query.edit_message_text("❌ Эта школа недоступна. Выберите другую.")
        return

    # Сбрасываем залипшие флаги поиска и выбранную цифру класса — иначе при
    # новой школе останется старый class_digit/поиск
    clear_search_flags(context)
    context.user_data.pop('class_digit', None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_school_selection.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add handlers/schools/school_selection.py tests/test_school_selection.py
git commit -m "Fix: reject invalid school selection and reset search flags"
```

---

### Task 9: Use the shared generic error message in the global handler

This is a pure refactor: `bot.py:195` and `GENERIC_ERROR_MSG` already contain the
identical string today. The test is a characterization test that must pass both
before and after; its value is locking the wording and proving the refactor is
behavior-preserving. Do not change the user-visible text.

**Files:**
- Modify: `bot.py` (imports and line 194-196)
- Test: `tests/test_error_handler.py` (create)

**Interfaces:**
- Consumes: `handlers.common.messaging.GENERIC_ERROR_MSG`, `ScheduleBot.error_handler(update, context)`.
- Produces: the global error handler replies with `GENERIC_ERROR_MSG`; no wording change.

- [ ] **Step 1: Write the characterization test**

Create `tests/test_error_handler.py`:

```python
# tests/test_error_handler.py
"""Глобальный обработчик ошибок отдаёт общий безопасный текст."""
import logging
from types import SimpleNamespace

from bot import ScheduleBot
from handlers.common.messaging import GENERIC_ERROR_MSG


async def test_error_handler_uses_generic_message():
    bot = ScheduleBot.__new__(ScheduleBot)
    bot.logger = logging.getLogger('test')

    replies = []

    async def reply_text(text, **kwargs):
        replies.append(text)

    update = SimpleNamespace(
        effective_message=SimpleNamespace(reply_text=reply_text))
    context = SimpleNamespace(error=RuntimeError('boom'))

    await bot.error_handler(update, context)

    assert replies == [GENERIC_ERROR_MSG]
```

- [ ] **Step 2: Run test to confirm it already passes (characterization)**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_error_handler.py -q`
Expected: PASS. This confirms the current behavior is the intended wording;
the next step makes the source reference the constant so future edits cannot drift.

- [ ] **Step 3: Import and use the constant**

In `bot.py`, add to the imports:
```python
from handlers.common.messaging import GENERIC_ERROR_MSG
```

Replace `bot.py:194-196`:
```python
                await update.effective_message.reply_text(
                    "❌ Произошла непредвиденная ошибка. Попробуйте позже."
                )
```
with:
```python
                await update.effective_message.reply_text(GENERIC_ERROR_MSG)
```

- [ ] **Step 4: Run test to verify it still passes**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_error_handler.py -q`
Expected: PASS (behavior preserved).

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_error_handler.py
git commit -m "P2: use shared GENERIC_ERROR_MSG in global error handler"
```

---

### Task 10: Phase 1 verification and docs sync

**Files:**
- Modify: `roadmap.md`
- Modify: `CHANGELOG.md`
- Modify: `README.md` (test count only)

**Interfaces:**
- Consumes: all Phase 1 changes.
- Produces: green lint/test run and updated project docs.

- [ ] **Step 1: Run the full test suite**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q`
Expected: PASS (all tests; baseline 64 + new regression tests).

- [ ] **Step 2: Run the linter**

Run: `.venv/bin/ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3: Update `roadmap.md`**

Move the completed P0 items out of the roadmap into `CHANGELOG.md` under a new `### Фаза 1 — критические исправления (P0)` heading, and remove from `roadmap.md` any entries now done. Keep the remaining Phase 2-4 items.

- [ ] **Step 4: Update the test count in `README.md`**

Replace the two occurrences of `64` in the test descriptions (`README.md` lines ~19 and ~62) with the actual count reported by Step 1.

- [ ] **Step 5: Commit**

```bash
git add roadmap.md CHANGELOG.md README.md
git commit -m "Docs: sync roadmap/changelog/README after Phase 1 fixes"
```

---

## Self-Review

**Spec coverage:**
- §4.1 date-scoped exchange cache → Task 5 (+ Task 6 flush).
- §4.2 school-scoped schedule cache → Task 4.
- §4.3 preserve user settings → Task 1.
- §4.4 offload blocking I/O → Task 6 (detect + log), Task 5 (atomic save/persist).
- §4.5 pinpoint fixes → Task 2 (KeyError), Task 3 (`update.message`), Task 7 (pagination type), Task 8 (school validation + flags), Task 9 (`GENERIC_ERROR_MSG`).
- §9 testing → every task adds a regression test; Task 10 runs the suite.

**Placeholder scan:** no TBD/TODO; every code step contains full code. Task 9 Step 2 includes an explicit instruction to handle the possibility that the strings already match, rather than leaving it ambiguous.

**Type consistency:** `detect_exchanges(..., persist=False)` is defined in Task 5 and called with `False` in Task 6. `ScheduleService(..., school_id=...)` and `_cache_key` are defined in Task 4 and used only there. `parse_all_classes_page` is defined and consumed in Task 7. `GENERIC_ERROR_MSG` is imported in Task 9. `set_user_school` keeps its `bool` return in Task 1 and is consumed in Task 8.

**Out of scope:** Phase 2 (robustness: partial-load merge, Markdown escaping, RetryAfter, FileDB durability, batch settings), Phase 3 (refactor/quality), Phase 4 (features) get their own plans.
