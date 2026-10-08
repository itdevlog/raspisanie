# 🌍 Публичный сайт: origin, edge, DNS, NTP и переменные окружения

Документ для эксплуатации публичного сайта расписания (гео-разделение origin/edge).
Разворачивание edge-хоста — в [deploy/edge/README.md](../deploy/edge/README.md);
контракт снапшота и дизайн — в
[спеке](superpowers/specs/2026-09-24-public-schedule-site-design.md) §1–§9.

---

## 1. Архитектура (кратко)

```
        Германия (origin)                        Москва (edge)
┌──────────────────────────────┐       ┌──────────────────────────────┐
│ бот + loader + push          │       │ публичный сайт (FastAPI)      │
│ Telegram-уведомления, VAPID  │──────▶│ Caddy (.ru, авто-TLS)         │
│ снапшот (SNAPSHOT_*)         │ POST  │ /api, /internal/snapshot      │
└──────────────────────────────┘ снапшот└──────────────────────────────┘
        EDGE_INGEST_URL                   ▲
        (HMAC + timestamp)                │ HTTPS
                                     Интернет (РФ)
```

- **Origin (Германия)** — текущий бот: загрузка данных Nikasoft, Telegram-рассылки,
  отправка Web Push. **Публикует** снапшот расписания на edge через
  `POST EDGE_INGEST_URL` (тело — JSON, HMAC-подпись, заголовок `X-Snapshot-Timestamp`).
- **Edge (Москва)** — публичный (без входа) сайт FastAPI, за Caddy с авто-TLS на
  `.ru`-домене. Принимает снапшот на `/internal/snapshot` и **проксирует**
  публичное push-API на origin (`EDGE_ORIGIN_URL`).
- `WEBAPP_URL` origin указывает на `.ru`-домен: Telegram Mini App открывается из РФ
  через edge.

Подробности SPA-fallback, `X-Forwarded-For` и rate-limit — в
[deploy/edge/README.md](../deploy/edge/README.md).

---

## 2. DNS: A-запись `.ru` → московский сервер

| Запись | Значение | Назначение |
|--------|----------|------------|
| `A` | IP **московского** edge-сервера | Публичный домен `.ru` (например, `raspisanie.example.ru`) |

- A-запись создаётся **до** запуска `install.sh`: Caddy выпускает сертификат
  Let's Encrypt через HTTP-01 challenge, а он требует, чтобы домен уже резолвился на
  этот хост и были открыты порты **80/443**.
- `EDGE_DOMAIN` в `install.sh`/`./manage.sh edge` должен совпадать с этой A-записью
  (скрипт отказывается работать без реального домена — чтобы не выпустить
  сертификат на чужое имя).
- Домен также попадает в `WEBAPP_URL` origin (см. §4) и в `EDGE_INGEST_URL`
  (`https://<домен>/internal/snapshot`).

---

## 3. NTP: синхронизация часов на ОБОИХ хостах

Система принимает снапшот только если расхождение часов не превышает **±300 с**.
Проверка живёт в `web/edge_ingest.py`:

- `TIMESTAMP_TOLERANCE_SECONDS = 300`;
- `_check_timestamp` отклоняет отсутствующий/нечисловой/не-конечный timestamp и
  значение, отклонившееся от `now()` более чем на 300 с (защита от replay);
- ответ при провале — `422` без деталей.

Отсюда **обязательное требование**: NTP включён и на origin, и на edge.

```bash
# Debian/Ubuntu (systemd-timesyncd обычно уже включён):
timedatectl status            # ждём "System clock synchronized: yes" и NTP service: active
sudo timedatectl set-ntp true

# Проверка расхождения с ближайшим сервером:
timedatectl show-timesync --all
chronyc tracking              # если установлен chrony
```

Без синхронизации часов публикация снапшота будет стабильно получать `422`
(«timestamp вне допуска»), и edge останется со stale-данными, даже если origin
работает штатно. Это первое, что нужно проверить при `422` на ingest.

---

## 4. Переменные окружения: origin vs edge

