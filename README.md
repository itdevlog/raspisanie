# 🏫 Telegram-бот школьного расписания (с авто-уведомлениями о заменах)

Современный асинхронный Telegram-бот для просмотра расписания и автоматических уведомлений о заменах. Работает на **python-telegram-bot v22.8**, тянет данные из системы **Nikasoft (Ника-Люкс)**, отслеживает изменения в реальном времени и присылает push-уведомления подписанным пользователям. Дополнительно поднимает **Mini App** — веб-версию расписания (FastAPI + Telegram WebApp).

Поддерживает **несколько школ**, кэширование, локальную JSON-БД, фоновое обновление, **веб-расписание** и полноценный админ-панель с интерактивными кнопками.

---

## ✨ Возможности

- 🏫 **Несколько школ** — гибкое переключение (напр. МАОУ СОШ №133 и №181 г. Екатеринбурга).
- 📅 **Расписание**: на **Сегодня / Завтра / Неделю** — для **классов**, **преподавателей** и **кабинетов**.
- 🔄 **Автоматический мониторинг замен** — фоновый сервис проверяет данные (сегодня **и завтра**), `ExchangeDetector` ловит новые замены и шлёт уведомления в формате «до → после» с временем урока (`🔄 6. 13:00-13:45 • Математика (Ищенко К.А., каб. 301) → Биология (Усольцева А.Д., каб. 4022)`); снятие замены помечается как `↩️ … — замена снята`.
- 👨‍🏫 **Замены в расписании учителей** — расписание преподавателя учитывает его собственные замены (`TEACH_EXCHANGE`, как на сайте): новые предметы, классы и кабинеты с маркером 🔄; в строках показан класс урока — `6. 13:00-13:40 • Литературное чтение (2д)`.
- 🗓️ **Переносы праздников** — дни `vacation`/`transfer` из `HOLIDAY_TRANSFER` обрабатываются как на сайте: в каникулы занятий нет, перенесённый день работает по расписанию другого дня недели.
- 🔍 **Свободные кабинеты** — кнопка «Свободный кабинет» в меню кабинетов: какие кабинеты свободны на текущий/следующий урок (с учётом замен и отмен).
- 💾 **Автосохранение** — выбранные школа и класс запоминаются в локальной JSON-БД.
- 🔔 **Подписки** — учителя и кабинеты: кнопка «Подписаться» в расписании, уведомления о заменах и список подписок в `/settings`.
- ⏰ **Напоминания об уроках** — «через N мин начнётся урок …» (тумблер в `/settings`; отдельный asyncio-цикл, без новых зависимостей).
- 📋 **Утренний дайджест** — расписание на день с заменами за час до **первого урока** (тумблер в `/settings`); привязка к уроку учитывает две смены и не шлётся в выходные.
- 🗓️ **Навигация по неделям** — листание недельного расписания класса «◀️ Прошлая / Текущая / Следующая ▶️» (±2 недели).
- 🌙 **Тихие часы** — не беспокоить в заданном окне (по умолчанию 22:00–7:00), вкл/выкл в `/settings`; плюс анти-флуд и обработка Telegram `RetryAfter`.
- ⚙️ **Гибкие настройки** — смена школы/класса, вкл/выкл уведомлений, напоминаний и тихих часов.
- 👑 **Админ-панель** — статус школ, принудительное обновление, статистика пользователей, `/check_exchanges`.
- 📊 **Мониторинг статуса** — команда `/status` показывает актуальность данных по каждой школе (иконка ✅/⚠️/🔴 «Устарело»).
- 🌐 **Mini App — веб-версия расписания (Telegram Web App)** — FastAPI-сервер в процессе бота: расписание классов/преподавателей/кабинетов, свободные кабинеты, поиск; вход по подписи `initData`.
- 🔍 **Умный поиск** — учителя/кабинеты по имени с пагинацией, кнопками «Обновить»/«Отмена».
- 📋 **CopyTextButton** — кнопка «Скопировать» к расписанию на день (до 256 символов).
- 🔄 **Inline-режим** — `@bot 9а` в любом чате отдаёт расписание (включается через @BotFather `/setinline`).
- 🛠️ **Качество кода** — 268 юнит/интеграционных тестов, ruff и mypy (чистые), CI.

