# 🏫 Telegram-бот школьного расписания (с авто-уведомлениями о заменах)

Современный асинхронный Telegram-бот для просмотра расписания и автоматических уведомлений о заменах. Работает на **python-telegram-bot v20.7**, тянет данные из системы **Nikasoft (Ника-Люкс)**, отслеживает изменения в реальном времени и присылает push-уведомления подписанным пользователям.

Поддерживает **несколько школ**, кэширование, локальную JSON-БД, фоновое обновление и полноценный админ-панель с интерактивными кнопками.

---

## ✨ Возможности

- 🏫 **Несколько школ** — гибкое переключение (напр. МАОУ СОШ №133 и №181 г. Екатеринбурга).
- 📅 **Расписание**: на **Сегодня / Завтра / Неделю** — для **классов**, **преподавателей** и **кабинетов**.
- 🔄 **Автоматический мониторинг замен** — фоновый сервис проверяет данные (сегодня **и завтра**), `ExchangeDetector` ловит новые замены и шлёт уведомления; снятие замены помечается как `↩️ … — замена снята`.
- 💾 **Автосохранение** — выбранные школа и класс запоминаются в локальной JSON-БД.
- 🔔 **Подписки** — учителя и кабинеты: кнопка «Подписаться» в расписании, уведомления о заменах и список подписок в `/settings`.
- ⏰ **Напоминания об уроках** — «через N мин начнётся урок …» (тумблер в `/settings`; отдельный asyncio-цикл, без новых зависимостей).
- 🌙 **Тихие часы** — не беспокоить в заданном окне (по умолчанию 22:00–7:00), вкл/выкл в `/settings`; плюс анти-флуд и обработка Telegram `RetryAfter`.
- ⚙️ **Гибкие настройки** — смена школы/класса, вкл/выкл уведомлений, напоминаний и тихих часов.
- 👑 **Админ-панель** — статус школ, принудительное обновление, статистика пользователей, `/check_exchanges`.
- 📊 **Мониторинг статуса** — команда `/status` показывает актуальность данных по каждой школе (иконка ✅/⚠️/🔴 «Устарело»).
- 🔍 **Умный поиск** — учителя/кабинеты по имени с пагинацией, кнопками «Обновить»/«Отмена».
- 🛠️ **Качество кода** — 165 юнит/интеграционных тестов, ruff (чистый), CI.

---

## 🛠️ Технологический стек

| Слой | Технология |
|------|-----------|
| Язык | **Python 3.11+** |
| Фреймворк | [python-telegram-bot v20.7](https://github.com/python-telegram-bot/python-telegram-bot) (async API, `Application.builder()`) |
| HTTP/парсинг | `requests` (загрузка JS-файлов Nikasoft), `re` |
| БД | Локальная JSON-БД `FileDB` (потокобезопасная, атомарная запись) |
| Часовой пояс | `pytz` / `TIMEZONE` (`.env`, по умолчанию `Asia/Yekaterinburg` = UTC+5) |
| Конфигурация | `python-dotenv` |

---

## 📁 Структура проекта

```text
telegrambot/
├── bot.py                      # Точка входа: приложение, сервисы, polling
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
├── data/                        # database.json, exchange_cache.json, notifications_cache.json
├── logs/                        # bot.log (ротация 5МБ×3), admin.log
└── tests/                       # 165 pytest (юнит + интеграционные моки)
```

---

## 🚀 Быстрый старт

### 1. Клонирование и окружение

```bash
git clone https://github.com/itdevlog/telegrambot.git
cd telegrambot

python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 2. Конфигурация `.env`

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
```

> 💡 Если `TELEGRAM_TOKEN` не задан — бот не упадёт внутри PTB, а выведет понятную ошибку.
> 💡 Невалидные числовые значения (`UPDATE_INTERVAL`, `MAX_RETRIES`, `ADMIN_IDS`) дают читаемое сообщение вместо краха на импорте.

### 3. Запуск

```bash
python bot.py
```

При старте бот создаст директории `data/`, `logs/`, `cache/`, загрузит свежие данные всех активных школ и запустит фоновое обновление через `post_init`.

### Запуск под systemd (сервер)

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

## 📘 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню: расписание, учителя, кабинеты, смена школы/класса |
| `/help` | Справка |
| `/status` | Статус актуальности данных по школам |
| `/settings` | Настройки: уведомления, напоминания об уроках (`⏰`), тихие часы (`🌙`), список подписок; у админов — `update_notifications` |
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
.venv/bin/python -m pytest    # 165 тестов
```

- Юнит: нарезка сообщений, `paginate`, `get_display_name`, матчинг класса (p.11), `FileDB` (битый файл/upsert/delete_one), кэш-уведомления, callback-роутинг, `@requires_school`, exchange round-trip.
- Интеграционные (pytest-asyncio + моки): навигация, рендер меню сущности.
- CI: `.github/workflows/ci.yml` — ruff + pytest на каждый push/PR.

---

## 📚 Ссылки

- [WIKI.md](WIKI.md) — подробное устройство проекта.
- [CHANGELOG.md](CHANGELOG.md) — история изменений.
- [roadmap.md](roadmap.md) — что осталось сделать.

---

Если у вас есть вопросы или предложения — создайте [Issue](https://github.com/itdevlog/telegrambot/issues).
