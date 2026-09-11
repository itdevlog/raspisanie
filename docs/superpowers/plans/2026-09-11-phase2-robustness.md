# Phase 2 — Robustness & Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Harden the bot's data flow: partial-load resilience, one invalidation path, Markdown safety, Telegram rate-limit handling, durable FileDB writes, batch notification lookups, and DataLoader hygiene.

**Architecture:** Targeted edits to existing services/handlers. A shared `escape_markdown` helper removes duplication; `BackgroundUpdater` gains a lock, a partial-load merge, and a single `_on_data_replaced()` hook reused by admin refreshes; `NotificationService` gains a `RetryAfter`-aware send helper and a settings-aware recipient index; `FileDB` surfaces write failures.

**Tech Stack:** Python 3.11, python-telegram-bot 20.7, pytest 7.4 (`asyncio_mode=auto`), ruff.

**Spec:** `docs/superpowers/specs/2026-09-11-quality-and-features-design.md` (§5)

## Global Constraints

- Python 3.11+, ruff `line-length = 120`, `target-version = "py311"`.
- Tests: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q`; lint: `.venv/bin/ruff check .`.
- Baseline 80 tests; every task must keep the suite green and add ≥1 regression test.
- Commit style follows `git log`: `Fix: ...`, `P2: ...`, `Tests: ...`, `Docs: ...`.
- Russian user-facing strings/comments. No new third-party dependencies.
- Never break the Phase 1 contracts: `detect_exchanges(..., persist=False)`, `ScheduleService(..., school_id=...)`, `parse_all_classes_page`.

---

### Task 1: `FileDB` surfaces write failures and tolerates a bare filename

**Files:**
- Modify: `database/file_db.py`
- Test: `tests/test_file_db.py` (extend)

**Interfaces:**
- Consumes: `FileDB`, `Collection`.
- Produces: `FileDB._save_data() -> bool`; `Collection.insert_one(...) -> bool`; `Collection.update_one(...) -> bool`; `Collection.delete_one(...) -> bool`. All return `False` when the disk write failed.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_file_db.py`:

```python
def test_save_data_returns_true_on_success():
    db_path = _mkdb()
    db = FileDB(db_path)
    assert db._save_data() is True


def test_update_one_returns_false_when_save_fails(monkeypatch):
    db_path = _mkdb()
    db = FileDB(db_path)
    col = db.get_collection('users')
    monkeypatch.setattr(db, '_save_data', lambda: False)
    assert col.update_one({'user_id': 1}, {'user_id': 1, 'name': 'A'}, upsert=True) is False


def test_bare_filename_does_not_crash():
    import tempfile, os
    d = tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        os.chdir(d)
        db = FileDB('database.json')
        col = db.get_collection('users')
        assert col.insert_one({'user_id': 7}) is True
    finally:
        os.chdir(cwd)
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_file_db.py -q`
Expected: FAIL — `_save_data` returns `None`, `update_one` returns `None`.

- [ ] **Step 3: Implement**

In `database/file_db.py`, replace `_save_data` with a bool-returning version:

```python
    def _save_data(self) -> bool:
        """Атомарно сохраняет данные. Возвращает False при ошибке (не глотает её молча)."""
        try:
            dir_name = os.path.dirname(self.db_path) or '.'
            os.makedirs(dir_name, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix='.file_db_tmp_', suffix='.json')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=2, default=self._json_serializer)
                shutil.move(temp_path, self.db_path)
            except Exception:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise
            return True
        except Exception as e:
            logger.error(f"Error saving database: {e}", exc_info=True)
            return False
```

Change `insert_one` to `return self.db._save_data()` (after append), `update_one` to `return self.db._save_data()` on each branch (and `return False` at the end), `delete_one` likewise. Keep signatures `-> bool`.

- [ ] **Step 4: Run tests to verify pass**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_file_db.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add database/file_db.py tests/test_file_db.py
git commit -m "Fix: FileDB surfaces save failures and tolerates bare filename"
```

---

### Task 2: Shared `escape_markdown`; apply at all dynamic-text sites

**Files:**
- Create: `services/text_utils.py`
- Modify: `services/base_schedule_service.py` (`_escape_markdown` delegates)
- Modify: `services/notification_service.py`
- Modify: `handlers/common/entity_menu.py`
- Modify: `handlers/common/school_info.py`
- Modify: `handlers/common/menu_builder.py`
- Test: `tests/test_text_utils.py` (create)

**Interfaces:**
- Produces: `services.text_utils.escape_markdown(text: str) -> str` escaping `_ * [ ] ( ) \`` in legacy Markdown.