---

## 🛠️ Технологический стек

| Слой | Технология |
|------|-----------|
| Язык | **Python 3.11+** |
| Фреймворк | [python-telegram-bot v22.8](https://github.com/python-telegram-bot/python-telegram-bot) (async API, `Application.builder()`, `Defaults`, `AIORateLimiter`) |
| HTTP/парсинг | `httpx` (загрузка JS-файлов Nikasoft, `data_loader`), `re` |
| Веб / Mini App | `fastapi` + `uvicorn` (Telegram WebApp, REST API, `/healthz`) |
| БД | Локальная JSON-БД `FileDB` (потокобезопасная, атомарная запись) |
| Часовой пояс | `zoneinfo` (stdlib) / `TIMEZONE` (`.env`, по умолчанию `Asia/Yekaterinburg` = UTC+5) |
| Конфигурация | `python-dotenv` |

---

## 📁 Структура проекта

```text
telegrambot/
├── bot.py                      # Точка входа: приложение, сервисы, polling
├── manage.sh                   # Установка/обновление/эксплуатация: install, update, doctor, backup…
├── requirements.txt            # Продакшен-зависимости
├── requirements-dev.txt         # Тесты/инструменты (pytest, ruff, mypy)
├── pytest.ini / ruff.toml / mypy.ini
├── .github/workflows/ci.yml     # CI: ruff + pytest
├── config/
│   ├── config.py                # .env, TIMEZONE, is_admin(), get_timezone()
│   └── schools.py               # Школы + get_display_name()/get_school_by_id()
├── core/
│   ├── data_loader.py           # Загрузка/парсинг JS Nikasoft
│   └── background_updater.py    # Фоновое обновление (asyncio + to_thread)
├── database/
│   └── file_db.py               # JSON-БД (потокобезопасная, `.corrupt`-бэкап)
├── handlers/
│   ├── start.py / admin/ / callbacks/ / common/ / rooms/ / schools/ / teachers/
│   ├── common/entity_menu.py    # Общая логика учителей/кабинетов
│   ├── common/menu_builder.py   # Единое главное меню + справка
│   ├── common/messaging.py      # Нарезка ≤4096, safe-edit, логи ошибок
│   └── common/requires_school.py# Декоратор @requires_school
├── services/                    # Бизнес-логика (расписание, замены, уведомления)
├── web/                         # Mini App: FastAPI API, HMAC-авторизация, статика
│   ├── api.py                   # /api/* и /healthz
│   ├── auth.py                  # валидация initData (Telegram WebApp)
│   ├── server.py                # uvicorn в общем event loop бота
│   └── static/                  # фронтенд (vanilla JS + Telegram WebApp SDK)
├── data/                        # database.json, exchange_cache.json, notifications_cache.json
├── logs/                        # bot.log (ротация 5МБ×3), admin.log
└── tests/                       # 268 pytest (юнит + интеграционные моки)
```

---

## 🚀 Быстрый старт

### Вариант 1: через `manage.sh` (рекомендуется)

Одна команда устанавливает всё: Python-окружение, зависимости, `.env` (интерактивно), systemd-сервис.

```bash
git clone https://github.com/itdevlog/telegrambot.git
cd telegrambot

./manage.sh install
```

Скрипт спросит токен бота (у [@BotFather](https://t.me/BotFather)) и предложит поставить systemd-сервис (автозапуск). После установки проверьте конфигурацию и запустите:

```bash
./manage.sh doctor    # диагностика: venv, .env, токен, сервис, /healthz
./manage.sh start     # запуск (или systemd уже запустил)
./manage.sh logs      # логи в реальном времени
```

**Обновление с GitHub** — с бэкапом данных и авто-откатом, если бот не поднялся:

```bash
./manage.sh update
```

Что делает `update`: бэкап `data/` + `.env` → `git pull` → обновление зависимостей → перезапуск → health-check `/healthz` (30 с). Если бот не поднялся — **автоматический откат** к предыдущему коммиту и рестарт.

Все команды:

| Команда | Что делает |
|---------|------------|
| `./manage.sh install` | Установка: venv, зависимости, `.env` (интерактив), systemd (с выбором) |
| `./manage.sh update` | Обновление с GitHub + бэкап + авто-откат при сбое |
| `./manage.sh start` / `stop` / `restart` | Управление ботом |
| `./manage.sh status` | Статус сервиса + health-check |
| `./manage.sh logs` | Логи в реальном времени (Ctrl+C — выход) |
| `./manage.sh backup` | Бэкап `data/` + `.env` в `backups/` (хранит последние 10) |
| `./manage.sh restore` | Восстановление из последнего бэкапа |
| `./manage.sh doctor` | Диагностика: venv, зависимости, `.env`, токен, сервис, `/healthz` |
| `./manage.sh uninstall` | Остановка + удаление сервиса (с вопросами) |

> 💡 Скрипт работает без systemd (тогда бот стартует в фоне через nohup, PID пишется в `bot.pid`). Флаг `--no-color` отключает цвета.

### Вариант 2: вручную

```bash
git clone https://github.com/itdevlog/telegrambot.git
cd telegrambot

python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

Скопируйте [.env.example](.env.example) в `.env` и заполните:

```bash
cp .env.example .env
```

```env
# Токен бота (у @BotFather)
TELEGRAM_TOKEN=123456789:ABCdef...

# ID администраторов через запятую (для /admin)
ADMIN_IDS=123456789,987654321

# Интервал фонового обновления (сек). По умолчанию 3600 = 1 час
UPDATE_INTERVAL=3600

# Попыток запросов к Nikasoft при сбоях
MAX_RETRIES=3

# Пути к данным и логам
DB_PATH=./data/database.json
CACHE_PATH=./data/cache.json
LOG_LEVEL=INFO
LOG_FILE=./logs/bot.log
ADMIN_LOG_FILE=./logs/admin.log
# Часовой пояс (Екатеринбург = UTC+5)
TIMEZONE=Asia/Yekaterinburg

# Web App / Mini App
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=8080
# Публичный HTTPS-URL фронтенда (см. раздел «Mini App»)
WEBAPP_URL=
```

> 💡 Если `TELEGRAM_TOKEN` не задан — бот не упадёт внутри PTB, а выведет понятную ошибку.
> 💡 Невалидные числовые значения (`UPDATE_INTERVAL`, `MAX_RETRIES`, `ADMIN_IDS`) дают читаемое сообщение вместо краха на импорте.

Запуск:

```bash
python bot.py
```

При старте бот создаст директории `data/`, `logs/`, `cache/`, загрузит свежие данные всех активных школ и запустит фоновое обновление через `post_init`.

> 🌐 `python bot.py` запускает **и бота, и веб-сервер** Mini App в одном процессе (порт `WEBAPP_PORT`, по умолчанию `8080`). Проверка живости — `GET /healthz`. Если веб не нужен, задайте `WEBAPP_PORT=0`.

### Запуск под systemd (если ставили вручную)

`/etc/systemd/system/tg-schedule-bot.service`:

```ini
[Unit]
Description=Telegram School Schedule Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/github/telegrambot
ExecStart=/root/github/telegrambot/.venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now tg-schedule-bot.service
journalctl -u tg-schedule-bot.service -f
```

> ✅ Логирование пишется **и в файл** (`RotatingFileHandler`, ротация 5 МБ × 3 бэкапа), **и в консоль** (видно в `journalctl`). Токен бота не пишется в debug-лог httpx.

---

## 🌐 Mini App (веб-версия)

Бот поднимает FastAPI-сервер (`web/`) в том же процессе и отдаёт веб-версию расписания как Telegram Web App.

**Настройка:**

1. Задайте `WEBAPP_URL` — **публичный HTTPS-URL** (Telegram требует HTTPS для кнопок Mini App). Локально удобно поднять туннель, на сервере — reverse proxy (nginx) с TLS:
   ```bash
   cloudflared tunnel --url http://localhost:8080   # выдаст https://…trycloudflare.com
   ```
2. Пропишите полученный URL в `.env`: `WEBAPP_URL=https://schedule.example.com`.
3. Перезапустите бота. При старте автоматически вызывается `set_chat_menu_button` (кнопка «🌐 Веб-расписание») — если `WEBAPP_URL` не задан, кнопка не добавляется и бот работает как раньше.
4. Inline-режим (`@bot 9а` в любом чате) включается в **@BotFather → `/setinline`** (имя бота уже задано при создании).

**Запуск и проверка:**

- `python bot.py` — бот **и** веб-сервер (порт `WEBAPP_PORT`/`8080`) в одном event loop.
- `GET /healthz` — проверка живости; `GET /api/schools`, `/api/{school}/schedule/{class|teacher|room}/{name}` — REST API Mini App.
- Пользовательские данные фронтенда подписаны: сервер валидирует Telegram `initData` (HMAC) и не доверяет неподписанным запросам.

---

## 📘 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню: расписание, учителя, кабинеты, смена школы/класса |
| `/help` | Справка |
| `/status` | Статус актуальности данных по школам |
| `/settings` | Настройки: уведомления, напоминания об уроках (`⏰`), дайджест дня (`📋`), тихие часы (`🌙`), список подписок; у админов — `update_notifications` |
| `/week <класс>` | Расписание на неделю (напр. `/week 5и`) |
| `/school` | Информация о школе |
| `/cancel` | Сбросить текущий ввод/поиск и вернуться в главное меню |
| `/admin` или `/stats` | Интерактивная админ-панель (`/stats` — статистика пользователей, только для `ADMIN_IDS`) |
| `/check_exchanges` | Принудительная проверка и рассылка замен (админ) |

---

## 🧭 Как это работает (кратко)

1. **Загрузка** — `DataLoader` обращается к `check_url` школы, регуляркой находит актуальный JS-файл (`20261013_12345.js`), скачивает его и парсит JSON-объект `var NIKA=`.
2. **Фоновое обновление** — `BackgroundUpdater` раз в `UPDATE_INTERVAL` (через `asyncio.to_thread`, не блокируя polling) скачивает свежее расписание, **очищает кэш** и передаёт данные детектору.
3. **Детект изменений** — `ExchangeDetector` сравнивает новое состояние с предыдущим (ключи уроков как строки), находит новые замены и сохраняет кэш в `data/exchange_cache.json`.
4. **Уведомления** — `NotificationService` находит получателей через O(N)-индекс `(школа, класс) → [user_id]`, форматирует сообщение с корректной датой и рассылает; кэш отправленных ключей живёт 24 ч.

---

## 🧪 Тесты и инструменты

```bash
pip install -r requirements-dev.txt

.venv/bin/ruff check .        # линтер (чисто)
.venv/bin/python -m pytest    # 268 тестов
```

- Юнит: нарезка сообщений, `paginate`, `get_display_name`, матчинг класса (p.11), `FileDB` (битый файл/upsert/delete_one), кэш-уведомления, callback-роутинг, `@requires_school`, exchange round-trip, замены учителей (`TEACH_EXCHANGE`), переносы праздников (`HOLIDAY_TRANSFER`), свободные кабинеты.
- Интеграционные (pytest-asyncio + моки): навигация, рендер меню сущности, меню свободных кабинетов.
- CI: `.github/workflows/ci.yml` — ruff + pytest на каждый push/PR.

---

## 📚 Ссылки

- [WIKI.md](WIKI.md) — подробное устройство проекта.
- [CHANGELOG.md](CHANGELOG.md) — история изменений.
- [roadmap.md](roadmap.md) — что осталось сделать.

---

Если у вас есть вопросы или предложения — создайте [Issue](https://github.com/itdevlog/telegrambot/issues).
