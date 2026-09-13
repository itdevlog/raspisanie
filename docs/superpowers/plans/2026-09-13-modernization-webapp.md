# Модернизация бота + Telegram Mini App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Обновить зависимости (PTB 22.8, httpx, zoneinfo), добавить структурированный слой данных, FastAPI-сервер Mini App и новые фичи Telegram (кнопки WebApp, CopyTextButton, реакции, inline-режим).

**Architecture:** Один процесс: PTB `Application` и uvicorn/FastAPI живут в одном event loop (PTB-паттерн custom startup: `initialize → start → updater.start_polling → uvicorn.serve`). Сервисы получают публичные структурные методы `get_day`/`get_week`; Markdown-рендер остаётся поверх структур (байт-в-байт прежним).

**Tech Stack:** Python 3.11, python-telegram-bot 22.8 (`[rate-limiter]`), FastAPI, uvicorn, httpx, zoneinfo, pytest.

**Spec:** `docs/superpowers/specs/2026-09-13-modernization-webapp-design.md`

## Global Constraints

- Python 3.11+; ruff line-length 120; mypy чистый (`PYTHONPATH=. .venv/bin/mypy .`).
- Тесты: `PYTHONPATH=. .venv/bin/pytest -q` (ТЕЛЕGRAM_TOKEN=dummy уже в CI). Базовый прогон: 227 passed — не падать.
- Русские строки сообщений бота НЕ менять (тесты сверяют тексты).
- Коммиты в стиле: `Feat: ...`, `Fix: ...`, `Docs: ...`.
- Проверка кода после каждой задачи: `PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q`.
- Существующие mypy-ошибки в `tests/test_teacher_exchanges.py` (6 шт., `find_teacher_id() -> str|None`) и `tests/test_integration.py` (4 шт.) — pre-existing, не чинить в этой работе, но не добавлять новых.
- PTB 22.8: `disable_web_page_preview` всё ещё работает (конвертируется в `link_preview_options`) — существующий код не трогаем.
- Названия env: `WEBAPP_HOST` (default `0.0.0.0`), `WEBAPP_PORT` (default `8080`), `WEBAPP_URL` (default пусто = Mini App кнопки выключены).
- `requirements.txt` — только прод-зависимости; `requirements-dev.txt` — pytest/ruff/mypy.
- Установка PTB: `python-telegram-bot[rate-limiter]==22.8` (добавляет `aiolimiter`).

---

### Task 1: pytz → zoneinfo