- [ ] **Step 1: Write failing test**

Create `tests/test_text_utils.py`:

```python
from services.text_utils import escape_markdown


def test_escapes_legacy_markdown_chars():
    assert escape_markdown('a_b*c[d]e(f)`g`') == r'a\_b\*c\[d\]e\(f\)\`g\`'


def test_empty_string():
    assert escape_markdown('') == ''
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_text_utils.py -q`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create the helper and delegate**

Create `services/text_utils.py`:

```python
# services/text_utils.py
"""Общие текстовые хелперы."""


def escape_markdown(text: str) -> str:
    """Экранирует спецсимволы legacy Markdown (Telegram parse_mode='Markdown').

    Экранируем `*`, `_`, `` ` `` и `[ ] ( )` — без последних сообщение с
    такими символами падает с «Can't parse entities».
    """
    if not text:
        return text
    for ch in ('_', '*', '[', ']', '(', ')', '`'):
        text = text.replace(ch, '\\' + ch)
    return text
```

In `services/base_schedule_service.py`, replace the body of `_escape_markdown` with a delegation:

```python
    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Экранирует спецсимволы legacy Markdown (единый хелпер)."""
        from services.text_utils import escape_markdown
        return escape_markdown(text)
```

- [ ] **Step 4: Apply in `notification_service._format_exchange_notification`**

Add import at top: `from services.text_utils import escape_markdown`. Replace the message construction so dynamic values are escaped:

```python
        message = [
            f"🔄 *{escape_markdown(class_name.upper())} - {day_name}, {date_str}*",
            "",
            "📝 *Новые замены в расписании:*",
            ""
        ]

        for exchange in exchanges:
            lesson_num = exchange.get('lesson_num', '?')
            original_subject = escape_markdown(exchange.get('original_subject', 'Неизвестно'))
            new_subject = escape_markdown(exchange.get('new_subject', ''))
            new_teacher = escape_markdown(exchange.get('new_teacher', ''))
            new_room = escape_markdown(exchange.get('new_room', ''))
            is_cancelled = exchange.get('is_cancelled', False)
            ...
```

(Keep the rest of the loop body identical.)

- [ ] **Step 5: Apply in `entity_menu.search_results`**

Add `from services.text_utils import escape_markdown` to imports. Replace the two interpolations of `search_query`:
- `f"❌ {self.cfg.label_plural.capitalize()} со '{search_query}' не найдены"` → `f"❌ {self.cfg.label_plural.capitalize()} со '{escape_markdown(search_query)}' не найдены"`
- `f"🔍 *Результаты поиска:* '{search_query}'\n\n"` → `f"🔍 *Результаты поиска:* '{escape_markdown(search_query)}'\n\n"`

- [ ] **Step 6: Apply in `school_info.py` and `menu_builder.py`**

`handlers/common/school_info.py`: import `escape_markdown`; wrap `school_name`, `city`, `export_date`, `export_time`, and the homepage URL in the info text. Example:

```python
    info_text = (
        f"🏫 *{escape_markdown(school_name)}*\n"
        f"📍 {escape_markdown(str(city))}\n\n"
        ...
        f"🕒 *Данные обновлены:*\n"
        f"{escape_markdown(str(export_date))} {escape_markdown(str(export_time))}\n\n"
        f"🔗 *Сайт школы:*\n"
        f"{escape_markdown(str(school_data.get('HOMEPAGE_URL', 'Не указан')))}"
    )
```

`handlers/common/menu_builder.py`: import `escape_markdown`; in `build_main_menu_text` wrap `school_name` and `current_class`; in `build_main_menu_keyboard` use the raw class for `callback_data` (do NOT escape callback data) but escape the button label. Minimal required: escape `school_name` and `current_class` in `build_main_menu_text`.

- [ ] **Step 7: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_text_utils.py tests/test_menu_builder.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add services/text_utils.py services/base_schedule_service.py services/notification_service.py handlers/common/entity_menu.py handlers/common/school_info.py handlers/common/menu_builder.py tests/test_text_utils.py
git commit -m "Fix: escape Markdown at dynamic-text sites via shared helper"
```

