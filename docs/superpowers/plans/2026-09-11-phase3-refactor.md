# Phase 3 — Refactor & Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Remove duplication and dead code, unify state reset and notification settings, and eliminate the stale/false-success admin surface — without changing user-visible behavior except where it fixes a bug.

**Architecture:** Consolidate `admin_panel.py` into `AdminCallbackHandler`; add a single `reset_user_flow()` helper and a `/cancel` command; make `UserPreferencesService` the one notification-settings store (delegating from `UserService`); extract shared helpers (`_find_class_id`, `_format_time_ago`, day-navigation keyboard); delete unreachable branches.

**Tech Stack:** Python 3.11, python-telegram-bot 20.7, pytest 7.4, ruff.

**Spec:** `docs/superpowers/specs/2026-09-11-quality-and-features-design.md` (§6)

## Global Constraints

- Python 3.11+, ruff line-length 120.
- Tests: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest -q`; lint: `.venv/bin/ruff check .`.
- Baseline 97 tests; keep green, add regression tests per task.
- Russian strings/comments. No new deps. Commit styles: `P2: ...`, `Fix: ...`, `Docs: ...`.
- Do not break Phase 1/2 contracts (`ScheduleService(school_id=)`, `detect_exchanges(persist=)`, `_on_data_replaced`, `escape_markdown`, `_perform_update` bool).

---

### Task 1: One admin panel — merge `admin_panel.py` into `AdminCallbackHandler`

**Files:**
- Modify: `handlers/callbacks/admin_callbacks.py`
- Modify: `handlers/admin/admin_panel.py`
- Modify: `bot.py` (setup_admin_handlers import stays)
- Test: `tests/test_admin_panel.py` (create)

**Interfaces:**
- Produces: `AdminCallbackHandler.show_panel(update, context, message_text=None)` (public) used for both `/admin` and callback.
- `admin_panel_handler` (for `/admin`, `/stats`) delegates to the handler instance; `/stats` renders user statistics.

- [ ] **Step 1: Write failing test**

Create `tests/test_admin_panel.py`:

```python
"""Админ-панель: одна реализация, /stats показывает статистику."""
from types import SimpleNamespace

import handlers.admin.admin_panel as ap
from handlers.callbacks.admin_callbacks import AdminCallbackHandler


class _Query:
    def __init__(self):
        self.edits = []
        self.answers = []

    async def answer(self, *a, **k):
        self.answers.append(a[0] if a else '')

    async def edit_message_text(self, text, **k):
        self.edits.append(text)


async def test_stats_shows_user_statistics(monkeypatch):
    sent = []

    async def reply_text(text, **k):
        sent.append(text)

    update = SimpleNamespace(effective_user=SimpleNamespace(id=1), message=SimpleNamespace(reply_text=reply_text))
    context = SimpleNamespace(
        bot_data={
            'config': SimpleNamespace(ADMIN_IDS=[1]),
            'user_service': SimpleNamespace(get_users_with_classes=lambda: [
                {'user_id': 1, 'current_school': 'school_133', 'school_classes': {'school_133': '5а'}},
            ]),
        },
        args=['stats'],
    )
    await ap.admin_panel_handler(update, context)
    assert sent and 'Стат' in sent[-1] or any('ользовател' in s for s in sent)
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_admin_panel.py -q`
Expected: FAIL — `/stats` currently shows the panel, not statistics; assertion on "ользовател" fails.

- [ ] **Step 3: Implement**

In `AdminCallbackHandler`, make `_show_admin_panel` public as `show_panel` (keep the private name as an alias if other code references it) and add a statistics method:

```python
    async def _show_statistics(self, update, context):
        """Показывает статистику пользователей (для /stats)."""
        user_service = context.bot_data.get('user_service')
        users = user_service.get_users_with_classes() if user_service else []
        total = len(users)
        by_school = {}
        for u in users:
            sid = u.get('current_school', '—')
            by_school[sid] = by_school.get(sid, 0) + 1
        lines = [f"📊 *Статистика*\n", f"👥 Пользователей с классами: *{total}*", ""]
        for sid, cnt in sorted(by_school.items()):
            lines.append(f"• {sid}: {cnt}")
        text = "\n".join(lines)
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, parse_mode='Markdown')
```

Refactor `admin_panel.py` to delegate:

```python
from handlers.callbacks.admin_callbacks import AdminCallbackHandler