**Files:**
- Modify: `config/config.py`
- Modify: tests: `tests/test_integration.py`, `tests/test_reminders.py`, `tests/test_exchange_service.py`, `tests/test_teacher_exchanges.py`, `tests/test_exchange_detector.py`, `tests/test_subscriptions.py`, `tests/test_quiet_hours.py`, `tests/test_schedule_cache.py`, `tests/test_background_updater_exchanges.py`, `tests/test_week_offset_next_lesson.py`, `tests/test_exchange_detector_dates.py`, `tests/test_digest.py`, `tests/test_free_rooms.py`, `tests/test_holiday_transfer.py`, `tests/test_week_navigation.py` (проверить grep'ом)

**Interfaces:**
- `config.config.get_timezone() -> ZoneInfo` — тип меняется с `pytz.BaseTzInfo` на `zoneinfo.ZoneInfo`; все потребители уже используют его как tzinfo-объект (передают в `datetime.now()`), сигнатура не меняется.

- [ ] **Step 1: Найти все использования pytz**

```bash
grep -rln "pytz" --include="*.py" . | grep -v .venv | sort
```

Ожидаемый результат: `config/config.py` + ~15 тестовых файлов из списка Files.

- [ ] **Step 2: Заменить в config/config.py**

В `config/config.py` заменить:

```python
import pytz
```
на
```python
from zoneinfo import ZoneInfo
```

и

```python
_TIMEZONE = pytz.timezone(_TZ_NAME)
```
на
```python
_TIMEZONE = ZoneInfo(_TZ_NAME)
```

- [ ] **Step 3: Заменить в тестах**

В каждом тестовом файле заменить `import pytz` → `from zoneinfo import ZoneInfo`, и `pytz.timezone('Asia/Yekaterinburg')` → `ZoneInfo('Asia/Yekaterinburg')`. В `tests/test_integration.py` (локальный `import pytz` внутри функции, строка ~110) — аналогично.

- [ ] **Step 4: Удалить pytz из requirements и окружения**

`requirements.txt`: удалить строку `pytz==2024.1`.

```bash
.venv/bin/pip uninstall -y pytz
```

- [ ] **Step 5: Проверить**

```bash
PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
```
Ожидание: все тесты зелёные (227 passed), новых mypy-ошибок нет (ZoneInfo — tzinfo, присваивание `svc.moscow_tz = ZoneInfo(...)` проходит).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Feat: migrate pytz to stdlib zoneinfo"
```

---

### Task 2: requests → httpx в data_loader

**Files:**
- Modify: `core/data_loader.py`
- Test: `tests/test_data_loader.py` (расширить)

**Interfaces:**
- `DataLoader.__init__` создаёт `httpx.Client` c заголовком User-Agent; `.session` остаётся атрибутом с методами `get(url, timeout=10)` → response с `.raise_for_status()` / `.text`.
- `close()` закрывает клиент (httpx `Client.close()` — синхронный, работает так же).

- [ ] **Step 1: Написать падающий тест (моки httpx)**

Дополнить `tests/test_data_loader.py`:

```python
import httpx

from core.data_loader import DataLoader


class _FakeResponse:
    def __init__(self, text='', status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError('err', request=None, response=None)


class _FakeClient:
    def __init__(self, text='var NIKA={}', status=200):
        self.text = text
        self.status = status
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        return _FakeResponse(self.text, self.status)

    def close(self):
        pass

    headers = {}


def test_download_parses_nika_var():
    loader = DataLoader.__new__(DataLoader)
    import logging
    loader.logger = logging.getLogger('t')
    loader.session = _FakeClient(text='var NIKA={"SCHOOL_NAME": "X"};')
    data = loader.download_schedule_data('https://b/', 'f.js', max_retries=1)
    assert data == {'SCHOOL_NAME': 'X'}


def test_download_retries_on_http_error():
    loader = DataLoader.__new__(DataLoader)
    import logging
    loader.logger = logging.getLogger('t')
    loader.session = _FakeClient(text='err', status=500)
    loader.config = type('C', (), {'MAX_RETRIES': 2})()
    import asyncio
    # time.sleep в ретраях заменим на маленькие интервалы через monkeypatch
    result = loader.download_schedule_data('https://b/', 'f.js', max_retries=1)
    assert result is None
```

Запустить: `PYTHONPATH=. .venv/bin/pytest tests/test_data_loader.py -q` — ожидание: падает (DataLoader импортирует requests, но тест использует `__new__`; падение будет на `import requests` если requests удалён — либо пока просто проходит на requests-сессии; главное — после замены на httpx оба теста зелёные).

- [ ] **Step 2: Заменить requests на httpx**

В `core/data_loader.py`:

```python
import requests
```
→
```python
import httpx
```

`self.session = requests.Session()` → `self.session = httpx.Client(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})` (заголовок перенесён в конструктор клиента; удалить `self.session.headers.update({...})`).

В `load_all_schools_data` заменить `requests.Session()` → `httpx.Client(headers=dict(self.session.headers))`; `session.close()` остаётся (httpx.Client.close существует).

Внимание: `time.sleep` в ретраях остаётся (синхронный клиент). `response.text` / `raise_for_status()` — API совместимы.

- [ ] **Step 3: Удалить requests**

`requirements.txt`: удалить `requests==2.31.0`.

```bash
.venv/bin/pip uninstall -y requests
```

- [ ] **Step 4: Проверить**

```bash
PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Feat: replace requests with httpx in data loader"
```

---

### Task 3: dotenv 1.2.3 + fastapi/uvicorn в зависимостях, PTB 22.8 + aiolimiter

**Files:**
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt` (добавить httpx — он нужен тестам для моков; pytest/httpx)

**Interfaces:**
- PTB 22.8 с extras `[rate-limiter]`; FastAPI + uvicorn для Task 6+.

- [ ] **Step 1: Обновить requirements.txt**

```
python-telegram-bot[rate-limiter]==22.8
fastapi==0.141.1
uvicorn==0.52.4
python-dotenv==1.2.3
httpx==0.28.1
```

(httpx пин: PTB 22.8 требует `httpx>=0.27,<0.29`; пиновать явно — чтобы data_loader и тесты имели стабильную версию. Проверить фактическую разрешённую версию после install и записать её.)

`requirements-dev.txt` — добавить после установки:
```
httpx==<фактическая версия из pip show httpx>
```
(если dev-файл уже получает httpx транзитивно через PTB — не добавлять, вместо этого убедиться что тестовые импорты `import httpx` работают в CI: `pip install -r requirements.txt` ставит PTB → httpx ставится. Тогда requirements-dev.txt не меняем.)

- [ ] **Step 2: Установить**

```bash
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

- [ ] **Step 3: Прогнать тесты — найти breaking changes PTB 22**

```bash
PYTHONPATH=. .venv/bin/pytest -q 2>&1 | tail -20
```

Известные особенности миграции (по ченджлогу PTB 21/22 и коду):
- `Update.effective_user` теперь также проверяет channel_post (22.8 fix) — не влияет.
- Если упадут тесты, использующие `filters`/`HTTPXRequest` — сверить сигнатуры: в 22.x `HTTPXRequest(connect_timeout=..., read_timeout=..., write_timeout=..., pool_timeout=...)` — все ещё поддерживаются (проверено по исходникам 22.8: параметры сохранены).
- `Application.builder().token(...).post_init(...).request(...).get_updates_request(...)` — API сохранён.
- Возможное падение: `telegram.error.RetryAfter` — не менялся.
- Если что-то упало — исправить минимально, зафиксировать в комментарии плана при исполнении.

- [ ] **Step 4: Проверить линтеры**

```bash
PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
```

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Feat: upgrade PTB to 22.8 with rate-limiter, add fastapi/uvicorn"
```

---

### Task 4: Структурированный слой данных: get_day/get_week + исключения

**Files:**
- Create: `services/schedule_exceptions.py`
- Modify: `services/base_schedule_service.py`
- Modify: `services/schedule_service.py`
- Modify: `services/teacher_service.py`
- Modify: `services/room_service.py`
- Test: `tests/test_structured_schedule.py` (create)

**Interfaces:**
- `services/schedule_exceptions.py`:
  - `class EntityNotFoundError(Exception)` — с атрибутами `.entity_type` ('class'|'teacher'|'room'), `.name`, `.message` (русская строка, готовая для Markdown).
  - `class PeriodNotFoundError(Exception)` — с `.message` = `"❌ Не удалось определить учебный период"`.
- `BaseScheduleService.get_day_data(self, date) -> dict` — НЕ реализован в базовом; каждый сервис реализует `get_day(name, date) -> dict`:
  ```python
  {
    "date": "13.09.2026", "day_name": "Воскресенье",
    "kind": "class",  # 'class' | 'teacher' | 'room'
    "entity": "9а",
    "lessons": [
      {"num": 1, "start": "08:00", "end": "08:45",
       "items": [{"subject": "Математика", "teacher": "Иванова", "room": "201",
                  "class_name": None}],
       "has_exchange": False, "is_cancelled": False},
    ],
    "vacation": False, "weekend": False,
  }
  ```
  Для teacher/room item поля `class_name` заполнены; для class — `class_name: null`.
  Vacation: `{"vacation": true, "lessons": [], ...}`; weekend: `{"weekend": true, "lessons": [], ...}`.
- `get_week(name, week_offset=0) -> list[dict]` — 5 дней (Пн-Пт), каждый — результат `get_day` (дни без уроков включаются с пустым `lessons`, чтобы веб-клиент сам решал, показывать или нет; выходные — `weekend: true`).
- Старые Markdown-методы (`_get_class_schedule_for_date` и т.п.) продолжают работать как раньше — ИЗМЕНЕНИЙ В НИХ НЕТ. Новые методы дублируют их поток (validation → period → effective_day → raw data → exchanges), но возвращают структуру. Дублирование сознательное: Markdown-путь остаётся байт-в-байт (спека §2), рефакторинг общего ядра — вне границ этой работы (спека «Границы работы»: формат Markdown не трогаем).

- [ ] **Step 1: Написать failing-тесты**

`tests/test_structured_schedule.py`:

```python
"""Структурный слой get_day/get_week (payload для Mini App)."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from services.room_service import RoomService
from services.schedule_exceptions import EntityNotFoundError, PeriodNotFoundError
from services.schedule_service import ScheduleService
from services.teacher_service import TeacherService

TZ = ZoneInfo('Asia/Yekaterinburg')


def _school():
    return {
        'SCHOOL_NAME': 'Тест',
        'CLASSES': {'c1': '5а', 'c2': '9б'},
        'TEACHERS': {'t1': 'Иванов', 't2': 'Петрова'},
        'ROOMS': {'r1': '101', 'r2': '202'},
        'SUBJECTS': {'s1': 'Математика', 's2': 'Биология'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45'], '2': ['08:55', '09:40']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
        # 13.09.2026 — воскресенье; берём понедельник 07.09.2026 (день 1)
        'CLASS_SCHEDULE': {'p1': {'c1': {'101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']},
                                              '102': {'s': ['s2'], 't': ['t2'], 'r': ['r2']}}}},
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
    }


def _monday():
    return datetime(2026, 9, 7, 10, 0, tzinfo=TZ)


def test_get_day_class_payload():
    svc = ScheduleService(_school())
    day = svc.get_day('5а', _monday())
    assert day['date'] == '07.09.2026'
    assert day['day_name'] == 'Понедельник'
    assert day['kind'] == 'class'
    assert day['entity'] == '5а'
    assert day['vacation'] is False and day['weekend'] is False
    assert len(day['lessons']) == 2
    first = day['lessons'][0]
    assert first['num'] == 1 and first['start'] == '08:00' and first['end'] == '08:45'
    assert first['items'][0]['subject'] == 'Математика'
    assert first['items'][0]['teacher'] == 'Иванов'
    assert first['items'][0]['room'] == '101'
    assert first['items'][0]['class_name'] is None
    assert first['has_exchange'] is False and first['is_cancelled'] is False


def test_get_day_case_insensitive():
    svc = ScheduleService(_school())
    day = svc.get_day('5А', _monday())
    assert day['entity'] == '5а'


def test_get_day_unknown_class_raises():
    svc = ScheduleService(_school())
    with pytest.raises(EntityNotFoundError) as e:
        svc.get_day('11ю', _monday())
    assert '11ю' in e.value.message


def test_get_day_teacher_payload():
    svc = TeacherService(_school())
    day = svc.get_day('Иванов', _monday())
    assert day['kind'] == 'teacher'
    assert day['lessons'][0]['items'][0]['class_name'] == '5а'


def test_get_day_room_payload():
    svc = RoomService(_school())
    day = svc.get_day('202', _monday())
    assert day['kind'] == 'room'
    assert day['lessons'][0]['items'][0]['class_name'] == '5а'
    assert day['lessons'][0]['items'][0]['subject'] == 'Биология'


def test_get_day_weekend():
    svc = ScheduleService(_school())
    sunday = datetime(2026, 9, 13, 10, 0, tzinfo=TZ)
    day = svc.get_day('5а', sunday)
    assert day['weekend'] is True and day['lessons'] == []


def test_get_day_vacation():
    school = _school()
    school['HOLIDAY_TRANSFER'] = {'07.09.2026': {'type': 'vacation'}}
    svc = ScheduleService(school)
    day = svc.get_day('5а', _monday())
    assert day['vacation'] is True and day['lessons'] == []


def test_get_day_exchange_marks():
    school = _school()
    school['CLASS_EXCHANGE'] = {'c1': {'07.09.2026': {'1': {'s': 's2', 't': 't2', 'r': 'r2'}}}}
    svc = ScheduleService(school)
    day = svc.get_day('5а', _monday())
    first = day['lessons'][0]
    assert first['has_exchange'] is True
    assert first['items'][0]['subject'] == 'Биология'


def test_get_day_cancelled():
    school = _school()
    school['CLASS_EXCHANGE'] = {'c1': {'07.09.2026': {'1': {'s': 'F'}}}}
    svc = ScheduleService(school)
    day = svc.get_day('5а', _monday())
    first = day['lessons'][0]
    assert first['is_cancelled'] is True


def test_get_day_no_period_raises():
    school = _school()
    school['PERIODS'] = {}
    svc = ScheduleService(school)
    with pytest.raises(PeriodNotFoundError):
        svc.get_day('5а', _monday())


def test_get_week_five_days():
    svc = ScheduleService(_school())
    days = svc.get_week('5а', 0)
    assert len(days) == 5
    assert days[0]['date'] == '07.09.2026'
    assert days[4]['date'] == '11.09.2026'


def test_get_week_offset_next_week():
    svc = ScheduleService(_school())
    days = svc.get_week('5а', 1)
    assert days[0]['date'] == '14.09.2026'
```

- [ ] **Step 2: Запустить — должны упасть (нет методов)**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_structured_schedule.py -q
```
Ожидание: FAIL/ERROR (AttributeError: no get_day / ImportError schedule_exceptions).

- [ ] **Step 3: Создать schedule_exceptions.py**

```python
# services/schedule_exceptions.py
"""Исключения структурного слоя расписаний (для API)."""


class EntityNotFoundError(Exception):
    """Сущность (класс/учитель/кабинет) не найдена."""

    def __init__(self, entity_type: str, name: str, message: str):
        super().__init__(message)
        self.entity_type = entity_type
        self.name = name
        self.message = message


class PeriodNotFoundError(Exception):
    """Не удалось определить учебный период для даты."""

    def __init__(self, message: str = "❌ Не удалось определить учебный период"):
        super().__init__(message)
        self.message = message
```

- [ ] **Step 4: Реализовать в BaseScheduleService общие хелперы**

Добавить в `services/base_schedule_service.py` (после `_get_lesson_times`):

```python
    def _day_payload(self, kind: str, entity: str, date: datetime) -> dict:
        """Общий каркас дневного payload: даты, каникулы, выходные."""
        return {
            'date': date.strftime('%d.%m.%Y'),
            'day_name': self._get_day_name(date),
            'kind': kind,
            'entity': entity,
            'lessons': [],
            'vacation': False,
            'weekend': False,
        }

    def _lessons_payload(self, schedule_data: list[dict]) -> list[dict]:
        """Преобразует внутренние lesson-словари в JSON-payload.

        data['s'/'t'/'r'] — параллельные списки: s[0] идёт с t[0] и r[0] (группы).
        Дедупликация не нужна: группы валидны по отдельности. Имена неизвестных
        id (замены TEACH_EXCHANGE кладут имена, не id) — показываем как есть.
        """
        lessons = []
        for lesson in schedule_data:
            times = self._get_lesson_times(lesson['lesson_num'])
            data = lesson.get('data', {})
            items = []
            length = max(len(data.get('s', [])), len(data.get('t', [])), len(data.get('r', [])))
            for i in range(length):
                def _at(values, idx):
                    if isinstance(values, list) and idx < len(values):
                        return values[idx]
                    if isinstance(values, list):
                        return values[0] if values else None
                    return values

                subject_id = _at(data.get('s'), i)
                teacher_id = _at(data.get('t'), i)
                room_id = _at(data.get('r'), i)
                items.append({
                    'subject': self.school_data.get('SUBJECTS', {}).get(subject_id, str(subject_id) if subject_id is not None else None),
                    'teacher': self.school_data.get('TEACHERS', {}).get(teacher_id, str(teacher_id) if teacher_id is not None else None),
                    'room': self.school_data.get('ROOMS', {}).get(room_id, str(room_id) if room_id is not None else None),
                    'class_name': lesson.get('class_name'),
                })
            lessons.append({
                'num': lesson['lesson_num'],
                'start': times[0],
                'end': times[1],
                'items': items,
                'has_exchange': lesson.get('has_exchange', False),
                'is_cancelled': lesson.get('is_cancelled', False),
            })
        return lessons

    def _week_dates(self, week_offset: int) -> list[datetime]:
        """Список дат Пн-Пт указанной недели."""
        today = datetime.now(self.moscow_tz)
        monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        return [monday + timedelta(days=d) for d in range(5)]
```

- [ ] **Step 5: Реализовать get_day/get_week в трёх сервисах**

`services/schedule_service.py` — добавить:

```python
    def get_day(self, class_name: str, date: datetime) -> dict:
        """Структурный payload дня для API (см. спеку §2)."""
        from services.schedule_exceptions import EntityNotFoundError, PeriodNotFoundError

        class_id = self._find_class_id(class_name)
        if not class_id:
            raise EntityNotFoundError('class', class_name, f"❌ Класс '{class_name}' не найден")

        period_id = self._get_period_for_date(date)
        if not period_id:
            raise PeriodNotFoundError()

        payload = self._day_payload('class', self.school_data['CLASSES'][class_id], date)

        effective = self._get_effective_day(date, period_id)
        if effective is None:
            payload['vacation'] = True
            return payload
        eff_period_id, day_num = effective
        if not eff_period_id:
            raise PeriodNotFoundError()

        if date.isoweekday() > 5 and not self._get_holiday_info(date):
            payload['weekend'] = True
            return payload

        info = self._get_holiday_info(date) or {}
        week_num = int(info.get('weeknum') or 0)
        schedule_data = self._get_schedule_data(eff_period_id, class_id, day_num, week_num)
        schedule_data = self.exchange_service.apply_exchanges_to_schedule(
            self.school_data['CLASSES'][class_id], schedule_data, date)
        payload['lessons'] = self._lessons_payload(schedule_data)
        return payload

    def get_week(self, class_name: str, week_offset: int = 0) -> list[dict]:
        """5 структурных payload'ов Пн-Пт."""
        return [self.get_day(class_name, d) for d in self._week_dates(week_offset)]
```

`services/teacher_service.py` — добавить (по той же схеме; после поиска `teacher_id` и проверок периода; weekend/vacation те же; schedule_data через `self._get_teacher_schedule_data(eff_period_id, teacher_id, day_num, date)`; НЕ применять `apply_exchanges_to_schedule` — этот метод уже применяет их внутри):

```python
    def get_day(self, teacher_name: str, date: datetime) -> dict:
        from services.schedule_exceptions import EntityNotFoundError, PeriodNotFoundError

        teacher_id = self.find_teacher_id(teacher_name)
        if not teacher_id:
            raise EntityNotFoundError('teacher', teacher_name,
                                     f"❌ Преподаватель '{teacher_name}' не найден")

        period_id = self._get_period_for_date(date)
        if not period_id:
            raise PeriodNotFoundError()

        payload = self._day_payload('teacher', self.school_data['TEACHERS'][teacher_id], date)

        effective = self._get_effective_day(date, period_id)
        if effective is None:
            payload['vacation'] = True
            return payload
        eff_period_id, day_num = effective
        if not eff_period_id:
            raise PeriodNotFoundError()

        if date.isoweekday() > 5 and not self._get_holiday_info(date):
            payload['weekend'] = True
            return payload

        schedule_data = self._get_teacher_schedule_data(eff_period_id, teacher_id, day_num, date)
        payload['lessons'] = self._lessons_payload(schedule_data)
        return payload

    def get_week(self, teacher_name: str, week_offset: int = 0) -> list[dict]:
        return [self.get_day(teacher_name, d) for d in self._week_dates(week_offset)]
```

`services/room_service.py` — аналогично teacher (entity 'room', `find_room_id`, `_get_room_schedule_data`, сообщение `f"❌ Кабинет '{room_name}' не найден"`).

- [ ] **Step 6: Прогнать новые тесты**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_structured_schedule.py -q
```
Ожидание: все зелёные.

- [ ] **Step 7: Полная проверка + commit**

```bash
PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
git add -A && git commit -m "Feat: structured schedule layer get_day/get_week for API"
```

---

### Task 5: Конфигурация WEBAPP + .env.example

**Files:**
- Modify: `config/config.py`
- Modify: `.env.example`

**Interfaces:**
- `Config.WEBAPP_HOST: str` (default `'0.0.0.0'`), `Config.WEBAPP_PORT: int` (через `_parse_int`, default `8080`), `Config.WEBAPP_URL: str` (default `''` — пустая строка = фичи Mini App выключены).

- [ ] **Step 1: Добавить в Config** (после `TIMEZONE`):

```python
    # Mini App / веб-сервер
    WEBAPP_HOST = os.getenv('WEBAPP_HOST', '0.0.0.0')
    WEBAPP_PORT = _parse_int('WEBAPP_PORT', 8080)
    WEBAPP_URL = os.getenv('WEBAPP_URL', '')
```

- [ ] **Step 2: Дополнить .env.example**

```
# Веб-версия (Telegram Mini App)
# Хост/порт FastAPI-сервера (работает в процессе бота)
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=8080
# Публичный HTTPS-URL фронтенда (требование Telegram для кнопок Mini App).
# Без него бот работает как раньше, кнопка веб-расписания не добавляется.
# Пример: https://schedule.example.com
WEBAPP_URL=
```

- [ ] **Step 3: Проверить + commit**

```bash
PYTHONPATH=. .venv/bin/pytest -q && git add -A && git commit -m "Feat: WEBAPP_* config for Mini App server"
```

---

### Task 6: web/auth.py — валидация Telegram initData

**Files:**
- Create: `web/__init__.py` (пустой)
- Create: `web/auth.py`
- Test: `tests/test_webapp_auth.py` (create)

**Interfaces:**
- `web/auth.py`:
  - `validate_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> dict | None` — парсит строку initData, проверяет подпись HMAC-SHA256 (алгоритм: secret = HMAC_SHA256(key="WebAppData", msg=bot_token); expected = HMAC_SHA256(key=secret, msg=data_check_string)), проверяет `auth_date` свежести `max_age` секунд от `time.time()`. Возвращает распарсенный dict (включая `user` как JSON) или None.
  - `parse_init_data(init_data: str) -> dict` — URL-decode + parse_qsl; `user`/`receiver` ключи — `json.loads`.
  - `get_user_from_init_data(init_data: str, bot_token: str) -> dict | None` — валидация + `.get('user')`.

- [ ] **Step 1: Failing-тесты**

`tests/test_webapp_auth.py`:

```python
"""Валидация Telegram initData (HMAC-SHA256)."""
import hashlib
import hmac
import json
import time
from urllib.parse import quote

from web.auth import get_user_from_init_data, parse_init_data, validate_init_data

BOT_TOKEN = '123456:ABC-DEF_token'
SECRET = hmac.new(b'WebAppData', BOT_TOKEN.encode(), hashlib.sha256).digest()


def _make_init_data(params: dict, sign: bool = True, auth_date: int | None = None) -> str:
    auth_date = auth_date if auth_date is not None else int(time.time())
    params = {**params, 'auth_date': str(auth_date)}
    pairs = sorted(params.items())
    data_check_string = '\n'.join(f'{k}={v}' for k, v in pairs)
    if sign:
        sig = hmac.new(SECRET, data_check_string.encode(), hashlib.sha256).hexdigest()
        pairs.append(('hash', sig))
    # parse_qsl декодирует %2B и т.п.; значения с юникодом кодируем
    return '&'.join(f'{k}={quote(str(v))}' for k, v in pairs)


def test_parse_init_data_decodes_user():
    user = {'id': 42, 'first_name': 'Иван'}
    raw = _make_init_data({'user': json.dumps(user, ensure_ascii=False)})
    parsed = parse_init_data(raw)
    assert parsed['user']['id'] == 42
    assert parsed['user']['first_name'] == 'Иван'
    assert 'hash' in parsed


def test_validate_ok():
    user = {'id': 42}
    raw = _make_init_data({'user': json.dumps(user)})
    assert validate_init_data(raw, BOT_TOKEN) is not None
    assert validate_init_data(raw, BOT_TOKEN)['user']['id'] == 42


def test_validate_bad_signature():
    raw = _make_init_data({'user': '{"id": 42}'}, sign=False) + '&hash=deadbeef'
    assert validate_init_data(raw, BOT_TOKEN) is None


def test_validate_expired():
    old = int(time.time()) - 90000
    raw = _make_init_data({'user': '{"id": 42}'}, auth_date=old)
    assert validate_init_data(raw, BOT_TOKEN) is None


def test_validate_wrong_token():
    raw = _make_init_data({'user': '{"id": 42}'})
    assert validate_init_data(raw, '999:other') is None


def test_get_user():
    raw = _make_init_data({'user': '{"id": 7}'})
    assert get_user_from_init_data(raw, BOT_TOKEN) == {'id': 7}


def test_get_user_invalid():
    raw = 'auth_date=1&hash=zz'
    assert get_user_from_init_data(raw, BOT_TOKEN) is None
```

- [ ] **Step 2: Запустить (должно упасть — нет модуля web)**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_webapp_auth.py -q
```

- [ ] **Step 3: Реализовать web/auth.py**

```python
# web/auth.py
"""Валидация Telegram WebApp initData (https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app)."""
import hashlib
import hmac
import json
from urllib.parse import parse_qsl


def parse_init_data(init_data: str) -> dict:
    """Разбирает строку initData в dict; 'user'/'receiver' — из JSON."""
    result = dict(parse_qsl(init_data, keep_blank_values=True))
    for key in ('user', 'receiver'):
        if key in result:
            try:
                result[key] = json.loads(result[key])
            except json.JSONDecodeError:
                result[key] = None
    return result


def validate_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> dict | None:
    """Проверяет подпись HMAC и свежесть auth_date. None = невалидно."""
    import time as _time

    if not init_data or not bot_token:
        return None
    data = parse_init_data(init_data)
    received_hash = data.pop('hash', None)
    if not received_hash:
        return None
    try:
        auth_age = _time.time() - int(data.get('auth_date', '0'))
    except ValueError:
        return None
    if auth_age < 0 or auth_age > max_age:
        return None
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(data.items()))
    secret_key = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        return None
    return data