---

### Task 3: Settings-aware recipient index (drop O(N²) lookups)

**Files:**
- Modify: `services/user_service.py`
- Modify: `services/notification_service.py`
- Test: `tests/test_notification_index.py` (extend)

**Interfaces:**
- Produces: `UserService.get_notification_settings_batch(school_id: str) -> dict[int, bool]` — one scan, `{user_id: enabled}`.
- Modifies: `NotificationService.get_users_for_exchange(school_id, class_name) -> list[int]` returning only users with notifications enabled for this school, using the cached index (which now stores settings).

- [ ] **Step 1: Write failing test**

Add to `tests/test_notification_index.py` (read the existing file first and follow its fixtures). New test:

```python
def test_get_notification_settings_batch():
    from services.user_service import UserService
    from tests.conftest_helpers import make_user_service  # if absent, construct inline
```

If no helper exists, create the service with a temp `FileDB` inline, add three users (one disabled), and assert the batch map. Concretely:

```python
def test_get_notification_settings_batch():
    import os, tempfile
    from database.file_db import FileDB
    from services.user_service import UserService

    d = tempfile.mkdtemp()
    us = UserService(FileDB(os.path.join(d, 'database.json')))
    us.set_user_class(1, '5а', 'school_133')
    us.set_user_class(2, '5а', 'school_133')
    us.set_user_notification_settings(2, False, 'school_133')

    batch = us.get_notification_settings_batch('school_133')
    assert batch[1] is True
    assert batch[2] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_notification_index.py -q`
Expected: FAIL — `AttributeError: 'UserService' object has no attribute 'get_notification_settings_batch'`.

- [ ] **Step 3: Add the batch method**

In `services/user_service.py` add:

```python
    def get_notification_settings_batch(self, school_id: str = None) -> dict:
        """Возвращает {user_id: notifications_enabled} для школы одним проходом.

        Убирает линейный find_one на каждого получателя при массовой рассылке.
        """
        result = {}
        for user in self.users_collection.find({}):
            user_id = user.get('user_id')
            if not user_id:
                continue
            settings = user.get('notification_settings', {}) or {}
            result[user_id] = settings.get(school_id, True) if school_id else True
        return result
```

- [ ] **Step 4: Use the batch map in the notification index**

In `services/notification_service.py`, extend `_build_user_class_index` to also store enabled flags. Replace `_user_class_index: dict[tuple, list[int]]` with `dict[tuple, list[tuple[int, bool]]]` and add a `_settings_batch` dict. Simpler: keep the index as `list[int]` and add a per-index settings map built alongside. Implement:

```python
    def _build_user_class_index(self, user_service, school_id: str):
        try:
            users_collection = user_service.db.get_collection('users')
            idx: dict[tuple, list[int]] = {}
            self._settings_for_school = {}
            for user_data in users_collection.find():
                user_id = user_data.get('user_id')
                if not user_id:
                    continue
                self._settings_for_school[user_id] = (user_data.get('notification_settings') or {}).get(school_id, True)
                school_classes = user_data.get('school_classes') or {}
                class_name = school_classes.get(school_id)
                if class_name:
                    key = (school_id, class_name.lower())
                    idx.setdefault(key, []).append(user_id)
            self._user_class_index = idx
            self._index_loaded_for_school = school_id
            return idx
        except Exception as e:
            self.logger.error(f"Error building user class index: {e}", exc_info=True)
            return {}
```

Add `self._settings_for_school: dict[int, bool] = {}` in `__init__` and reset it in `reset_user_class_index`. Add:

```python
    def get_users_for_exchange(self, school_id: str, class_name: str) -> list[int]:
        """Получатели класса, у которых уведомления включены для школы."""
        candidates = self._user_class_index.get((school_id, class_name.lower()), [])
        return [uid for uid in candidates if self._settings_for_school.get(uid, True)]
```

