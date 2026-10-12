# 🏫 Школьное расписание

**Telegram-бот + публичный сайт расписания с уведомлениями о заменах.**

[![CI](https://github.com/itdevlog/raspisanie/actions/workflows/ci.yml/badge.svg)](https://github.com/itdevlog/raspisanie/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-868%20pytest%20%2B%20403%20vitest-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

Асинхронный Telegram-бот для просмотра расписания и **автоматических уведомлений о заменах**.
Тянет данные из системы **Nikasoft (Ника-Люкс)**, следит за изменениями в реальном времени и
присылает уведомления подписчикам. Дополнительно поднимает **Mini App** (веб-расписание
внутри Telegram) и **публичный сайт** — мобильное PWA без входа, на отдельном `.ru`-домене,
с Web Push и офлайн-режимом.

Поддерживает **несколько школ**, кэширование, локальную JSON-БД, фоновое обновление,
напоминания об уроках, утренний дайджест, тихие часы и полноценную **админ-панель**.

---

## 🇬🇧 English

An async Telegram bot for school schedules with **automatic substitution (change) alerts**.
It pulls data from the **Nikasoft** system, detects changes in real time, and notifies
subscribers. It also serves a **Telegram Mini App** and a public **Svelte PWA** schedule site
(no login, Web Push, offline). Multi-school, JSON storage, background updates, admin panel.
Docs are in Russian (see [docs/](docs/README.md)).

---

## 👥 Для кого этот проект

| Аудитория | Что нужно | Куда смотреть |
|-----------|-----------|---------------|
| **Пользователи** (родители, ученики, учителя) | Просто открыть бота или сайт | [docs/USAGE.md](docs/USAGE.md) |
| **Администраторы / self-host** | Развернуть бота и сайт у себя | [docs/INSTALL.md](docs/INSTALL.md) |
| **Разработчики** | Понять устройство и доработать | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |

---

## 📸 Скриншоты

> _Плейсхолдеры — замените на реальные PNG в [`docs/assets/screenshots/`](docs/assets/screenshots/)._

| Бот | Публичный сайт |
|-----|----------------|
| ![Меню бота](docs/assets/screenshots/bot-menu.png) | ![Главная сайта](docs/assets/screenshots/site-home.png) |
| ![Расписание в боте](docs/assets/screenshots/bot-schedule.png) | ![Расписание на сайте](docs/assets/screenshots/site-schedule.png) |
| ![Замены](docs/assets/screenshots/bot-exchanges.png) | ![Календарь](docs/assets/screenshots/site-calendar.png) |

---

## ✨ Возможности

### 🤖 Telegram-бот
- 🏫 **Несколько школ** — переключение между школами (напр. МАОУ СОШ №133, №181, №16, №19, №123).
- 📅 **Расписание** на **Сегодня / Завтра / Неделю** — для **классов**, **учителей** и **кабинетов**.
- 🔄 **Мониторинг замен** — фоновый сервис проверяет сегодня и завтра, `ExchangeDetector` ловит новые
  замены и шлёт «до → после» (`🔄 6. 13:00-13:45 • Математика … → Биология …`); снятие — `↩️ … — замена снята`.
- 👨‍🏫 **Замены у учителей** — расписание преподавателя учитывает его собственные замены (`TEACH_EXCHANGE`).
- 🗓️ **Переносы праздников** — `vacation`/`transfer` из `HOLIDAY_TRANSFER` обрабатываются как на сайте.
- 🔍 **Свободные кабинеты** — какие кабинеты свободны на текущий/следующий урок (с учётом замен и отмен).
- 🔔 **Подписки** — на учителей и кабинеты: уведомления о заменах + список подписок в `/settings`.
- ⏰ **Напоминания об уроках** и 📋 **утренний дайджест** (за час до первого урока, с учётом смен).
- 🌙 **Тихие часы** — по умолчанию 22:00–7:00; анти-флуд и обработка Telegram `RetryAfter`.
- 👑 **Админ-панель** — статус школ, принудительное обновление, статистика пользователей, `/check_exchanges`.
- 📊 **`/status`** — актуальность данных по каждой школе (✅/⚠️/🔴 «Устарело»).

### 🌍 Публичный сайт (Svelte PWA, без входа)
- 📅 Расписание класса/учителя/кабинета (сегодня/завтра/неделя/месяц) с **свайпами** между днями.
- 🎨 Настройки оформления: скины (Классика/Минимализм/Тёмная/Контрастная/Молодёжный), акцент, размер шрифта,
  **5 видов расписания** (Компактный/Карточки/Таблица/Таймлайн/Сейчас и далее).
- 🔗 Share-ссылки `/s/{school}/{kind}/{name}?date=…`, History-роутинг и SPA-fallback.
- 📲 Установка на домашний экран, офлайн-индикатор, service worker.
- 🔔 **Web Push** о заменах (VAPID), с режимом «не беспокоить ночью».
- 💬 Кнопка «Открыть в Telegram» и тема Telegram WebApp.

### 🛠️ Инфраструктура
- 📦 **origin → edge**: бот публикует снапшот данных (HMAC-SHA256 + timestamp), edge отдаёт его
  как read-only API за Caddy с авто-TLS — быстро из РФ и устойчиво к сбоям канала.
- 🧪 **868** pytest + **403** vitest, ruff/mypy/svelte-check/eslint чисто, CI на GitHub Actions.
- 🐍 Python 3.11+ · Node 20 (сборка сайта).

---

## 🚀 Быстрый старт

### Бот — одна команда (рекомендуется)

```bash
curl -fsSL https://raw.githubusercontent.com/itdevlog/raspisanie/main/manage.sh | bash -s -- install
```

Скрипт поставит окружение, интерактивно настроит `.env` (токен — у [@BotFather](https://t.me/BotFather))
и предложит systemd-сервис. Дальше:

```bash
cd /opt/raspisanie
./manage.sh doctor   # диагностика
./manage.sh logs     # логи
./manage.sh update   # обновление с авто-откатом
```

### Публичный сайт — одна команда на edge-хосте

```bash
sudo EDGE_DOMAIN=schedule.example.ru ./manage.sh edge
```

Полные инструкции (бот, Mini App, публичный сайт, HTTPS, несколько ботов) — в
**[docs/INSTALL.md](docs/INSTALL.md)**.

---

## 🌍 Архитектура (кратко)

```
Origin (сервер с ботом): бот + Nikasoft + ExchangeDetector + Web Push
        │  POST /internal/snapshot  (JSON, HMAC-SHA256 + X-Snapshot-Timestamp)
        ▼
Edge (сервер в РФ): Caddy (.ru, авто-TLS) → FastAPI (read-only API) + Svelte PWA
        ▲  push-API проксируется обратно на origin (X-Edge-Auth)
   Пользователи
```

- **Снапшот** публикуется origin'ом при старте, раз в цикл обновления и после admin-refresh;
  edge принимает его только при валидной подписи, timestamp ±300 с и совпадении `version`.
- **Деградация канала** — edge отвечает из последней копии даже при устаревшем снапшоте,
  показывая возраст данных (`GET /healthz`).
- Подробнее — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) и [docs/EDGE.md](docs/EDGE.md).

---

## 📘 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню: расписание, учителя, кабинеты, смена школы/класса |
| `/help` | Справка |
| `/status` | Статус актуальности данных по школам |
| `/settings` | Уведомления, напоминания (`⏰`), дайджест (`📋`), тихие часы (`🌙`), подписки |
| `/week <класс>` | Расписание на неделю (напр. `/week 5и`) |
| `/school` | Информация о школе |
| `/cancel` | Сбросить ввод/поиск и вернуться в главное меню |
| `/admin` · `/stats` | Админ-панель и статистика (только `ADMIN_IDS`) |
| `/check_exchanges` | Принудительная проверка и рассылка замен (админ) |

---

## 🛠️ Технологический стек

| Слой | Технология |
|------|-----------|
| Язык | **Python 3.11+** |
| Бот | [python-telegram-bot v22.8](https://github.com/python-telegram-bot/python-telegram-bot) (async, `Application.builder`, `AIORateLimiter`) |
| HTTP/парсинг | `httpx`, `re` |
| Веб / Mini App | `fastapi` + `uvicorn` (REST API, `/healthz`) |
| Публичный сайт | Svelte 5 + Vite + TypeScript (PWA); edge FastAPI из снапшота; Caddy (авто-TLS) + systemd |
| Web Push | `pywebpush` + `cryptography` (VAPID), Service Worker |
| БД | Локальная JSON-БД `FileDB` (потокобезопасная, атомарная запись: `fsync` + `.bak`) |
| Часовой пояс | `zoneinfo` / `TIMEZONE` (по умолчанию `Asia/Yekaterinburg`) |

---

## 📚 Документация

- [docs/README.md](docs/README.md) — индекс документации.
- [docs/INSTALL.md](docs/INSTALL.md) — установка и развёртывание.
- [docs/USAGE.md](docs/USAGE.md) — как пользоваться ботом и сайтом.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — устройство проекта.
- [docs/EDGE.md](docs/EDGE.md) · [docs/WIDGET.md](docs/WIDGET.md) — edge-сервер и виджет.
- [CHANGELOG.md](CHANGELOG.md) — история изменений.

---

## 📄 Лицензия

[MIT](LICENSE). Вопросы и предложения — [Issues](https://github.com/itdevlog/raspisanie/issues).