def get_user_from_init_data(init_data: str, bot_token: str) -> dict | None:
    """Валидирует initData и возвращает dict пользователя (или None)."""
    data = validate_init_data(init_data, bot_token)
    user = (data or {}).get('user')
    return user if isinstance(user, dict) else None
```

Важно: `data_check_string` строится по СТРОКОвым значениям parse_qsl (то, что пришло), поэтому `parse_init_data` НЕ должен превращать user в dict до подсчёта подписи. Решение: `validate_init_data` парсит сырые пары сам:

```python
def validate_init_data(init_data: str, bot_token: str, max_age: int = 86400) -> dict | None:
    import time as _time

    if not init_data or not bot_token:
        return None
    raw_pairs = parse_qsl(init_data, keep_blank_values=True)
    raw = dict(raw_pairs)
    received_hash = raw.pop('hash', None)
    if not received_hash:
        return None
    try:
        auth_age = _time.time() - int(raw.get('auth_date', '0'))
    except ValueError:
        return None
    if auth_age < 0 or auth_age > max_age:
        return None
    data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(raw.items()))
    secret_key = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        return None
    # валидно — теперь декодируем user из JSON
    data = parse_init_data(init_data)
    return data
```

(в `data_check_string` участвуют ВСЕ поля кроме hash — как требует документация Telegram.)

- [ ] **Step 4: Прогнать тесты**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_webapp_auth.py -q
```