Then in `notify_exchange_updates`, replace the recipient source and the per-user settings check:
- `users = self._get_users_by_class(user_service, school_id, class_name)` → build index if needed, then `users = self.get_users_for_exchange(school_id, class_name)`; pass through the existing `_get_users_by_class` call first so the index exists.
- Remove the inner `notifications_enabled = user_service.get_user_notification_settings(...)` block — recipients are already filtered. Keep the send loop.

- [ ] **Step 5: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_notification_index.py tests/test_exchange_service.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/user_service.py services/notification_service.py tests/test_notification_index.py
git commit -m "P2: batch notification settings and settings-aware recipient index"
```

---

### Task 4: `BackgroundUpdater` — partial-load merge, lock, single invalidation hook

**Files:**
- Modify: `core/background_updater.py`
- Test: `tests/test_background_updater_merge.py` (create)

**Interfaces:**
- Produces: `BackgroundUpdater._on_data_replaced() -> None` (clears schedule cache + resets notification index). `_perform_update` merges new data over last-known-good and is serialized by `self._update_lock: asyncio.Lock`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_background_updater_merge.py`:

```python
# tests/test_background_updater_merge.py
"""Регрессии: частичная загрузка сохраняет last-known-good; единый _on_data_replaced."""
from types import SimpleNamespace

from core.background_updater import BackgroundUpdater


def _make():
    app = SimpleNamespace(bot_data={}, bot=None)
    up = BackgroundUpdater(app)
    return up, app


def test_on_data_replaced_clears_cache_and_index():
    up, app = _make()
    calls = {'cleared': 0, 'reset': 0}

    class _Cache:
        def clear(self):
            calls['cleared'] += 1

    class _Notif:
        def reset_user_class_index(self):
            calls['reset'] += 1

    app.bot_data['cache_service'] = _Cache()
    app.bot_data['notification_service'] = _Notif()
    up._on_data_replaced()
    assert calls == {'cleared': 1, 'reset': 1}


def test_merge_keeps_failed_school():
    old = {'s1': {'v': 1}, 's2': {'v': 2}}
    new = {'s1': {'v': 99}}
    merged = BackgroundUpdater._merge_schools_data(old, new)
    assert merged['s1'] == {'v': 99}
    assert merged['s2'] == {'v': 2}  # last-known-good сохранён
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_background_updater_merge.py -q`
Expected: FAIL — methods missing.

- [ ] **Step 3: Implement**

In `core/background_updater.py` `__init__`, add:
```python
        self._update_lock = asyncio.Lock()
```

Add the two methods:
```python
    @staticmethod
    def _merge_schools_data(old: dict, new: dict) -> dict:
        """Свежие данные поверх last-known-good: не потерять школу при сбое загрузки."""
        merged = dict(old or {})
        merged.update(new or {})
        return merged

    def _on_data_replaced(self):
        """Единая реакция на замену schools_data: сброс кэша расписания и индекса уведомлений."""
        cache_service = self.application.bot_data.get('cache_service')
        if cache_service:
            cache_service.clear()
            self.logger.info("Кэш расписания очищен после обновления данных")
        notification_service = self.application.bot_data.get('notification_service')
        if notification_service and hasattr(notification_service, 'reset_user_class_index'):
            notification_service.reset_user_class_index()
```

In `_perform_update`, wrap the body in the lock. At the top:
```python
        if self._update_lock.locked():
            self.logger.warning("Обновление уже выполняется — пропуск повторного запуска")
            return
        async with self._update_lock:
            await self._perform_update_locked()
```
Then rename the existing body to `_perform_update_locked` (keep `_perform_update` as the locking wrapper), and inside it replace the data-replacement block:

```python
            if new_schools_data:
                merged = self._merge_schools_data(old_schools_data, new_schools_data)
                self.application.bot_data['schools_data'] = merged
                self._on_data_replaced()
                from config.schools import get_display_name as _gdn  # already imported at module top
                updated_schools = [
                    get_display_name(sid, new_schools_data[sid])
                    for sid in new_schools_data
                    if sid not in old_schools_data or old_schools_data[sid] != new_schools_data[sid]
                ]
                await self._check_exchange_updates(old_schools_data, merged)
                ...
```