_admin_handler = AdminCallbackHandler()

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not _is_admin(user_id, context):
        await update.message.reply_text("❌ У вас нет прав доступа к админ-панели")
        return
    if context.args and context.args[0] == 'stats':
        await _admin_handler._show_statistics(update, context)
        return
    await _admin_handler._show_admin_panel(update, context)
```

Remove the now-duplicated `_build_admin_panel_text`, `_build_admin_keyboard`, `_get_schools_status`, `_update_callback_message`, `_handle_message_error` from `admin_panel.py` (keep `_is_admin` and `setup_admin_handlers`). This removes the divergent `"⚡ Принудительное обновление"` omission — the callback keyboard is now the only one.

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_admin_panel.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add handlers/admin/admin_panel.py handlers/callbacks/admin_callbacks.py tests/test_admin_panel.py
git commit -m "P2: single admin panel implementation; /stats shows statistics"
```

---

### Task 2: `/cancel` and unified `reset_user_flow`

**Files:**
- Modify: `handlers/common/messaging.py`
- Modify: `handlers/start.py`
- Modify: `handlers/common/callback_handler.py` (`handle_change_class`)
- Modify: `bot.py` (register `/cancel`)
- Test: `tests/test_cancel.py` (create)

**Interfaces:**
- Produces: `handlers.common.messaging.reset_user_flow(context)` — clears `waiting_for_*`, `class_digit`, and search-query keys. `/cancel` resets and shows the main menu.

- [ ] **Step 1: Write failing test**

Create `tests/test_cancel.py`:

```python
"""Сброс «залипшего» состояния: reset_user_flow и /cancel."""
from types import SimpleNamespace

from handlers.common.messaging import reset_user_flow
from handlers.start import cancel_handler


def _context():
    return SimpleNamespace(
        user_data={'waiting_for_teacher_search': True, 'class_digit': '5',
                   'teacher_search_query': 'Ив', 'room_search_query': '101'},
        bot_data={
            'user_service': SimpleNamespace(
                get_user_school=lambda uid: 'school_133',
                get_current_class=lambda uid: None,
            ),
            'schools_data': {'school_133': {'CLASSES': {}}},
        },
    )


def test_reset_user_flow_clears_all():
    ctx = _context()
    reset_user_flow(ctx)
    assert ctx.user_data == {}


async def test_cancel_handler_replies_main_menu():
    sent = []

    async def reply_text(text, **k):
        sent.append(text)

    update = SimpleNamespace(effective_user=SimpleNamespace(id=1),
                             message=SimpleNamespace(reply_text=reply_text))
    ctx = _context()
    await cancel_handler(update, ctx)
    assert sent and 'меню' in sent[-1].lower()
    assert ctx.user_data == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_cancel.py -q`
Expected: FAIL — `reset_user_flow`/`cancel_handler` missing.

- [ ] **Step 3: Implement**

In `handlers/common/messaging.py` add:

```python
def reset_user_flow(context) -> None:
    """Полностью сбрасывает временное состояние пользователя (флаги поиска, цифра класса, запросы)."""
    for key in (
        'waiting_for_teacher_search', 'waiting_for_room_search',
        'class_digit', 'teacher_search_query', 'room_search_query',
    ):
        context.user_data.pop(key, None)
```

Keep `clear_search_flags` as a subset (it is used elsewhere); or reimplement it to call `reset_user_flow` minus class_digit — do NOT change its existing behavior (tests depend on it). Leave `clear_search_flags` as-is.

In `handlers/start.py` add:

```python
from handlers.common.messaging import reset_user_flow

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает текущее действие и возвращает в главное меню."""
    reset_user_flow(context)
    await start_handler(update, context)
```

Note: `start_handler` currently always calls `update.message.reply_text`. For `/cancel` that is fine (command → message). Ensure `start_handler` works with `update.message`. (It does.)

In `handlers/common/callback_handler.py` `handle_change_class`, call `reset_user_flow(context)` before `show_class_selection` (replace the manual `clear_user_class` region only if needed — keep `clear_user_class`).

In `bot.py` register:
```python
self.application.add_handler(CommandHandler("cancel", cancel_handler))
```
and import `cancel_handler`.

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_cancel.py tests/test_integration.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add handlers/common/messaging.py handlers/start.py handlers/common/callback_handler.py bot.py tests/test_cancel.py
git commit -m "P2: add /cancel and unified reset_user_flow"
```

---

### Task 3: Delete dead code and stop leaking `str(e)`

**Files:**
- Modify: `handlers/common/entity_menu.py`
- Modify: `handlers/callbacks/teacher_callbacks.py`
- Modify: `handlers/callbacks/room_callbacks.py`
- Modify: `handlers/callbacks/class_callbacks.py`
- Test: `tests/test_dead_code.py` (create)

**Interfaces:** no new public API; removes unreachable branches and replaces raw exception text with `log_user_error`.

- [ ] **Step 1: Write failing test**

Create `tests/test_dead_code.py`:

```python
"""Мёртвые ветки удалены; ошибки не утекают через str(e)."""
import inspect