- [ ] **Step 5: Полная проверка + commit**

```bash
PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
git add -A && git commit -m "Feat: Telegram initData HMAC validation for Mini App"
```

---

### Task 7: web/api.py — FastAPI-эндпоинты

**Files:**
- Create: `web/api.py`
- Test: `tests/test_webapp_api.py` (create)

**Interfaces:**
- `create_app(services: dict) -> FastAPI` — фабрика; `services` = `{'bot_data': dict, 'config': Config}` (bot_data — живой dict приложения, веб читает из него те же ключи: `schools_data`, `user_service`).
- Эндпоинты (все JSON):
  - `GET /healthz` → `{"status": "ok"}`
  - `GET /api/schools` → `{"schools": [{"id": "school_133", "name": "МАОУ СОШ №133", "loaded": true}]}`
  - `GET /api/{school_id}/classes` → `{"classes": ["5а", ...]}`
  - `GET /api/{school_id}/teachers` → `{"teachers": [...]}`
  - `GET /api/{school_id}/rooms` → `{"rooms": [...]}`
  - `GET /api/{school_id}/schedule/{kind}/{name}?date=dd.mm.YYYY` → payload `get_day` (date optional = сегодня); kind ∈ {class, teacher, room}
  - `GET /api/{school_id}/schedule/{kind}/{name}/week?offset=0` → `{"days": [...payload get_day...]}`
  - `GET /api/{school_id}/search?q=...` → `{"teachers": [...], "rooms": [...]}` (min 2 символа — как search_teachers; rooms — 1 символ)
  - `GET /api/{school_id}/free-rooms?date=&lesson=` → `{"free_rooms": [...]}` (date optional = сегодня; lesson int 1..12)
  - `GET /api/me` → `{"user": null | {"id": ...}, "school_id": ..., "class_name": ... | null}` — из initData (заголовок `X-Telegram-Init-Data`), школа/класс через user_service.
- Ошибки: `EntityNotFoundError` → 404 `{"detail": msg}`; `PeriodNotFoundError` → 422; неизвестная школа → 404.
- Анонимный доступ разрешён (read-only всё и так read-only); `/api/me` без валидного initData → `user: null`, дефолтная школа/класс.

- [ ] **Step 1: Failing-тесты**

`tests/test_webapp_api.py`:

```python
"""API Mini App через FastAPI TestClient."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from web.api import create_app

TZ = ZoneInfo('Asia/Yekaterinburg')


def _school():
    return {
        'SCHOOL_NAME': 'Тест',
        'CLASSES': {'c1': '5а'},
        'TEACHERS': {'t1': 'Иванов'},
        'ROOMS': {'r1': '101', 'r2': '202'},
        'SUBJECTS': {'s1': 'Математика'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
        'CLASS_SCHEDULE': {'p1': {'c1': {'101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}}}},
        'CLASS_EXCHANGE': {},
        'TEACH_EXCHANGE': {},
        'HOLIDAY_TRANSFER': {},
    }


class _FakeUserService:
    def get_user_school(self, uid):
        return 'school_133'

    def get_user_class(self, uid, school_id=None):
        return '5а'


def _client(monkeypatch):
    bot_data = {'schools_data': {'school_133': _school()}, 'user_service': _FakeUserService()}
    app = create_app({'bot_data': bot_data})
    return TestClient(app)


def test_healthz():
    client = _client(None)
    assert client.get('/healthz').status_code == 200
    assert client.get('/healthz').json() == {'status': 'ok'}


def test_schools_list():
    r = _client(None).get('/api/schools')
    assert r.status_code == 200
    body = r.json()['schools']
    assert body[0]['id'] == 'school_133'
    assert body[0]['loaded'] is True


def test_classes_list():
    r = _client(None).get('/api/school_133/classes')
    assert r.json()['classes'] == ['5а']


def test_schedule_day_with_date():
    r = _client(None).get('/api/school_133/schedule/class/5а?date=07.09.2026')
    assert r.status_code == 200
    day = r.json()
    assert day['entity'] == '5а'
    assert day['lessons'][0]['items'][0]['subject'] == 'Математика'


def test_schedule_week():
    r = _client(None).get('/api/school_133/schedule/class/5а/week?offset=1')
    assert r.status_code == 200
    assert len(r.json()['days']) == 5


def test_schedule_unknown_entity_404():
    r = _client(None).get('/api/school_133/schedule/class/11ю?date=07.09.2026')
    assert r.status_code == 404


def test_unknown_school_404():
    r = _client(None).get('/api/school_999/classes')
    assert r.status_code == 404


def test_search():
    r = _client(None).get('/api/school_133/search?q=ив')
    assert r.status_code == 200
    assert 'Иванов' in r.json()['teachers']


def test_free_rooms():
    r = _client(None).get('/api/school_133/free-rooms?date=07.09.2026&lesson=1')
    assert r.status_code == 200
    assert '202' in r.json()['free_rooms']  # r2 занят на 1-м уроке, r1 свободен... уточнить по данным


def test_me_anonymous():
    r = _client(None).get('/api/me')
    assert r.status_code == 200
    body = r.json()
    assert body['user'] is None
    assert body['school_id'] == 'school_133'
    assert body['class_name'] == '5а'
```

Примечание к `test_free_rooms`: на уроке 1 занят кабинет 101 (r1), свободен 202 (r2) — assert `'202' in r.json()['free_rooms']` и `'101' not in ...`.

- [ ] **Step 2: Запустить (упадёт — нет web.api)**

- [ ] **Step 3: Реализовать web/api.py**

```python
# web/api.py
"""REST API Mini App: читает живые bot_data (один процесс с ботом)."""
import os
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from config.config import Config
from config.schools import SCHOOLS_CONFIG, get_display_name
from services.room_service import RoomService
from services.schedule_exceptions import EntityNotFoundError, PeriodNotFoundError
from services.schedule_service import ScheduleService
from services.teacher_service import TeacherService
from services.text_utils import escape_markdown  # noqa: F401  (для будущих сообщений)

from .auth import get_user_from_init_data


def _school_or_404(services: dict, school_id: str) -> dict:
    schools_data = services['bot_data'].get('schools_data', {})
    school_data = schools_data.get(school_id)
    if not school_data:
        raise HTTPException(404, f"Школа '{school_id}' не найдена")
    return school_data


def _service_for(kind: str, school_data: dict):
    if kind == 'class':
        return ScheduleService(school_data)
    if kind == 'teacher':
        return TeacherService(school_data)
    if kind == 'room':
        return RoomService(school_data)
    raise HTTPException(404, f"Неизвестный тип расписания '{kind}'")


def _parse_date(date_str: str | None) -> datetime:
    tz = ScheduleService.__mro__  # placeholder — не использовать
    return _now()  # см. _now ниже


def _now() -> datetime:
    from config.config import get_timezone
    return datetime.now(get_timezone())


def _parse_date_or_none(date_str: str | None) -> datetime:
    if not date_str:
        return _now()
    try:
        return datetime.strptime(date_str, '%d.%m.%Y').replace(tzinfo=get_timezone())
    except ValueError:
        raise HTTPException(422, "Некорректная дата; ожидается dd.mm.YYYY")


def create_app(services: dict) -> FastAPI:
    app = FastAPI(title="Schedule Bot Mini App API", docs_url=None, redoc_url=None)

    @app.get('/healthz')
    async def healthz():
        return {'status': 'ok'}

    @app.get('/api/schools')
    async def schools():
        schools_data = services['bot_data'].get('schools_data', {})
        return {'schools': [
            {'id': sid, 'name': cfg.get('name'), 'loaded': sid in schools_data}
            for sid, cfg in SCHOOLS_CONFIG.items() if cfg.get('active', True)
        ]}

    @app.get('/api/{school_id}/classes')
    async def classes(school_id: str):
        return {'classes': ScheduleService(_school_or_404(services, school_id)).get_available_classes()}

    @app.get('/api/{school_id}/teachers')
    async def teachers(school_id: str):
        return {'teachers': TeacherService(_school_or_404(services, school_id)).get_available_teachers()}

    @app.get('/api/{school_id}/rooms')
    async def rooms(school_id: str):
        return {'rooms': RoomService(_school_or_404(services, school_id)).get_available_rooms()}

    @app.get('/api/{school_id}/schedule/{kind}/{name}')
    async def schedule_day(school_id: str, kind: str, name: str, date: str | None = None):
        svc = _service_for(kind, _school_or_404(services, school_id))
        try:
            return svc.get_day(name, _parse_date_or_none(date))
        except EntityNotFoundError as e:
            raise HTTPException(404, e.message) from e
        except PeriodNotFoundError as e:
            raise HTTPException(422, e.message) from e

    @app.get('/api/{school_id}/schedule/{kind}/{name}/week')
    async def schedule_week(school_id: str, kind: str, name: str, offset: int = Query(0, ge=-2, le=2)):
        svc = _service_for(kind, _school_or_404(services, school_id))
        try:
            return {'days': svc.get_week(name, offset)}
        except EntityNotFoundError as e:
            raise HTTPException(404, e.message) from e
        except PeriodNotFoundError as e:
            raise HTTPException(422, e.message) from e

    @app.get('/api/{school_id}/search')
    async def search(school_id: str, q: str = Query(..., min_length=1, max_length=80)):
        school_data = _school_or_404(services, school_id)
        return {
            'teachers': TeacherService(school_data).search_teachers(q),
            'rooms': RoomService(school_data).search_rooms(q),
        }

    @app.get('/api/{school_id}/free-rooms')
    async def free_rooms(school_id: str, date: str | None = None,
                         lesson: int = Query(..., ge=1, le=12)):
        school_data = _school_or_404(services, school_id)
        return {'free_rooms': RoomService(school_data).get_free_rooms(_parse_date_or_none(date), lesson)}

    @app.get('/api/me')
    async def me(x_telegram_init_data: str | None = Header(None)):
        token = (services.get('config') or Config()).TELEGRAM_TOKEN or ''
        user = get_user_from_init_data(x_telegram_init_data, token) if x_telegram_init_data else None
        user_service = services['bot_data'].get('user_service')
        school_id = user_service.get_user_school(user['id']) if user and user_service else None
        class_name = user_service.get_user_class(user['id']) if user and user_service else None
        return {'user': user, 'school_id': school_id, 'class_name': class_name}

    # Статика Mini App (создаётся в Task 8)
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    if os.path.isdir(static_dir):
        app.mount('/', StaticFiles(directory=static_dir, html=True), name='static')

    return app
```

