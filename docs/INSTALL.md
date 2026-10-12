# Установка и развёртывание

Три независимые части, которые можно ставить по отдельности:

| Часть | Что это | Кому нужно |
|-------|---------|-----------|
| **Бот** | Telegram-бот (расписание, замены, напоминания) | Основной сценарий |
| **Mini App** | Веб-расписание внутри Telegram (FastAPI) | Если нужна кнопка в Telegram |
| **Публичный сайт** | Svelte PWA на `.ru`-домене (origin → edge) | Если нужен сайт без входа |

---

## 1. Бот

### Вариант A — одна команда (рекомендуется)

```bash
curl -fsSL https://raw.githubusercontent.com/itdevlog/raspisanie/main/manage.sh | bash -s -- install
```

Скрипт:

- спросит каталог установки (по умолчанию `/opt/raspisanie`);
- склонирует репозиторий и поставит Python-окружение и зависимости;
- интерактивно настроит `.env` (токен — у [@BotFather](https://t.me/BotFather));
- предложит systemd-сервис (автозапуск).

Недостающие системные пакеты (**git**, **curl**, **python3-venv/pip**) скрипт предложит установить сам.

> ⚠️ `curl | bash` исполняет код от root. Сначала можно просмотреть: `curl -fsSL <url> | less`.

Управление из каталога установки:

```bash
cd /opt/raspisanie
./manage.sh doctor    # диагностика: venv, .env, токен, сервис, /healthz
./manage.sh start     # запуск
./manage.sh logs      # логи
./manage.sh status    # статус + health-check
```

### Вариант B — вручную

```bash
git clone https://github.com/itdevlog/raspisanie.git /opt/raspisanie
cd /opt/raspisanie
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
pip install -r requirements.txt
cp .env.example .env             # и заполните токен/админов
python bot.py
```

Минимальный `.env`:

```env
TELEGRAM_TOKEN=123456789:ABCdef...
ADMIN_IDS=123456789
TIMEZONE=Asia/Yekaterinburg
UPDATE_INTERVAL=3600
MAX_RETRIES=3
MAX_PARALLEL_SCHOOLS=4
DB_PATH=./data/database.json
CACHE_PATH=./data/cache.json
LOG_LEVEL=INFO
LOG_FILE=./logs/bot.log
ADMIN_LOG_FILE=./logs/admin.log
```

Полный список переменных и их назначение — в [.env.example](../.env.example).

### systemd

`/etc/systemd/system/tg-schedule-bot.service`:

```ini
[Unit]
Description=Telegram School Schedule Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/raspisanie
ExecStart=/opt/raspisanie/.venv/bin/python bot.py
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

### Обновление

```bash
./manage.sh update
```

Делает бэкап `data/` + `.env` → `git pull` → обновление зависимостей → перезапуск →
health-check `/healthz` (30 с). Если бот не поднялся — **автоматический откат** к предыдущему коммиту.

### Все команды `manage.sh`

| Команда | Что делает |
|---------|------------|
| `install` | Установка: venv, зависимости, `.env`, systemd |
| `update` | Обновление с GitHub + бэкап + авто-откат |
| `start` / `stop` / `restart` | Управление ботом |
| `status` | Статус сервиса + health-check |
| `logs` | Логи в реальном времени |
| `backup` / `restore` | Бэкап и восстановление `data/` + `.env` |
| `doctor` | Диагностика окружения |
| `caddy` | HTTPS через Caddy (для Mini App) |
| `edge` | Развёртывание публичного сайта на edge-хосте |
| `uninstall` | Остановка + удаление сервиса |

---

## 2. Mini App (веб-расписание в Telegram)

Бот поднимает FastAPI-сервер (`web/`) в том же процессе.

1. Задайте `WEBAPP_URL` — **публичный HTTPS-URL** (Telegram требует HTTPS):
   ```env
   WEBAPP_HOST=127.0.0.1
   WEBAPP_PORT=8080
   WEBAPP_URL=https://schedule.example.com
   ```
2. HTTPS проще всего через Caddy (нужны открытые 80/443 и DNS на сервер):
   ```bash
   ./manage.sh caddy
   ```
   Caddy выпустит сертификат Let's Encrypt и проксирует на бота.
3. Перезапустите бота. Кнопка меню Mini App добавляется автоматически, если `WEBAPP_URL` задан.

> 🔒 `WEBAPP_HOST=127.0.0.1` по умолчанию — порт бота не торчит в интернет, наружу смотрит только Caddy.
> `WEBAPP_PORT=80`/`443` запрещён (эти порты нужны Caddy). Если веб не нужен — `WEBAPP_PORT=0`.

**Несколько ботов на одном сервере:** у каждого свой каталог, свой `.env` и свой порт; Caddy общий.
Имя инстанса берётся из имени каталога (`tg-schedule-bot-<instance>`, Caddy-фрагмент, PID-файл).
Переопределить: `./manage.sh --instance <name> <команда>` или `RASPISANIE_INSTANCE=<name>`.

---

## 3. Публичный сайт (origin → edge)

Публичный сайт без входа на отдельном `.ru`-домене. **Гео-разделение**: бот и отправка Web Push —
на **origin**; публичный сайт обслуживает **edge** из локальной копии данных (быстро из РФ).

```
Origin: бот + Nikasoft + ExchangeDetector + Web Push
        │  POST /internal/snapshot  (HMAC-SHA256 + X-Snapshot-Timestamp)
        ▼
Edge: Caddy (.ru, авто-TLS) → FastAPI (read-only API) + Svelte PWA
```

### Edge-хост

Требования: Debian/Ubuntu, DNS A-запись домена на этот сервер, открытые порты 80/443, синхронизированные часы (NTP).

```bash
git clone https://github.com/itdevlog/raspisanie.git /opt/raspisanie
cd /opt/raspisanie
sudo EDGE_DOMAIN=schedule.example.ru ./manage.sh edge
```

`deploy/edge/install.sh` поставит Caddy (авто-TLS), Node 20, Python-окружение, соберёт фронтенд,
создаст systemd-сервис `raspisanie-edge` и конфиг `/etc/raspisanie-edge.env`.

Секреты (пусто в шаблоне) заполните в `/etc/raspisanie-edge.env`:

```env
EDGE_HOST=127.0.0.1
EDGE_PORT=8090
SNAPSHOT_PATH=/var/lib/raspisanie-edge/snapshot.json
SNAPSHOT_MAX_AGE=7200
SNAPSHOT_MAX_BYTES=20971520
EDGE_INGEST_SECRET=<общий секрет с origin>
EDGE_AUTH_SECRET=<общий секрет с origin>
EDGE_ORIGIN_URL=https://origin.example.com   # для push-прокси (нужен HTTPS)
VAPID_PUBLIC_KEY=<публичный ключ>
VAPID_SUBJECT=mailto:admin@example.ru
TIMEZONE=Asia/Yekaterinburg
```

### Origin

В `.env` бота добавьте (секреты сгенерируйте и продублируйте на edge):

```env
WEBAPP_URL=https://schedule.example.ru
EDGE_INGEST_URL=https://schedule.example.ru/internal/snapshot
EDGE_INGEST_SECRET=<секрет>
EDGE_AUTH_SECRET=<секрет>
VAPID_PUBLIC_KEY=<публичный ключ>
VAPID_PRIVATE_KEY=<приватный ключ>
VAPID_SUBJECT=mailto:admin@example.ru
```

Сгенерировать VAPID-пару: `./manage.sh vapid`.

### Web Push

Нужен HTTPS-эндпоинт origin, доступный с edge (для прокси push-подписок). Тогда на edge
`EDGE_ORIGIN_URL=https://origin.example.com` (origin за reverse-proxy с TLS), и на origin заданы
VAPID-ключи + `EDGE_AUTH_SECRET`. Без этого сайт работает, но `/api/push/*` не регистрируются.

### Проверка

```bash
curl -sf https://schedule.example.ru/healthz            # {"status":"ok", ...}
curl -sf https://schedule.example.ru/api/schools
curl -sf https://schedule.example.ru/api/push/vapid-public-key
```

Подробности и чек-лист — [EDGE.md](EDGE.md).

---

## Диагностика

| Симптом | Причина / решение |
|---------|-------------------|
| Бот стартует и сразу останавливается | `WEBAPP_PORT` занят (напр. Caddy держит 80). Возьмите свободный порт или `WEBAPP_PORT=0` |
| Mini App: `404`/нет кнопки | Не задан `WEBAPP_URL` или нет HTTPS |
| Сайт: `502` | edge не может достучаться до origin — проверьте DNS/порты |
| Web Push не работает | origin не доступен по HTTPS с edge → пустой `EDGE_ORIGIN_URL` |
| Снапшот отклоняется | Разошлись часы (нужен NTP) или разные секреты |

`./manage.sh doctor` проверяет venv, зависимости, `.env`, токен, сервис и `/healthz`.