from handlers.common import entity_menu
from handlers.callbacks import teacher_callbacks, room_callbacks, class_callbacks


def _src(mod):
    return inspect.getsource(mod)


def test_no_raw_exception_interpolation_in_entity_menu():
    src = _src(entity_menu)
    # str(e) / {e} не должны попадать в текст пользователю
    assert ': {e}")' not in src
    assert '{e}")' not in src or 'log_user_error' in src


def test_dead_menu_branches_removed():
    assert 'menu_teacher' not in _src(teacher_callbacks)
    assert 'menu_room' not in _src(room_callbacks)
    assert 'parts[1] == "digit"' not in _src(class_callbacks)
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_dead_code.py -q`
Expected: FAIL — dead branches still present; `entity_menu` interpolates `{e}`.

- [ ] **Step 3: Implement**

- `entity_menu.py`: import `log_user_error`; replace the four `f"...: {e}"` error replies (in `menu`, `show_all`, `select`, `search_results`) with `log_user_error("<context>", e)`.
- `teacher_callbacks.py` / `room_callbacks.py`: remove the `menu_teacher` / `menu_room` branches (the router sends those to `NavigationCallbackHandler`).
- `class_callbacks.py`: remove the `if parts[1] == "digit":` branch (router intercepts `class_digit_` first).
- Also delete confirmed-unused methods on `ExchangeDetector`: `get_current_exchanges_for_class` and `_get_teacher_name` if still present (grep first; keep `clear_school_cache`, it is referenced by the interface).

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_dead_code.py tests/test_callback_router.py tests/test_integration.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add handlers/common/entity_menu.py handlers/callbacks/teacher_callbacks.py handlers/callbacks/room_callbacks.py handlers/callbacks/class_callbacks.py services/exchange_detector.py tests/test_dead_code.py
git commit -m "P2: remove dead branches and stop leaking exception text"
```

---

### Task 4: Extract shared helpers (`_find_class_id`, `_format_time_ago`)

**Files:**
- Modify: `services/base_schedule_service.py`
- Modify: `services/schedule_service.py`
- Modify: `services/exchange_service.py`
- Modify: `services/status_service.py`
- Test: `tests/test_shared_helpers.py` (create)

**Interfaces:**
- Produces: `BaseScheduleService._find_class_id` stays; `ScheduleService._find_class_id` removed in favor of the base one; `ExchangeService._find_class_id` delegates to a small module-level helper. `format_time_ago(time_diff)` module function in `services/base_schedule_service.py`, used by `StatusService`.

- [ ] **Step 1: Write failing test**

Create `tests/test_shared_helpers.py`:

```python
from datetime import timedelta

from services.base_schedule_service import format_time_ago


def test_format_time_ago():
    assert format_time_ago(timedelta(seconds=10)) == 'только что'
    assert format_time_ago(timedelta(minutes=5)) == '5 мин'
    assert format_time_ago(timedelta(hours=3)) == '3 ч'
    assert format_time_ago(timedelta(days=2)) == '2 дн'
```

- [ ] **Step 2: Run to verify failure**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_shared_helpers.py -q`
Expected: FAIL — no module-level `format_time_ago`.

- [ ] **Step 3: Implement**

In `services/base_schedule_service.py`, add a module-level function and delegate the method:

```python
def format_time_ago(time_diff: timedelta) -> str:
    """Форматирует разницу во времени (единый хелпер)."""
    if time_diff < timedelta(minutes=1):
        return "только что"
    elif time_diff < timedelta(hours=1):
        return f"{int(time_diff.total_seconds() / 60)} мин"
    elif time_diff < timedelta(days=1):
        return f"{int(time_diff.total_seconds() / 3600)} ч"
    else:
        return f"{time_diff.days} дн"
```

`BaseScheduleService._format_time_ago` returns `format_time_ago(time_diff)`. `StatusService._format_time_ago` delegates to `format_time_ago`.

For `_find_class_id`: move the canonical implementation to `BaseScheduleService` (it already exists there? verify) and have `ScheduleService` and `ExchangeService` use it. `ExchangeService` holds `school_data`; add a tiny module-level `find_class_id(school_data, class_name)` in `services/base_schedule_service.py` and have both services call it.

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_shared_helpers.py tests/test_exchange_service.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/base_schedule_service.py services/schedule_service.py services/exchange_service.py services/status_service.py tests/test_shared_helpers.py
git commit -m "P2: extract shared time/class-id helpers"
```