Убрать из кода мусорные placeholder-функции `_parse_date` при реализации — оставить только `_parse_date_or_none` и `_now`.

- [ ] **Step 4: Прогнать тесты API**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_webapp_api.py -q
```

- [ ] **Step 5: Полная проверка + commit**

```bash
PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
git add -A && git commit -m "Feat: FastAPI JSON API for Mini App"
```

---

### Task 8: web/static — фронтенд Mini App

**Files:**
- Create: `web/static/index.html`
- Create: `web/static/app.js`
- Create: `web/static/style.css`

**Interfaces:**
- Статика отдаётся FastAPI (`/` → index.html). Telegram SDK: `https://telegram.org/js/telegram-web-app.js`.
- Элементы DOM (id): `school-select`, `tabs` (кнопки `tab-class`, `tab-teacher`, `tab-room`), `entity-select` (datalist/select для класса), `search-input`, `search-results`, `date-prev`, `date-next`, `date-label`, `mode-day`, `mode-week`, `schedule-container`, `free-rooms-btn`, `free-rooms-result`, `loading` (спиннер).

- [ ] **Step 1: index.html**

```html
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Расписание</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link rel="stylesheet" href="style.css">
</head>
<body>
<div id="app">
  <header>
    <select id="school-select" aria-label="Школа"></select>
  </header>
  <nav id="tabs">
    <button id="tab-class" class="tab active">Класс</button>
    <button id="tab-teacher" class="tab">Учитель</button>
    <button id="tab-room" class="tab">Кабинет</button>
    <button id="free-rooms-btn" class="tab" title="Свободные кабинеты">🔍</button>
  </nav>
  <section id="entity-row">
    <input id="search-input" list="entity-list" placeholder="Выберите или начните вводить…">
    <datalist id="entity-list"></datalist>
  </section>
  <section id="controls">
    <button id="date-prev">‹</button>
    <span id="date-label"></span>
    <button id="date-next">›</button>
    <span class="spacer"></span>
    <button id="mode-day" class="mode active">День</button>
    <button id="mode-week" class="mode">Неделя</button>
  </section>
  <div id="loading" hidden>Загрузка…</div>
  <main id="schedule-container"></main>
  <section id="free-rooms-result" hidden></section>
</div>
<script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: style.css** (тема — CSS-переменные Telegram)

```css
:root {
  --bg: var(--tg-theme-bg-color, #fff);
  --text: var(--tg-theme-text-color, #000);
  --hint: var(--tg-theme-hint-color, #888);
  --link: var(--tg-theme-link-color, #2481cc);
  --button: var(--tg-theme-button-color, #2481cc);
  --button-text: var(--tg-theme-button-text-color, #fff);
  --secondary-bg: var(--tg-theme-secondary-bg-color, #f0f0f0);
}
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
       background: var(--bg); color: var(--text); }
#app { max-width: 640px; margin: 0 auto; padding: 12px; }
header select, #search-input { width: 100%; padding: 10px; border-radius: 8px;
  border: 1px solid var(--hint); background: var(--secondary-bg); color: var(--text); font-size: 16px; }
#tabs { display: flex; gap: 8px; margin: 12px 0; }
.tab { flex: 1; padding: 10px 0; border-radius: 8px; border: none;
  background: var(--secondary-bg); color: var(--text); font-size: 14px; }
.tab.active { background: var(--button); color: var(--button-text); }
#controls { display: flex; align-items: center; gap: 8px; margin: 8px 0; }
#controls button { border: none; border-radius: 8px; background: var(--secondary-bg);
  color: var(--text); padding: 8px 12px; font-size: 16px; }
#controls .spacer { flex: 1; }
.mode.active { background: var(--button); color: var(--button-text); }
#date-label { font-weight: 600; }
.lesson { background: var(--secondary-bg); border-radius: 10px; padding: 10px 12px; margin: 8px 0; }
.lesson .time { font-weight: 700; color: var(--link); }
.lesson .badge { margin-left: 6px; font-size: 12px; }
.lesson.cancelled { opacity: .6; text-decoration: line-through; }
.day-title { margin: 16px 0 4px; font-weight: 700; }
.hint { color: var(--hint); }
#loading { padding: 24px; text-align: center; color: var(--hint); }
```

- [ ] **Step 3: app.js**

```javascript
/* Mini App «Расписание»: vanilla JS, Telegram WebApp SDK. */
const tg = window.Telegram.WebApp;
tg.ready(); tg.expand();

const $ = (id) => document.getElementById(id);
const state = {
  schoolId: null, kind: 'class', entity: null,
  date: null,          // ISO-подобная dd.mm.yyyy или null = сегодня
  mode: 'day',         // 'day' | 'week'
  schools: [], entities: [],
};

async function api(path) {
  const r = await fetch(path, { headers: { 'X-Telegram-Init-Data': tg.initData || '' } });
  if (!r.ok) {
    const body = await r.json().catch(() => ({ detail: 'Ошибка сети' }));
    throw new Error(body.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

function fmtDate(d) {
  const x = d instanceof Date ? d : new Date();
  return `${String(x.getDate()).padStart(2, '0')}.${String(x.getMonth() + 1).padStart(2, '0')}.${x.getFullYear()}`;
}

function shiftDate(days) {
  const base = state.date ? parseDate(state.date) : new Date();
  base.setDate(base.getDate() + days);
  state.date = fmtDate(base);
  render();
}

function parseDate(s) {
  const [d, m, y] = s.split('.').map(Number);
  return new Date(y, m - 1, d);
}

async function init() {
  try {
    const [schools, me] = await Promise.all([api('/api/schools'), api('/api/me')]);
    state.schools = schools.schools;
    const sel = $('school-select');
    sel.innerHTML = schools.schools.map(s => `<option value="${s.id}">${s.name}</option>`).join('');
    if (me.school_id && schools.schools.some(s => s.id === me.school_id)) sel.value = me.school_id;
    state.schoolId = sel.value;
    if (me.class_name) { state.entity = me.class_name; $('search-input').value = me.class_name; }
    sel.onchange = () => { state.schoolId = sel.value; state.entity = null; loadEntities(); render(); };
    await loadEntities();
    render();
  } catch (e) { showError(e.message); }
}

async function loadEntities() {
  const kindPath = { class: 'classes', teacher: 'teachers', room: 'rooms' }[state.kind];
  const body = await api(`/api/${state.schoolId}/${kindPath}`);
  state.entities = body[{ class: 'classes', teacher: 'teachers', room: 'rooms' }[state.kind]];
  $('entity-list').innerHTML = state.entities.map(e => `<option value="${e}">`).join('');
}

function setKind(kind) {
  state.kind = kind; state.entity = null; $('search-input').value = '';
  ['tab-class', 'tab-teacher', 'tab-room'].forEach(id => $(id).classList.remove('active'));
  $(`tab-${kind}`).classList.add('active');
  loadEntities().then(render).catch(e => showError(e.message));
}

function lessonHtml(l) {
  const items = l.items.map(i =>
    `${i.subject}${i.class_name ? ` (${i.class_name})` : ''} — ${i.teacher || ''} · ${i.room || ''}`).join('; ');
  const badge = l.is_cancelled ? '<span class="badge">❌ отменено</span>'
    : l.has_exchange ? '<span class="badge">🔄 замена</span>' : '';
  return `<div class="lesson${l.is_cancelled ? ' cancelled' : ''}">
    <span class="time">${l.num}. ${l.start}–${l.end}</span>${badge}<br>${items || '—'}</div>`;
}

function dayHtml(day) {
  if (day.vacation) return `<div class="hint">🏖️ Каникулы/праздник</div>`;
  if (day.weekend) return `<div class="hint">Выходной</div>`;
  if (!day.lessons.length) return `<div class="hint">📭 Занятий нет</div>`;
  return day.lessons.map(lessonHtml).join('');
}

async function render() {
  const container = $('schedule-container');
  const free = $('free-rooms-result');
  free.hidden = true; container.hidden = false;
  $('date-label').textContent = state.date || fmtDate(new Date());
  if (!state.entity) {
    container.innerHTML = `<div class="hint">Выберите ${state.kind === 'class' ? 'класс' : state.kind === 'teacher' ? 'преподавателя' : 'кабинет'} выше</div>`;
    return;
  }
  $('loading').hidden = false;
  try {
    if (state.mode === 'day') {
      const q = state.date ? `?date=${state.date}` : '';
      const day = await api(`/api/${state.schoolId}/schedule/${state.kind}/${encodeURIComponent(state.entity)}${q}`);
      container.innerHTML = `<div class="day-title">${day.day_name}, ${day.date}</div>` + dayHtml(day);
    } else {
      const off = 0; // неделя — всегда текущая (лимит ±2)
      const body = await api(`/api/${state.schoolId}/schedule/${state.kind}/${encodeURIComponent(state.entity)}/week?offset=${off}`);
      container.innerHTML = body.days.map(d =>
        `<div class="day-title">${d.day_name}, ${d.date}</div>` + dayHtml(d)).join('<hr>');
    }
  } catch (e) { container.innerHTML = `<div class="hint">⚠️ ${e.message}</div>`; }
  finally { $('loading').hidden = true; }
}

async function showFreeRooms() {
  const container = $('schedule-container');
  $('free-rooms-result').hidden = false;
  container.hidden = true;
  const el = $('free-rooms-result');
  const lesson = promptLesson();
  if (!lesson) { el.hidden = true; container.hidden = false; return; }
  try {
    const q = `lesson=${lesson}${state.date ? `&date=${state.date}` : ''}`;
    const body = await api(`/api/${state.schoolId}/free-rooms?${q}`);
    el.innerHTML = `<div class="day-title">Свободные кабинеты, урок ${lesson}</div>` +
      (body.free_rooms.length ? body.free_rooms.join(' · ') : 'Все заняты');
  } catch (e) { el.innerHTML = `<div class="hint">⚠️ ${e.message}</div>`; }
}

function promptLesson() {
  const n = window.prompt('Номер урока (1-12)', '1');
  return n && Number(n) >= 1 && Number(n) <= 12 ? Number(n) : null;
}

function showError(msg) { $('schedule-container').innerHTML = `<div class="hint">⚠️ ${msg}</div>`; }

$('tab-class').onclick = () => setKind('class');
$('tab-teacher').onclick = () => setKind('teacher');
$('tab-room').onclick = () => setKind('room');
$('free-rooms-btn').onclick = () => showFreeRooms();
$('date-prev').onclick = () => shiftDate(-1);
$('date-next').onclick = () => shiftDate(1);
$('mode-day').onclick = () => { state.mode = 'day'; $('mode-day').classList.add('active'); $('mode-week').classList.remove('active'); render(); };
$('mode-week').onclick = () => { state.mode = 'week'; $('mode-week').classList.add('active'); $('mode-day').classList.remove('active'); render(); };
$('search-input').oninput = (e) => { state.entity = e.target.value || null; clearTimeout(state._t); state._t = setTimeout(render, 400); };

init();
```

- [ ] **Step 4: Проверить вручную (смоук)**

```bash
PYTHONPATH=. .venv/bin/python - <<'EOF'
# Смоук: приложение создаётся, статика примонтирована, /healthz и / отвечают
import sys; sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from web.api import create_app
app = create_app({'bot_data': {'schools_data': {}, 'user_service': None}})
c = TestClient(app)
assert c.get('/healthz').json() == {'status': 'ok'}
r = c.get('/')
assert r.status_code == 200 and 'telegram-web-app.js' in r.text
print('static ok')
EOF
```

- [ ] **Step 5: Полная проверка + commit**

```bash
PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
git add -A && git commit -m "Feat: Mini App frontend (vanilla JS + Telegram SDK)"
```

---

### Task 9: web/server.py + запуск в event loop бота (bot.py)

**Files:**
- Create: `web/server.py`
- Modify: `bot.py`

**Interfaces:**
- `web/server.py`:
  - `async def run_webapp(app, config) -> None` — конфигурирует uvicorn.Server, вызывает `await server.serve()`; `server.should_exit` ставится uvicorn'ом по SIGINT/SIGTERM.
- `bot.py`:
  - `ScheduleBot.run()` переписывается с `run_polling` на custom loop (PTB-паттерн):
    ```python
    async def run_async(self):
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=False)
        # post_init: PTB сам не вызывает его без run_polling — вызываем руками
        if self.application.post_init:
            await self.application.post_init(self.application)
        await run_webapp(self.application, self.config)   # блокирует до SIGINT/SIGTERM
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
    ```
  - `main`: `asyncio.run(bot.run_async())` — KeyboardInterrupt больше не перехватывается внутри (uvicorn ловит сигналы сам и возвращает управление).
  - Если `WEBAPP_PORT` == 0 — сервер не стартует, вместо `run_webapp` вызывается «вечное ожидание» (`asyncio.Event().wait()`, SIGINT всё равно прерывает asyncio.run). Это позволяет запустить бота без веб-части (локально).

- [ ] **Step 1: Реализовать web/server.py**

```python
# web/server.py
"""Запуск FastAPI в event loop бота (один процесс)."""
import asyncio
import logging
import uvicorn

logger = logging.getLogger(__name__)


async def run_webapp(application, config) -> None:
    """Обслуживает Mini App (uvicorn) до SIGINT/SIGTERM (uvicorn ставит should_exit)."""
    from web.api import create_app

    services = {
        'bot_data': application.bot_data,
        'config': config,
    }
    server = uvicorn.Server(uvicorn.Config(
        create_app(services),
        host=config.WEBAPP_HOST,
        port=config.WEBAPP_PORT,
        log_level='warning',
        access_log=False,
    ))
    logger.info(f"🌐 Веб-сервер Mini App: http://{config.WEBAPP_HOST}:{config.WEBAPP_PORT}")
    # uvicorn.Server.serve() сам ставит signal handlers; install=None —
    # не трогаем дефолтные обработчики asyncio.run
    await server.serve()


async def wait_forever() -> None:
    """Режим без веб-сервера: ждём сигнала завершения."""
    await asyncio.Event().wait()
```

- [ ] **Step 2: Изменить bot.py**

В `bot.py`:
- Добавить импорты: `import asyncio`, `from web.server import run_webapp, wait_forever`.
- Заменить метод `run()` (строки с `self.application.run_polling(...)`) на:

```python
    async def run_async(self):
        """Запускает бота и веб-сервер в одном event loop (PTB custom startup)."""
        self.setup_handlers()
        self.logger.info("Бот запущен")
        self.logger.info("✅ Бот запущен! Остановите сочетанием Ctrl+C")
        self.logger.info("🏫 Доступные школы:")
        for school in SCHOOLS_CONFIG.values():
            if school.get('active', True):
                status = "✅" if school['id'] in self.application.bot_data.get('schools_data', {}) else "❌"
                self.logger.info(f"   {status} {school['name']} ({school['city']})")

        await self.application.initialize()
        await self.application.start()
        if self.application.updater:
            await self.application.updater.start_polling()

        try:
            if getattr(self.config, 'WEBAPP_PORT', 0):
                await run_webapp(self.application, self.config)
            else:
                await wait_forever()
        finally:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            self.background_updater.stop()
            self.logger.info("🛑 Бот остановлен")

    def run(self):
        asyncio.run(self.run_async())
```

- `_post_init` остаётся зарегистрированным через билдер (`post_init=self._post_init`) — PTB вызывает его в `application.start()`? НЕТ: post_init вызывается run_polling'ом. Проверить: в PTB 22 `post_init` вызывается в `Application.initialize()`? Свериться с исходником:

```bash
grep -n "post_init" .venv/lib/python3.11/site-packages/telegram/ext/_application.py | head
```

Факт (проверено по исходникам 22.8): `post_init` вызывается внутри `Application.initialize()` — то есть при custom startup (`await application.initialize()`) он вызовется автоматически. Оставляем регистрацию через билдер, отдельный ручной вызов не нужен. Если после проверки окажется иначе — вызвать `self.application.post_init(self.application)` вручную после `initialize()` (см. примечание в Interfaces).

- Удалить неиспользуемый импорт, если ruff укажет (`HTTPXRequest` остаётся).

- [ ] **Step 3: Смоук-запуск бота**

```bash
TELEGRAM_TOKEN=dummy WEBAPP_PORT=0 timeout 5 .venv/bin/python bot.py 2>&1 | head -20
```
Ожидание: логи «Загрузка данных...», попытка polling упадёт с ошибкой токена (dummy) — это нормально; главное — нет ImportError/AttributeError и bot доходит до старта polling. Зафиксировать вывод.

Затем смоук с веб-сервером (порт 8099):

```bash
TELEGRAM_TOKEN=dummy WEBAPP_PORT=8099 timeout 5 .venv/bin/python bot.py 2>&1 | head -25 &
sleep 3; curl -s http://127.0.0.1:8099/healthz
```
Ожидание: `{"status":"ok"}`.

- [ ] **Step 4: Полная проверка + commit**

```bash
PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
git add -A && git commit -m "Feat: run FastAPI webserver inside bot event loop"
```

---

### Task 10: Кнопка Mini App в меню + MenuButtonWebApp

**Files:**
- Modify: `handlers/common/menu_builder.py`
- Modify: `bot.py` (post_init: set_chat_menu_button)
- Test: `tests/test_menu_builder.py` (расширить)

**Interfaces:**
- `build_main_menu_keyboard(current_class, webapp_url: str | None = None)` — добавляет кнопку `InlineKeyboardButton("🌐 Веб-расписание", web_app=WebAppInfo(url=webapp_url))` в конец (отдельным рядом), если webapp_url задан.
- Все вызывающие (`handlers/start.py`, `handlers/common/main_menu.py`) берут URL из `context.bot_data.get('webapp_url')`.
- `bot.py`: в `_post_init` при непустом `WEBAPP_URL` — `await application.bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="🌐 Веб-расписание", web_app=WebAppInfo(url=...)))` (глобально, chat_id=None).
- `bot_data['webapp_url']` устанавливается в `setup_services` из конфига.

- [ ] **Step 1: Failing-тест**

Добавить в `tests/test_menu_builder.py`:

```python
def test_build_main_menu_keyboard_webapp_button():
    from telegram import WebAppInfo
    kb = build_main_menu_keyboard("5а", webapp_url="https://x.example").to_dict()
    buttons = [b for row in kb['inline_keyboard'] for b in row]
    wa = [b for b in buttons if b.get('web_app')]
    assert len(wa) == 1
    assert wa[0]['web_app']['url'] == "https://x.example"


def test_build_main_menu_keyboard_no_webapp_without_url():
    kb = build_main_menu_keyboard("5а").to_dict()
    buttons = [b for row in kb['inline_keyboard'] for b in row]
    assert all(not b.get('web_app') for b in buttons)
```

Запустить — упадёт (`build_main_menu_keyboard() got an unexpected keyword argument`).

- [ ] **Step 2: Реализовать**

`menu_builder.py` — сигнатура и добавление ряда:

```python
def build_main_menu_keyboard(current_class: str | None,
                             webapp_url: str | None = None) -> InlineKeyboardMarkup:
    ...существующее построение rows...
    if webapp_url:
        rows.append([InlineKeyboardButton("🌐 Веб-расписание", web_app=WebAppInfo(url=webapp_url))])
    return InlineKeyboardMarkup(rows)
```
(`from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo` вверху.)

`handlers/start.py` и `handlers/common/main_menu.py`:

```python
webapp_url = context.bot_data.get('webapp_url')
reply_markup = build_main_menu_keyboard(current_class, webapp_url)
```

`bot.py` — в `setup_services` добавить:

```python
        self.application.bot_data['webapp_url'] = self.config.WEBAPP_URL or None
```

и в `_post_init` (после уведомления админов):

```python
        webapp_url = self.config.WEBAPP_URL
        if webapp_url:
            try:
                from telegram import MenuButtonWebApp, WebAppInfo
                await application.bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(
                        text="🌐 Веб-расписание",
                        web_app=WebAppInfo(url=webapp_url),
                    )
                )
            except Exception as e:
                self.logger.error(f"Ошибка установки MenuButtonWebApp: {e}")
```

- [ ] **Step 3: Проверить**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_menu_builder.py -q && PYTHONPATH=. .venv/bin/pytest -q
```
Существующие тесты `test_menu_builder.py` вызывают `build_main_menu_keyboard("5а")` — без второго аргумента, обратно совместимо.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "Feat: Mini App button in main menu and chat menu button"
```

---

### Task 11: CopyTextButton + реакции в class_schedule_handler

**Files:**
- Modify: `handlers/common/class_schedule.py`
- Test: `tests/test_schedule_reply.py` (create)

**Interfaces:**
- После отправки расписания (`reply_long_message`) на исходное сообщение ставится реакция ✅/❌ (Bot API `setMessageReaction`, PTB `context.bot.set_message_reaction(chat_id, message_id, reaction=[ReactionTypeEmoji(emoji)]`); emojis: `telegram.constants.ReactionEmoji.EYES` ("👀") при получении, `THUMBS_UP` ("👍") при успехе, `THUMBS_DOWN`? нет — для ошибки реакции нет (сообщение об ошибке и так отправляется).
- `handlers/common/messaging.py`: `reply_long_message(update, context, text, parse_mode=None, copy_text=None)` — новый опциональный параметр: если задан (и ≤256 симв.), к первому chunk'у добавляется клавиатура с `InlineKeyboardButton("📋 Скопировать", copy_text=CopyTextButton(text=copy_text))`.

- [ ] **Step 1: Failing-тест**

`tests/test_schedule_reply.py`:

```python
"""Реакции и CopyTextButton при запросе расписания текстом."""
from types import SimpleNamespace

from telegram import CopyTextButton
from telegram.constants import ReactionEmoji

from handlers.common.messaging import reply_long_message


class _Message:
    def __init__(self):
        self.chat_id = 10
        self.message_id = 20
        self.sent = []

    async def reply_text(self, text, parse_mode=None, reply_markup=None, **kw):
        self.sent.append((text, reply_markup))
        return SimpleNamespace(chat=SimpleNamespace(id=self.chat_id), message_id=self.message_id)


class _Bot:
    def __init__(self):
        self.reactions = []

    async def set_message_reaction(self, chat_id, message_id, reaction=None, **kw):
        self.reactions.append((chat_id, message_id, reaction))


async def test_copy_text_keyboard_added():
    msg = _Message()
    update = SimpleNamespace(message=msg, effective_chat=SimpleNamespace(id=10))
    context = SimpleNamespace(bot=_Bot())
    await reply_long_message(update, context, "коротко", copy_text="коротко")
    text, markup = msg.sent[0]
    assert markup is not None
    btn = markup.inline_keyboard[0][0]
    assert btn.copy_text.text == "коротко"


async def test_copy_text_skipped_when_long():
    msg = _Message()
    update = SimpleNamespace(message=msg, effective_chat=SimpleNamespace(id=10))
    context = SimpleNamespace(bot=_Bot())
    await reply_long_message(update, context, "x" * 300, copy_text="x" * 300)
    text, markup = msg.sent[0]
    assert markup is None
```

Запустить — упадёт (нет параметра copy_text).

- [ ] **Step 2: Расширить reply_long_message**

`handlers/common/messaging.py`:

```python
MAX_COPY_TEXT_LENGTH = 256


async def reply_long_message(
    update, context, text: str, parse_mode: str | None = 'Markdown',
    copy_text: str | None = None,
):
    """Отправляет длинное сообщение reply-сообщениями, разбивая по лимиту.

    copy_text: если задано и ≤256 символов — к первому сообщению добавляется
    кнопка «📋 Скопировать» (CopyTextButton, Bot API 7.4+).
    """
    from telegram import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup

    chunks = split_long_message(text)
    if not chunks:
        return

    reply_markup = None
    if copy_text and len(copy_text) <= MAX_COPY_TEXT_LENGTH:
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("📋 Скопировать", copy_text=CopyTextButton(text=copy_text))
        ]])

    for i, chunk in enumerate(chunks, start=1):
        markup = reply_markup if i == 1 else None
        await update.message.reply_text(
            _mark_chunk(chunk, i, len(chunks)),
            parse_mode=parse_mode,
            reply_markup=markup,
            disable_web_page_preview=True,
        )
```

- [ ] **Step 3: Реакции в class_schedule.py**

В `handlers/common/class_schedule.py` (ветка запроса класса, после строки `class_name = message_text`, перед `schedule_service`):

```python
    # Реакция «👀 обрабатываю» на исходное сообщение
    try:
        from telegram import ReactionTypeEmoji
        await context.bot.set_message_reaction(
            chat_id=message.chat_id, message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji=ReactionEmoji.EYES)],
        )
    except Exception:
        pass  # реакции могут быть недоступны (не критично)