Remove the old inline `cache_service.clear()` and `reset_user_class_index()` blocks (now in `_on_data_replaced`). Keep the admin-notification logic.

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_background_updater_merge.py tests/test_background_updater_exchanges.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/background_updater.py tests/test_background_updater_merge.py
git commit -m "P2: merge partial loads, lock updates, single invalidation hook"
```

---

### Task 5: Admin refresh uses the shared invalidation and a concurrency guard

**Files:**
- Modify: `handlers/callbacks/admin_callbacks.py`
- Test: `tests/test_admin_refresh_invalidation.py` (create)

**Interfaces:**
- Consumes: `BackgroundUpdater._on_data_replaced()`.
- Produces: after `_refresh_all_schools`/`_refresh_school` update `bot_data['schools_data']`, `_on_data_replaced()` is invoked; a `self._refresh_lock` prevents overlapping manual refreshes.

- [ ] **Step 1: Write failing test**

Create `tests/test_admin_refresh_invalidation.py`:

```python
"""Регрессия: ручной refresh вызывает _on_data_replaced()."""
from types import SimpleNamespace
import asyncio

import handlers.callbacks.admin_callbacks as ac


class _Query:
    def __init__(self):
        self.edits = []

    async def answer(self, *a, **k):
        pass

    async def edit_message_text(self, text, **k):
        self.edits.append(text)


class _Loader:
    def load_school_data(self, cfg, max_retries=None):
        return {'CLASSES': {}}

    def load_all_schools_data(self):
        return {'school_133': {'CLASSES': {}}}


async def test_refresh_school_invalidates(monkeypatch):
    called = {'n': 0}
    updater = SimpleNamespace(_on_data_replaced=lambda: called.__setitem__('n', called['n'] + 1))
    monkeypatch.setattr(ac, 'DataLoader', lambda: _Loader())

    h = ac.AdminCallbackHandler()
    query = _Query()
    update = SimpleNamespace(
        callback_query=query,
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=1),
    )
    context = SimpleNamespace(
        bot_data={'background_updater': updater, 'config': SimpleNamespace(ADMIN_IDS=[1])},
        bot=SimpleNamespace(),
    )
    async def _show(*a, **k):
        pass
    monkeypatch.setattr(h, '_show_admin_panel', _show)

    await h._refresh_school(update, context, 'school_133')
    assert called['n'] == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_admin_refresh_invalidation.py -q`
Expected: FAIL — `_on_data_replaced` not called.

- [ ] **Step 3: Implement**

In `AdminCallbackHandler.__init__`, add:
```python
    def __init__(self):
        self._refresh_lock = asyncio.Lock()
```

Add a helper:
```python
    def _invalidate_data(self, context):
        """Единая инвалидация после ручной замены schools_data."""
        updater = context.bot_data.get('background_updater')
        if updater and hasattr(updater, '_on_data_replaced'):
            updater._on_data_replaced()
        else:
            cache_service = context.bot_data.get('cache_service')
            if cache_service:
                cache_service.clear()
            notification_service = context.bot_data.get('notification_service')
            if notification_service and hasattr(notification_service, 'reset_user_class_index'):
                notification_service.reset_user_class_index()
```

In `_refresh_all_schools`, after `context.bot_data['schools_data'] = schools_data`, call `self._invalidate_data(context)`. Wrap the method body:
```python
        if self._refresh_lock.locked():
            await query.answer("⏳ Обновление уже выполняется")
            return
        async with self._refresh_lock:
            ...existing body...
```
In `_refresh_school`, after merging into `schools_data`, call `self._invalidate_data(context)`, under the same lock.

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_admin_refresh_invalidation.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add handlers/callbacks/admin_callbacks.py tests/test_admin_refresh_invalidation.py
git commit -m "P2: admin refresh shares invalidation and guards concurrency"
```

---

### Task 6: `RetryAfter`-aware sending and broadcast throttle

**Files:**
- Modify: `services/notification_service.py`
- Test: `tests/test_notification_retry.py` (create)

**Interfaces:**
- Produces: `NotificationService._send_message(bot, chat_id, text, parse_mode='Markdown', max_attempts=3) -> bool` — retries on `telegram.error.RetryAfter`, returns `False` on other failures.

- [ ] **Step 1: Write failing test**

Create `tests/test_notification_retry.py`:

```python
"""Регрессия: RetryAfter приводит к повторной отправке."""
from telegram.error import RetryAfter

from services.notification_service import NotificationService


class _Bot:
    def __init__(self):
        self.calls = 0

    async def send_message(self, chat_id, text, parse_mode=None):
        self.calls += 1
        if self.calls == 1:
            raise RetryAfter(0)
        return True


async def test_send_retries_after_retryafter():
    svc = NotificationService()
    bot = _Bot()
    ok = await svc._send_message(bot, 1, 'hi')
    assert ok is True
    assert bot.calls == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_notification_retry.py -q`
Expected: FAIL — `_send_message` missing.

- [ ] **Step 3: Implement**

Add import `import asyncio` and `from telegram.error import RetryAfter` to `services/notification_service.py`. Add:

```python
    async def _send_message(self, bot, chat_id: int, text: str, parse_mode: str = 'Markdown',
                            max_attempts: int = 3) -> bool:
        """Отправляет сообщение, пережидая Telegram RetryAfter (429)."""
        for attempt in range(max_attempts):
            try:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
                return True
            except RetryAfter as e:
                wait = float(getattr(e, 'retry_after', 1) or 1)
                self.logger.warning(f"Telegram RetryAfter {wait}s (попытка {attempt + 1})")
                await asyncio.sleep(wait)
            except Exception as e:
                self.logger.error(f"Failed to send message to {chat_id}: {e}")
                return False
        return False
```

Replace the direct `await context.bot.send_message(...)` in `notify_admins` and in the `notify_exchange_updates` per-user loop with `await self._send_message(context.bot, ...)`. Add a small `await asyncio.sleep(0.05)` between user sends to throttle.

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_notification_retry.py tests/test_notification_index.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/notification_service.py tests/test_notification_retry.py
git commit -m "P2: handle Telegram RetryAfter and throttle broadcasts"
```

---

### Task 7: `DataLoader` single retry layer and session hygiene

**Files:**
- Modify: `core/data_loader.py`
- Test: `tests/test_data_loader.py` (create)

**Interfaces:**
- Produces: `load_school_data` performs at most `MAX_RETRIES` total attempts (inner calls use `max_retries=1`); `load_all_schools_data` accepts an optional session and closes a session it creates.

- [ ] **Step 1: Write failing test**

Create `tests/test_data_loader.py`:

```python
"""Регрессия: вложенные ретраи не множатся."""
from core.data_loader import DataLoader


class _CountingLoader(DataLoader):
    def __init__(self):
        super().__init__()
        self.filename_calls = 0

    def get_current_filename(self, check_url, max_retries=None):
        self.filename_calls += 1
        return None  # всегда неудача


def test_single_retry_layer():
    loader = _CountingLoader()
    loader.config.MAX_RETRIES = 3
    result = loader.load_school_data({'name': 'X', 'check_url': 'u', 'base_url': 'b'})
    assert result is None
    # ровно MAX_RETRIES попыток, а не MAX_RETRIES²
    assert loader.filename_calls == 3
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_data_loader.py -q`
Current behavior: `load_school_data` calls `get_current_filename` (which itself retries `MAX_RETRIES` times) once per outer attempt → `filename_calls` == 9, test fails. Expected FAIL.

- [ ] **Step 3: Implement single retry layer**

In `core/data_loader.py` `load_school_data`, pass `max_retries=1` to the inner calls so only the outer loop retries:

```python
            filename = self.get_current_filename(school_config['check_url'], max_retries=1)
            ...
            data = self.download_schedule_data(school_config['base_url'], filename, max_retries=1)
```

Since the test subclass overrides `get_current_filename` with a `max_retries=None` signature, it still accepts `max_retries=1` — fine.

- [ ] **Step 4: Run test**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_data_loader.py -q`
Expected: PASS.

- [ ] **Step 5: Session hygiene (no test; verified by suite)**

`load_all_schools_data` currently uses the shared `self.session`. Change it to create a dedicated session per invocation and close it in `finally`, so concurrent `to_thread` runs cannot share a non-thread-safe session:

```python
    def load_all_schools_data(self) -> dict[str, dict]:
        """Загружает данные всех активных школ; использует локальную сессию и закрывает её."""
        schools_data = {}
        failed_schools = []
        session = requests.Session()
        session.headers.update(self.session.headers)
        original = self.session
        try:
            self.session = session
            for school_id, school_config in SCHOOLS_CONFIG.items():
                ...existing loop...
        finally:
            self.session = original
            try:
                session.close()
            except Exception:
                pass
        ...existing failed warning...
        return schools_data
```

(Keep the existing loop body and warning intact.)

- [ ] **Step 6: Run full suite**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/data_loader.py tests/test_data_loader.py
git commit -m "P2: single retry layer and per-call session in DataLoader"
```

---

### Task 8: mypy annotations

**Files:**
- Modify: `services/notification_service.py`
- Test: none (verified via `mypy`)

**Interfaces:** no runtime change.

- [ ] **Step 1: Fix the known annotation**

`services/notification_service.py:27`: `self._index_loaded_for_school: str = None` → `self._index_loaded_for_school: str | None = None`.

Add the new fields introduced in Task 3 with annotations: `self._settings_for_school: dict[int, bool] = {}`.

- [ ] **Step 2: Run mypy on touched modules**

Run: `.venv/bin/python -m mypy services/notification_service.py`
Expected: no new errors attributable to the changed lines (pre-existing errors elsewhere are acceptable if unchanged).

- [ ] **Step 3: Full suite + lint**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q && .venv/bin/ruff check .`
Expected: PASS / clean.

- [ ] **Step 4: Commit**

```bash
git add services/notification_service.py
git commit -m "P2: correct Optional annotation for notification index state"
```

---

### Task 9: Phase 2 docs sync

**Files:**
- Modify: `roadmap.md`
- Modify: `CHANGELOG.md`
- Modify: `README.md` (test count only)
- Modify: `WIKI.md` (test count + any changed architecture)

- [ ] **Step 1: Full verification**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q && .venv/bin/ruff check .`
Expected: PASS / clean.

- [ ] **Step 2: Update docs**

Add a `### Фаза 2 — надёжность и консистентность (P1)` section to `CHANGELOG.md` listing: FileDB save-failure surfacing; shared Markdown escaping; batch notification settings; partial-load merge + update lock + single invalidation; admin refresh invalidation; RetryAfter handling; DataLoader single retry/session hygiene; mypy annotation. Remove completed items from `roadmap.md` and note Phase 2 done, Phase 3-4 remain. Update the test count in `README.md` and `WIKI.md`.

- [ ] **Step 3: Commit**

```bash
git add roadmap.md CHANGELOG.md README.md WIKI.md
git commit -m "Docs: sync roadmap/changelog/README/WIKI after Phase 2"
```

---

## Self-Review

**Spec coverage:**
- §5 partial-load merge → Task 4. Single invalidation + admin → Tasks 4-5.
- §5 Markdown escaping → Task 2. Update lock → Task 4 (background) + Task 5 (admin).
- §5 RetryAfter + broadcast throttle → Task 6. FileDB → Task 1. Batch settings → Task 3.
- §5 DataLoader → Task 7. mypy → Task 8.
- **Deliberate deviation:** parallel school download via Semaphore is NOT implemented. Ruling: `load_all_schools_data` already runs off the event loop via `asyncio.to_thread`; parallelizing adds thread-management and flakiness for an hourly job with two schools. Recorded as a Phase-2 deferred minor. The single-retry and session fixes deliver the correctness value.
- §5 week-message chunking is already satisfied by `handlers/common/messaging.py` (`split_long_message` via `edit_long_message`/`reply_long_message`); no new code, verified in Task 6's review.

**Placeholder scan:** no TBD; each code step carries concrete code. Task 3 Step 1 notes an inline construction path if no test helper exists.

**Type consistency:** `_save_data() -> bool` (Task 1) is consumed by `update_one`/`insert_one`/`delete_one` in the same task. `escape_markdown` (Task 2) is used by `base_schedule_service`, `notification_service`, `entity_menu`, `school_info`, `menu_builder`. `_on_data_replaced()` is defined in Task 4 and consumed in Tasks 4-5. `_send_message` defined and consumed in Task 6. `get_notification_settings_batch` / `_settings_for_school` defined and consumed in Task 3.