Оба сервера читают один и тот же `config/config.py` (`AppConfig`), но заполняют
разные поля. Полный шаблон origin — `.env.example` в корне репозитория; шаблон
edge — `deploy/edge/edge.env.example` (копируется в `/etc/raspisanie-edge.env`).

> **Ключевое различие:** `EDGE_INGEST_URL`/`EDGE_INGEST_SECRET` — это **origin-only**
> настройки (куда origin *шлёт* снапшот). А `EDGE_HOST`/`EDGE_PORT` и другие
> `EDGE_*` серверные настройки — **edge-only** (как edge *принимает* запросы).
> `EDGE_ORIGIN_URL` — **только edge** (куда edge *проксирует* push на origin).

### Origin (Германия)

| Переменная | Дефолт в `config.py` | Назначение |
|------------|----------------------|------------|
| `VAPID_PUBLIC_KEY` | `''` | Публичный VAPID-ключ (Web Push). Отдаётся edge-ом браузеру. |
| `VAPID_PRIVATE_KEY` | `''` | Приватный ключ подписи push. **Секрет**, не коммитить. |
| `VAPID_SUBJECT` | `mailto:admin@example.ru` | Контакт VAPID (`mailto:`/URL). |
| `EDGE_INGEST_URL` | `''` | URL ingest edge: `https://<домен>/internal/snapshot`. Пусто — публикация выключена. |
| `EDGE_INGEST_SECRET` | `''` | Общий HMAC-секрет тела снапшота (совпадает с edge). **Секрет**. |
| `EDGE_AUTH_SECRET` | `''` | Общий секрет origin↔edge: edge добавляет `X-Edge-Auth` при прокси push. **Секрет**. |
| `SNAPSHOT_MAX_RETRIES` | `3` | Ретраи публикации снапшота (не путать с `MAX_RETRIES` загрузки). |
| `SNAPSHOT_MAX_BYTES` | `20971520` | Максимальный размер **публикуемого** снапшота (байт); тот же лимит edge применяет к приёму. |
| `SNAPSHOT_PATH` | `./data/snapshot.json` | **на origin не используется** — origin не пишет файл, а шлёт тело снапшота по HTTP; переменную читает только edge (см. ниже). |
| `SNAPSHOT_MAX_AGE` | `7200` | **на origin не используется** — читается только на edge (healthz/stale). |
| `WEBAPP_URL` | `''` | **→ `.ru`-домен**: Telegram Mini App открывается из РФ через edge. |

### Edge (Москва)

| Переменная | Дефолт в `config.py` | Назначение |
|------------|----------------------|------------|
| `EDGE_HOST` | `127.0.0.1` | Хост FastAPI edge (loopback; наружу — Caddy). |
| `EDGE_PORT` | `8090` | Порт FastAPI edge (должен совпадать с `{$EDGE_PORT}` в `Caddyfile`). |
| `SNAPSHOT_PATH` | `./data/snapshot.json` | Файл принятого снапшота (в `install.sh` — `/var/lib/raspisanie-edge/snapshot.json`). |
| `SNAPSHOT_MAX_AGE` | `7200` | Возраст (сек) до пометки stale в `/healthz` и UI. |
| `SNAPSHOT_MAX_BYTES` | `20971520` | Максимальный **принимаемый** размер снапшота (байт). |
| `EDGE_INGEST_SECRET` | `''` | HMAC-секрет входящего снапшота (совпадает с origin). **Секрет**. |
| `EDGE_AUTH_SECRET` | `''` | Общий секрет origin↔edge для прокси push. **Секрет**. |
| `EDGE_ORIGIN_URL` | `''` | **edge-only**: базовый URL origin для прокси public push-API. Включается только вместе с `EDGE_AUTH_SECRET`; иначе push-маршруты не регистрируются (vapid-public-key → 404). |
| `VAPID_PUBLIC_KEY` | `''` | Публичный ключ, отдаётся локально эндпоинтом `/api/push/vapid-public-key`. |
| `VAPID_PRIVATE_KEY` | `''` | Нужен origin для отправки; на edge можно оставить пустым. |
| `VAPID_SUBJECT` | `mailto:admin@example.ru` | Контакт VAPID. |