```
(импорты вверху файла: `from telegram.constants import ReactionEmoji`.)

После успешной `reply_long_message(update, context, response)` (в самом конце ветки):

```python
    try:
        from telegram import ReactionTypeEmoji
        await context.bot.set_message_reaction(
            chat_id=message.chat_id, message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji=ReactionEmoji.THUMBS_UP)],
        )
    except Exception:
        pass
```

И передать `copy_text`: собрать plain-текст дня для копирования (без Markdown): использовать структурный метод:

```python
    copy_text = None
    try:
        day = schedule_service.get_day(exact_class_name or class_name, schedule_service.moscow_tz and __import__('datetime').datetime.now(schedule_service.moscow_tz))
        if day and day.get('lessons') and not day['lessons'][0].get('is_cancelled') is None:
            lines = []
            for l in day['lessons']:
                first = l['items'][0] if l['items'] else {}
                lines.append(f"{l['num']}. {l['start']}-{l['end']} {first.get('subject') or ''} {first.get('room') or ''}".strip())
            copy_text = "\n".join(lines)[:256]
    except Exception:
        copy_text = None
    await reply_long_message(update, context, response, copy_text=copy_text)
```

Упростить при реализации (убрать `__import__` — сделать `from datetime import datetime` вверху модуля): 

```python
    copy_text = _plain_day_text(schedule_service, exact_class_name or class_name)
    await reply_long_message(update, context, response, copy_text=copy_text)