---

### Task 5: Unify notification settings schema

**Files:**
- Modify: `services/user_preferences.py`
- Modify: `services/user_service.py`
- Modify: `handlers/common/settings.py`
- Modify: `core/background_updater.py`
- Test: `tests/test_notification_settings_unified.py` (create)

**Interfaces:**
- Single source of truth: `UserService.get_user_notification_settings/set_user_notification_settings` (per-school map) for exchange notifications; `UserPreferencesService` becomes the only writer for `update_notifications` (admin). `settings.py` reads/writes `update_notifications` only via `UserPreferencesService` and `exchange` only via `UserService` (already true). Task verifies no remaining dual-write and that `background_updater._get_admin_notification_settings` reads the same store the UI writes.

- [ ] **Step 1: Write failing test**

Create `tests/test_notification_settings_unified.py`:

```python
"""Настройки обновлений, записанные UI, читаются фоновым апдейтером."""
import os, tempfile

from database.file_db import FileDB
from services.user_preferences import UserPreferencesService
from services.user_service import UserService


def test_update_notification_roundtrip():
    d = tempfile.mkdtemp()
    db = FileDB(os.path.join(d, 'database.json'))
    UserService(db)  # ensure collections
    prefs = UserPreferencesService(db)
    prefs.enable_update_notifications(1)
    assert UserPreferencesService(db).get_notification_settings(1)['update_notifications'] is True
    prefs.disable_update_notifications(1)
    assert UserPreferencesService(db).get_notification_settings(1)['update_notifications'] is False
```

- [ ] **Step 2: Run to verify pass/fail**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_notification_settings_unified.py -q`
Expected: likely PASS already (round-trip works). If it passes, keep it as a characterization test and focus the task on removing any remaining dual-write. Specifically:
- `handlers/common/settings.py` must not read exchange settings from `user_preferences` nor update settings from `user_service`.
- Grep for `notification_settings` writes and confirm only `UserService` writes `set_user_notification_settings`, and only `UserPreferencesService` writes `update_notifications`.
- If `background_updater._get_admin_notification_settings` reads only the first admin (documented limitation), replace with: return enabled if ANY admin has it enabled. Add a test with a fake UserService returning two admins.

- [ ] **Step 3: Implement**

If changes are needed:
- `background_updater._get_admin_notification_settings`: iterate all `ADMIN_IDS`, return `{'update_notifications': any(enabled)}`.
- Document the two-domain split in a module docstring in `user_preferences.py` (exchange = per-school `UserService`; admin update = `UserPreferencesService`).

- [ ] **Step 4: Run tests**

Run: `TELEGRAM_TOKEN=dummy .venv/bin/python -m pytest tests/test_notification_settings_unified.py tests/test_notification_index.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/user_preferences.py services/user_service.py handlers/common/settings.py core/background_updater.py tests/test_notification_settings_unified.py
git commit -m "P2: clarify and test notification settings store split"
```

---

### Task 6: Phase 3 docs sync

**Files:** `roadmap.md`, `CHANGELOG.md`, `README.md` (test count), `WIKI.md` (test count + admin panel note).

- [ ] **Step 1:** full suite + ruff.
- [ ] **Step 2:** add `### Фаза 3 — рефакторинг и качество (P2)` to CHANGELOG; remove done items from roadmap; update counts.
- [ ] **Step 3:** commit `Docs: sync roadmap/changelog/README/WIKI after Phase 3`.

---

## Self-Review

**Spec coverage:** §6 admin merge → T1; settings schema → T5; shared helpers → T4; reset/cancel → T2; dead code + `str(e)` → T3; docs → T6.
**Deliberate deferrals (recorded):** repository/TypedDict domain layer and clock injection are NOT implemented — they are large, cross-cutting refactors with low user-visible value; the spec lists them but Phase 3's highest-value items are the duplication/dead-code/UX fixes. Remaining `_find_class_id`/day-keyboard duplication beyond the extracted helpers is left; noted in roadmap.
**Placeholders:** none; each step carries concrete code.
**Type consistency:** `reset_user_flow` defined+used in T2; `format_time_ago` defined+used in T4; admin `show_panel`/`_show_statistics` defined+used in T1.