> `SNAPSHOT_MAX_RETRIES` на edge не используется (значение читается `AppConfig`,
> но ретраи — забота origin). В `edge.env.example` он оставлен для совместимости.

Секреты (`EDGE_INGEST_SECRET`, `EDGE_AUTH_SECRET`, `VAPID_PRIVATE_KEY`) заполняются
на серверах в `.env`/`/etc/raspisanie-edge.env` и **не коммитятся** в репозиторий.

---

## 5. Build-time переменные фронтенда

| Переменная | Где | Назначение |
|------------|-----|------------|
| `VITE_TELEGRAM_BOT` | сборка `frontend/dist` (Vite, W24) | Имя бота без `@` для кнопки «Открыть в Telegram». **Если не задана — кнопка скрыта** (`frontend/src/components/OpenInTelegram.svelte`, `frontend/src/lib/telegram.ts`). |

Это переменная **сборки**, а не рантайма: её нужно задать в окружении перед
`npm run build` (в CI или в `install.sh`), иначе в собранном `frontend/dist`
кнопка «Открыть в Telegram» отсутствует.

---

## 6. Web Push: как устроено

origin **регистрирует** публичные маршруты `/api/push/subscribe` и
`/api/push/unsubscribe`, когда заданы VAPID-ключи и `EDGE_AUTH_SECRET`
(`web/api.py`). `PushSubscriptionStore` (`services/push_store.py`) создаётся из
`FileDB` бота в `bot.py::setup_services` и передаётся в `create_app(...)` из
`web/server.py::run_webapp` через `bot_data['push_store']`. Подписки хранятся в
коллекции `web_push_subscriptions`.

Поток подписки:

- браузер отправляет только тело JSON на **edge** `/api/push/subscribe`
  (секрет в клиенте не хранится);
- edge-прокси (`web/edge_push.py`) добавляет заголовок `X-Edge-Auth` и
  проксирует запрос на origin `{EDGE_ORIGIN_URL}/api/push/...`;
- origin проверяет `X-Edge-Auth` и сохраняет подписку;
- `GET /api/push/vapid-public-key` отдаётся **edge** локально из
  `VAPID_PUBLIC_KEY` (origin такого маршрута не имеет);
- per-client rate-limit `/api/push/*` живёт на **edge** (origin вызывается
  единственным peer-IP — edge — поэтому лимит там схлопнулся бы в одну корзину).

Telegram-уведомления о заменах работают как раньше и от этого не зависят.

---

## 7. Чек-лист развёртывания

- [ ] A-запись `.ru` → московский сервер создана, порты 80/443 открыты.
- [ ] **NTP синхронизирован на origin и на edge** (`timedatectl status` → synchronized).
- [ ] Origin `.env`: `VAPID_*`, `EDGE_INGEST_URL` (`https://<домен>/internal/snapshot`),
      `EDGE_INGEST_SECRET`, `EDGE_AUTH_SECRET`, `SNAPSHOT_MAX_RETRIES`,
      `WEBAPP_URL=https://<домен>`.
- [ ] Edge `/etc/raspisanie-edge.env`: `EDGE_HOST`/`EDGE_PORT`,
      `SNAPSHOT_PATH`/`SNAPSHOT_MAX_AGE`/`SNAPSHOT_MAX_BYTES`, `EDGE_INGEST_SECRET`,
      `EDGE_AUTH_SECRET`, `EDGE_ORIGIN_URL`, `VAPID_PUBLIC_KEY`.
- [ ] Перед сборкой фронтенда задана `VITE_TELEGRAM_BOT` (иначе кнопка скрыта).
- [ ] Проверка: `curl -sf https://<домен>/healthz` (возраст снапшота) и
      `curl -sf https://<домен>/api/push/vapid-public-key`.
- [ ] Проверка Web Push: `curl -sf https://<домен>/api/push/vapid-public-key`
      возвращает `{"key": ...}`; тестовая подписка (кнопка «Включить
      уведомления») сохраняется и видна на origin в коллекции
      `web_push_subscriptions`.