```

с приватной функцией в том же файле:

```python
def _plain_day_text(schedule_service, class_name: str) -> str | None:
    """Plain-текст уроков дня для кнопки «Скопировать» (≤256 симв.)."""
    from datetime import datetime
    from services.schedule_exceptions import EntityNotFoundError, PeriodNotFoundError
    try:
        day = schedule_service.get_day(class_name, datetime.now(schedule_service.moscow_tz))
    except (EntityNotFoundError, PeriodNotFoundError):
        return None
    if not day.get('lessons'):
        return None
    lines = []
    for lesson in day['lessons']:
        first = lesson['items'][0] if lesson['items'] else {}
        line = f"{lesson['num']}. {lesson['start']}-{lesson['end']} {first.get('subject') or ''}".strip()
        if first.get('room'):
            line += f" ({first['room']})"
        lines.append(line)
    return "\n".join(lines)[:256] or None
```

- [ ] **Step 4: Проверить + commit**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_schedule_reply.py -q && PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
git add -A && git commit -m "Feat: copy-text button and message reactions for schedule requests"
```

---

### Task 12: Inline-режим (поиск расписания в любом чате)

**Files:**
- Create: `handlers/inline_schedule.py`
- Modify: `bot.py` (register InlineQueryHandler)
- Test: `tests/test_inline_schedule.py` (create)

**Interfaces:**
- `async def inline_query_handler(update, context)` — строит до 5 результатов `InlineQueryResultArticle`:
  - запрос ≥1 символа, матчинг классов по `lower().startswith(query.lower())` (как «умный поиск»), при пустом запросе — класс пользователя из профиля;
  - каждый результат: title = "📅 {класс} — сегодня", InputTextMessageContent с расписанием на сегодня (Markdown parse_mode через `InputTextMessageContent(parse_mode='Markdown')`), id = f"cls_{class_name}";
  - `cache_time=300, is_personal=True` (школа у каждого своя).
- Регистрация в `bot.py` `setup_handlers`: `self.application.add_handler(InlineQueryHandler(inline_query_handler))` (импорт вверху).
- Включение режима: задокументировать в README (Task 13), код работает и при выключенном inline в BotFather (Telegram просто не шлёт inline_query... НЕТ — шлёт только если режим включён у BotFather; задокументировать).

- [ ] **Step 1: Failing-тест**

`tests/test_inline_schedule.py`:

```python
"""Inline-режим: поиск расписания в любом чате."""
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from handlers.inline_schedule import build_inline_results


def _school():
    return {
        'SCHOOL_NAME': 'Тест',
        'CLASSES': {'c1': '5а', 'c2': '9б'},
        'TEACHERS': {'t1': 'Иванов'},
        'ROOMS': {'r1': '101'},
        'SUBJECTS': {'s1': 'Математика'},
        'PERIODS': {'p1': {'b': '01.09.2026', 'e': '31.05.2027'}},
        'LESSON_TIMES': {'1': ['08:00', '08:45']},
        'LESSONSINDAY': 12,
        'DAY_NAMES': ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'],
        'CLASS_SCHEDULE': {'p1': {'c1': {'101': {'s': ['s1'], 't': ['t1'], 'r': ['r1']}}}},
        'CLASS_EXCHANGE': {}, 'TEACH_EXCHANGE': {}, 'HOLIDAY_TRANSFER': {},
    }


def _ctx(school_data):
    return SimpleNamespace(
        bot_data={'schools_data': {'school_133': school_data},
                  'user_service': SimpleNamespace(
                      get_user_school=lambda uid: 'school_133',
                      get_user_class=lambda uid, s=None: '5а')},
    )


def test_build_results_by_prefix():
    results = build_inline_results('9', _ctx(_school()), user_id=1)
    assert len(results) == 1
    assert results[0].title == '📅 9б — сегодня'


def test_build_results_case_insensitive():
    results = build_inline_results('5А', _ctx(_school()), user_id=1)
    assert len(results) == 1
    assert results[0].id == 'cls_5а'


def test_build_results_empty_query_uses_profile_class():
    results = build_inline_results('', _ctx(_school()), user_id=1)
    assert len(results) == 1
    assert results[0].title == '📅 5а — сегодня'


def test_build_results_limited_to_5():
    school = _school()
    school['CLASSES'] = {f'c{i}': f'{i}а' for i in range(1, 11)}
    results = build_inline_results('а', _ctx(school), user_id=1)
    assert len(results) <= 5
```

- [ ] **Step 2: Запустить (упадёт — нет модуля)**

- [ ] **Step 3: Реализовать handlers/inline_schedule.py**

```python
# handlers/inline_schedule.py
"""Inline-режим: @bot 9а — расписание класса на сегодня в любом чате."""
import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram import InlineQueryResultArticle, InputTextMessageContent

from services.schedule_service import ScheduleService

logger = logging.getLogger(__name__)
MAX_RESULTS = 5


def build_inline_results(query: str, context, user_id: int) -> list:
    """Строит inline-результаты по префиксу класса (или классу профиля)."""
    bot_data = context.bot_data
    schools_data = bot_data.get('schools_data', {})
    user_service = bot_data.get('user_service')
    if not schools_data or not user_service:
        return []

    school_id = user_service.get_user_school(user_id)
    school_data = schools_data.get(school_id)
    if not school_data:
        return []

    service = ScheduleService(school_data, school_id=school_id)
    all_classes = service.get_available_classes()

    q = (query or '').strip().lower()
    if q:
        matched = [c for c in all_classes if c.lower().startswith(q)]
    else:
        profile_class = user_service.get_user_class(user_id)
        matched = [profile_class] if profile_class else []

    results = []
    for class_name in sorted(matched)[:MAX_RESULTS]:
        text = service.get_class_schedule_today(class_name)
        results.append(InlineQueryResultArticle(
            id=f"cls_{class_name}",
            title=f"📅 {class_name} — сегодня",
            input_message_content=InputTextMessageContent(
                message_text=text, parse_mode='Markdown'),
            description="Расписание с заменами",
        ))
    return results


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отвечает на inline-запросы расписания."""
    if not update.inline_query:
        return
    results = build_inline_results(update.inline_query.query, context,
                                    update.inline_query.from_user.id)
    await update.inline_query.answer(
        results, cache_time=300, is_personal=True,
    )
```

- [ ] **Step 4: Зарегистрировать в bot.py**

В `setup_handlers`, после MessageHandler:

```python
        # Inline-режим: расписание в любом чате (@bot 9а)
        from handlers.inline_schedule import inline_query_handler
        from telegram.ext import InlineQueryHandler
        self.application.add_handler(InlineQueryHandler(inline_query_handler))
```
(импорты лучше поднять в шапку файла.)

- [ ] **Step 5: Проверить + commit**

```bash
PYTHONPATH=. .venv/bin/pytest tests/test_inline_schedule.py -q && PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
git add -A && git commit -m "Feat: inline mode for schedule search in any chat"
```

---

### Task 13: Defaults + AIORateLimiter; README/CHANGELOG/.env.example

**Files:**
- Modify: `bot.py` (builder: Defaults + rate limiter)
- Modify: `README.md`, `CHANGELOG.md`, `.env.example` (если не в Task 5)

**Interfaces:**
- `Application.builder()` получает `.defaults(Defaults(link_preview_options=LinkPreviewOptions(is_disabled=True)))` и `.rate_limiter(AIORateLimiter(max_retries=3))`.
- `notification_service._send_message`: ручной RetryAfter-цикл остаётся (rate limiter уже ждёт сам, но ручной retry не мешает; тест test_notification_retry остаётся зелёным). Ничего в notification_service НЕ менять.
- Документация: раздел Mini App в README (HTTPS, BotFather: /setmenubutton, inline через @BotFather → /setinline), CHANGELOG-запись.

- [ ] **Step 1: Defaults + AIORateLimiter в bot.py**

Импорты:

```python
from telegram.ext import AIORateLimiter, Defaults
from telegram import LinkPreviewOptions
```

В билдере (`.token(...)` цепочка):

```python
        self.application = (
            Application.builder()
            .token(self.config.TELEGRAM_TOKEN)
            .post_init(self._post_init)
            .defaults(Defaults(link_preview_options=LinkPreviewOptions(is_disabled=True)))
            .rate_limiter(AIORateLimiter(max_retries=3))
            .request(request)
            .get_updates_request(...)
            .build()
        )
```

`request`/`get_updates_request` — существующие HTTPXRequest без изменений.

Внимание: Defaults с link_preview_options конфликтует с явным `disable_web_page_preview=True` в messaging.py? НЕТ — PTB: явный аргумент метода перекрывает Defaults; `disable_web_page_preview` конвертируется в link_preview_options сам. Всё работает.

- [ ] **Step 2: Смоук-запуск**

```bash
TELEGRAM_TOKEN=dummy WEBAPP_PORT=0 timeout 5 .venv/bin/python bot.py 2>&1 | head -10
```
Ожидание: как в Task 9.

- [ ] **Step 3: README (обновить стек + добавить разделы)**

В `README.md`:
- заголовок/стек: `python-telegram-bot v22.8`, FastAPI/uvicorn, httpx, zoneinfo (заменить упоминания requests/pytz/20.7);
- добавить в «Возможности» пункт «🌐 Mini App — веб-версия расписания (Telegram Web App)»;
- новый раздел «## 🌐 Mini App (веб-версия)»: настройка `WEBAPP_URL`, HTTPS (пример: cloudflared/nginx reverse proxy), BotFather: `/setinline` для inline-режима, кнопка меню через `set_chat_menu_button` (ставится автоматически при WEBAPP_URL);
- «Запуск»: `python bot.py` — теперь и бот, и веб (порт 8080); `/healthz` для проверки.

- [ ] **Step 4: CHANGELOG**

Добавить запись сверху (по образцу существующих):

```markdown
## 13.09.2026

### Модернизация: PTB 22.8, Mini App, новые фичи Telegram

- **python-telegram-bot 20.7 → 22.8** (Bot API 10.0, `AIORateLimiter`, `Defaults`); `requests` → `httpx` (data loader); `pytz` → `zoneinfo` (stdlib).
- **Mini App** — FastAPI + uvicorn в процессе бота (`web/`): API `/api/schools`, `/api/{school}/schedule/{class|teacher|room}/{name}`, free-rooms, search, `/api/me`; фронтенд на vanilla JS + Telegram WebApp SDK; кнопка «🌐 Веб-расписание» в меню и MenuButton; HMAC-валидация initData.
- **Структурный слой сервисов** — `get_day`/`get_week` возвращают JSON-payload (уроки, замены, отмены, каникулы/выходные) для API; Markdown-вывод бота не изменился.
- **CopyTextButton** — «📋 Скопировать» к расписанию на день (≤256 симв.).
- **Реакции** — 👀 при обработке текстового запроса, 👍 после ответа.
- **Inline-режим** — `@bot 9а` в любом чате (включить через @BotFather /setinline).
- **Defaults** — превью ссылок отключено глобально.
```

- [ ] **Step 5: Финальная проверка + commit**

```bash
PYTHONPATH=. .venv/bin/ruff check . && PYTHONPATH=. .venv/bin/mypy . && PYTHONPATH=. .venv/bin/pytest -q
git add -A && git commit -m "Feat: defaults and rate limiter; docs for Mini App era"
```

---

## Self-Review (выполнен при написании)

1. **Спека-покрытие:** зависимости (§1: Tasks 1-3), структурный слой (§2: Task 4), FastAPI (§3: Tasks 5-9), фронтенд (§4: Task 8), фичи Telegram (§5: Tasks 10-12, 13), тесты (§6: в каждом task), порядок работ = порядку задач.
2. **Placeholders:** в Task 7 код создания `_parse_date` помечен как удаляемый мусор — executor должен оставить только чистую версию (выделено отдельной правкой после основного блока). В Task 11 inline-код с `__import__` помечен «упростить при реализации» с финальной версией. Оба места имеют явные финальные варианты.
3. **Типы:** `get_day(name, date) -> dict`, `get_week(name, week_offset=0) -> list[dict]` единообразны в трёх сервисах и в API-тестах. `build_main_menu_keyboard(current_class, webapp_url=None)` — обратная совместимость проверена тестом без URL.
4. **Порядок:** Task 9 (server) зависит от Task 7 (api) и Task 5 (config); Task 10 зависит от Task 5; inline (12) зависит от Task 4 (get_class_schedule_today — нет, использует старый Markdown-метод; зависимостей от Task 4 нет, но порядок оставлен после фич для логичности коммитов).