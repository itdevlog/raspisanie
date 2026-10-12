# Дизайн: модернизация бота + Telegram Mini App

Дата: 2026-09-13
Статус: утверждён (подход A — единый процесс)

## Цель

Перевести бота на современные версии библиотек, добавить современные
возможности Telegram (Bot API 9.x–10.0, PTB 22.8) и выпустить веб-версию
расписания в виде Telegram Mini App. Один процесс, одна копия данных.

## 1. Зависимости и миграции

Новый `requirements.txt`:

```
python-telegram-bot==22.8
fastapi
uvicorn
python-dotenv==1.2.3
```

- **Удаляется `requests`:** `core/data_loader.py` переходит на
  `httpx.Client` (httpx — уже транзитивная зависимость PTB, API совместим:
  `get/raise_for_status/text/close`).
- **Удаляется `pytz`:** переход на `zoneinfo` (stdlib, Python 3.11).
  `pytz.timezone(X)` → `ZoneInfo(X)` везде (config.py, ~15 тестов).
  `datetime(..., tzinfo=ZoneInfo(...))` корректнее pytz-паттерна.
- **PTB 20.7 → 22.8:** код не использует polls/payments (основные breaking
  changes там). Проверка — полный прогон тестов.
- **AIORateLimiter** подключается в `Application.builder()`: автоматическая
  пауза при `RetryAfter`. Ручной retry-код в notification_service
  упрощается.

## 2. Структурированный слой данных

Сейчас публичные методы сервисов возвращают готовый Telegram Markdown.
Инвертируем конвейер: **данные → структура → (Markdown | JSON)**.
Markdown-вывод остаётся байт-в-байт прежним (тесты сообщений — гарантия
от регрессий).

Новые публичные методы (Schedule/Teacher/Room сервисы):

```python
get_day(name, date) -> dict          # один день
get_week(name, week_offset) -> list[dict]
```

Формат payload урока:

```json
{"num": 1, "start": "08:00", "end": "08:45",
 "items": [{"subject": "Математика", "teacher": "Иванова", "room": "201"}],
 "has_exchange": false, "is_cancelled": false}
```

Ошибки («класс не найден», «период не определён») становятся
исключениями вместо строк с ❌. API отдаёт 404; Markdown-методы ловят
исключение и возвращают прежние строки (обратная совместимость).

## 3. Веб-сервер FastAPI

Новые файлы: `web/server.py`, `web/api.py`, `web/auth.py`,
`web/static/` (index.html, app.js, style.css).

- **Запуск в event loop бота:** `run_polling` заменяется на документированный
  паттерн PTB для ASGI-интеграции:
  `initialize → start → updater.start_polling → uvicorn.serve()`.
  Сигналы (SIGINT/SIGTERM) → graceful shutdown uvicorn, в finally —
  остановка бота и фоновых задач. Один процесс: API читает живые
  `schools_data` из `bot_data` (обновляет BackgroundUpdater).
- **Эндпоинты (JSON):**
  - `GET /healthz`
  - `GET /api/schools`
  - `GET /api/{school_id}/classes`
  - `GET /api/{school_id}/teachers`
  - `GET /api/{school_id}/rooms`
  - `GET /api/{school_id}/schedule/{kind}/{name}?date=`
  - `GET /api/{school_id}/schedule/{kind}/{name}/week?offset=`
  - `GET /api/{school_id}/search?q=`
  - `GET /api/{school_id}/free-rooms?date=&lesson=`
  - `GET /api/me` — школа/класс пользователя из Telegram initData
- **auth.py:** валидация `initData` (HMAC-SHA256 ключом бота, окно
  свежести 24 ч) без новых зависимостей. Без валидного initData
  (локальная разработка) — API работает анонимно read-only.
- **Конфиг:** `WEBAPP_HOST` (0.0.0.0), `WEBAPP_PORT` (8080),
  `WEBAPP_URL` (публичный HTTPS — требование Telegram для кнопок Mini App;
  без него сервер работает для локальной разработки, кнопки не
  добавляются).

## 4. Фронтенд Mini App (без сборки)

Vanilla JS + официальный `telegram-web-app.js`, статика отдаётся FastAPI.
Тема — CSS-переменные Telegram (тёмная/светлая), BackButton работает.

Экраны: выбор школы (если >1) → вкладки **Класс | Учитель | Кабинет** →
расписание на день; переключатель День/Неделя, стрелки ‹ ›; поиск по
учителям/кабинетам; страница свободных кабинетов (дата + номер урока);
маркеры замен (⚠/✘) как в боте. Класс пользователя подставляется из
`/api/me`.

## 5. Новые фичи Telegram

- **Кнопка Mini App:** «🌐 Веб-расписание» (`WebAppInfo`) в главное меню +
  глобальная `MenuButtonWebApp` через `set_chat_menu_button` в post_init
  (только при заданном `WEBAPP_URL`).
- **CopyTextButton:** кнопка «📋 Скопировать» к дневному расписанию
  (лимит Telegram 256 символов — длинные обрезаются).
- **Реакции:** на текстовый запрос расписания бот ставит 👀 при получении,
  меняет на ✅/❌ по результату (замена «печатаю...»).
- **Inline-режим:** `@botname 9а` в любом чате — расписание на сегодня
  (школа из профиля пользователя). Включение в BotFather
  задокументировать.
- **Defaults:** `link_preview_options` отключены глобально. `parse_mode`
  глобально НЕ меняем (в коде смешаны formatted/plain вызовы).

## 6. Ошибки и тесты

Новые тесты:
- структурированные методы (payload-форма, обмены/отмены);
- auth (HMAC валидный/невалидный/протухший);
- API через FastAPI TestClient (формы ответов, 404, поиск).

Существующие тесты: замена pytz/requests-заглушек, обновление
notification-retry под AIORateLimiter. Полный `pytest` после каждого этапа.

## 7. Порядок работ

1. Зависимости + zoneinfo + httpx (бот как раньше, тесты зелёные)
2. PTB 22.8 + AIORateLimiter
3. Структурированный слой (Markdown не меняется)
4. FastAPI + фронтенд
5. Фичи Telegram (кнопки, реакции, inline)
6. README/CHANGELOG (настройка Mini App, inline, HTTPS)

## Границы работы

- Не трогаем: формат Markdown-сообщений, админ-панель, фоновый обновлятор
  (кроме точечной интеграции с новым запуском), БД-слой.
- Веб-часть — read-only просмотр; управление подписками через веб не
  входит.