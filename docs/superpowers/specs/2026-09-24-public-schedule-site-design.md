# Дизайн: публичный мобильный сайт расписания (гео-разделение)

Дата: 2026-09-24
Статус: утверждён (вариант A — гео-разделение, снапшот-реплика A1)
Обновлено: 2026-10-04 — уточнения после ревью плана (проверка версии/размера
снапшота; алерт по сбою публикации вместо «устаревания на origin»; push MVP —
только подписки классов).

## Цель

Выпустить публичный (без входа) мобильный сайт расписания на отдельном `.ru`
домене, доступный и быстрый из России, не затрагивая бота в Германии. Сайт —
современное PWA: просмотр расписания, избранное и share-ссылки, Web Push о
заменах, связь с Telegram-ботом.

Причина гео-разделения: бот и исходящие Web Push (FCM/Apple/Mozilla) надёжно
работают из Германии, а пользователи расписания — в России. Публичный сайт
размещается на отдельном сервере в Москве (Debian) и отвечает из локальной
реплики данных, устойчивой к деградации канала между странами.

## 1. Архитектура

```
        Интернет / пользователи в РФ            Telegram
                    │                              │
             ┌──────▼───────┐                      │
             │ Caddy (.ru)  │  TLS, автосертификат │
             │ Москва,Debian│                      │
             ├──────────────┤                      │
             │ Edge FastAPI │◄── /internal/snapshot (HMAC)
             │ Svelte PWA   │                      │
             └──────▲───────┘                      │
                    │ снапшот (JSON, раз в цикл)   │
             ┌──────┴───────┐                      │
             │ Origin       │◄─────────────────────┘
             │ Германия     │  бот, Nikasoft, ExchangeDetector,
             │ (текущий)    │  Web Push (VAPID → FCM/Apple)
             └──────────────┘
```

- **Origin (Германия, текущий сервер)** — не переезжает. Бот, загрузка
  Nikasoft, `ExchangeDetector`, отправка Web Push, публикация снапшота.
  Публично origin отдаёт только `/api/push/subscribe|unsubscribe` (защищены
  общим секретом edge `X-Edge-Auth`); остальные данные публичный сайт берёт с
  edge и origin не завязан на публичный сайт.
- **Edge (Москва, Debian)** — публичный сайт и read-only API. Отвечает из
  локальной копии данных. Если снапшот устарел — отдаёт последнюю копию и
  показывает возраст данных.

## 2. Технологический стек

| Слой | Технология | Обоснование |
|------|-----------|-------------|
| Edge API | FastAPI + uvicorn (переиспользование `web/api.py::create_app`) | Те же `ScheduleService`/`TeacherService`/`RoomService` |
| Фронтенд | Svelte 5 + Vite + TypeScript | Малый вес, реактивность, mobile-first |
| PWA | Service Worker + manifest | Офлайн-кэш расписания (логика уже есть в `web/static/service-worker.js`) |
| Push | `pywebpush` + VAPID, SW `push` event | Отправка из Германии (FCM/Apple доступны стабильно) |
| Edge-хостинг | Caddy (авто-TLS) + systemd | Как уже устроено на немецком сервере |
| Транспорт снапшота | HTTPS POST + HMAC-SHA256 | Не нужен SSH/rsync, легко тестируется |
| Хранилище подписок | `FileDB` на origin | Рядом с текущей БД, без новой инфраструктуры |

## 3. Снапшот (контракт origin → edge)

```json
{
  "version": 1,
  "generated_at": "2026-09-24T12:00:00+05:00",
  "schools": { "<school_id>": { /* SchoolData, см. services/school_types.py */ } },
  "schools_config": { "<school_id>": { "name": "...", "active": true } }
}
```

- Передаётся `POST` на `EDGE_INGEST_URL` (HTTPS) с телом JSON.
- Заголовки: `X-Snapshot-Signature` (HMAC-SHA256 от сырого тела, hex) и
  `X-Snapshot-Timestamp` (unix seconds).
- Edge отклоняет снапшот при неверной подписи, расхождении timestamp более
  ±300 с (защита от replay), неподдерживаемом `version` или теле сверх
  `SNAPSHOT_MAX_BYTES`. Ответ — 401/409/413/422 без деталей.
- Запись на edge атомарна (`tempfile` + `os.replace` + `fsync`), по образцу
  `database/file_db.py`.

## 4. Поток данных

1. `BackgroundUpdater._perform_update_locked` на origin обновляет
   `schools_data` (раз в `UPDATE_INTERVAL`, час) и ловит замены.
2. После успешного обновления (и на старте) origin публикует снапшот на edge.
   Публикация — best-effort: ошибка логируется и алертится, но не ломает
   цикл обновления. Ретраи с backoff.
3. Edge валидирует подпись, атомарно пишет `snapshot.json` и подменяет
   `schools_data` в памяти.
4. Edge FastAPI обслуживает публичные маршруты расписания из памяти; PWA
   кэширует ответы (TTL) для офлайна.
5. `GET /healthz` на edge отдаёт возраст снапшота и `version`; `status` =
   `ok`/`stale` по порогу. Origin возраст edge не видит, поэтому алертит
   админов при **провале публикации** снапшота; edge-порог — информативный.

## 5. Публичный API

- Существующие `/api/schools`, `/api/{school}/classes|teachers|rooms`,
  `/api/{school}/schedule/{kind}/{name}` (+ `/week`), `/api/{school}/search`,
  `/api/{school}/free-rooms` — уже без авторизации, публичны как есть, с
  текущим rate-limit.
- `/api/me` и `/api/widget` остаются Telegram-онли и публичным сайтом не
  используются.
- Новые на origin (защищены `X-Edge-Auth`):
  - `POST /api/push/subscribe`
  - `POST /api/push/unsubscribe`
- Новые на edge:
  - `POST /internal/snapshot` (HMAC + timestamp)
  - `GET /api/push/vapid-public-key` — отдаётся локально из `VAPID_PUBLIC_KEY`
    (публичный ключ не секрет, проксировать не нужно)
  - `POST /api/push/subscribe|unsubscribe` — reverse-proxy на origin с
    `X-Edge-Auth`
  - `GET /healthz` — `{status, snapshot_age_seconds, generated_at}`

`/api/schools` на edge берёт школы из `schools_config` снапшота; на origin —
из `SCHOOLS_CONFIG` (обратная совместимость).

## 6. Web Push

- VAPID-пара генерируется один раз, хранится в `.env` origin
  (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`).
- PWA: выбор школы/класса → кнопка «Включить уведомления о заменах» →
  `Notification.requestPermission()` → `pushManager.subscribe`.
- Подписка + выбор (`school_id`, `kind`, `name`) отправляются на edge
  `/api/push/subscribe`; edge ретранслирует на origin с `X-Edge-Auth`.
  Фронтенд общается только с `.ru` доменом (без CORS).
- Origin хранит подписки в `FileDB` (коллекция `web_push_subscriptions`:
  `endpoint`, `keys`, `school_id`, `kind`, `name`, `created_at`).
- При обнаружении замены `BackgroundUpdater._check_exchange_updates` после
  Telegram-рассылки вызывает push-сервис для подписок класса-источника
  (`kind='class'`). Entity-подписки (учитель/кабинет) — задел на будущее,
  фронтенд таких подписок в MVP не создаёт.
- Ответы 404/410 при отправке удаляют мёртвую подписку; есть очистка
  устаревших.
- Payload: `{title, body, url}`; `url` ведёт на share-страницу класса.

## 7. Фронтенд (Svelte PWA)

Экраны:

- **Главная** — выбор школы, «сегодня» для сохранённого класса.
- **Расписание** — сегодня/завтра/неделя, вкладки класс/учитель/кабинет,
  замены и отмены подсвечены, каникулы/переносы.
- **Поиск** учителей/кабинетов, **свободные кабинеты**.
- **Избранное** — школа+класс в `localStorage`.
- **Push opt-in**.
- **«Открыть в Telegram»** — deep link `t.me/<bot>?start=…`.
- **Офлайн-индикатор** — данные из TTL-кэша SW.

Share-ссылки: `/s/{school}/{kind}/{name}?date=…` (история + SPA-fallback на
edge). Приложение определяет Telegram WebApp и при наличии SDK учитывает
тему/BackButton, но работает и в обычном браузере.

## 8. Конфигурация

Origin `.env` (дополнительно):

```
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:admin@example.ru
EDGE_INGEST_URL=https://rasp.example.ru/internal/snapshot
EDGE_INGEST_SECRET=
EDGE_AUTH_SECRET=
SNAPSHOT_MAX_RETRIES=3
```

Edge `.env` (тот же `AppConfig`, edge-специфичные поля):

```
EDGE_HOST=127.0.0.1
EDGE_PORT=8090
SNAPSHOT_PATH=./data/snapshot.json
SNAPSHOT_MAX_AGE=7200
SNAPSHOT_MAX_BYTES=20971520
EDGE_INGEST_SECRET=
EDGE_AUTH_SECRET=
EDGE_ORIGIN_URL=https://origin.example.com   # edge-only: прокси push на origin
VAPID_PUBLIC_KEY=
```

`config/config.py` расширяется новыми полями `AppConfig` с дефолтами, чтобы
один и тот же модуль читался на обоих серверах.

## 9. Деплой и эксплуатация

- **Origin**: новые зависимости `pywebpush`, `cryptography`; в `.env` —
  VAPID и edge-секреты; `WEBAPP_URL` указывает на `.ru` домен (Mini App
  открывается из РФ через edge).
- **Edge (Москва)**: `deploy/edge/` — `Caddyfile`, systemd-юнит,
  `install.sh` (Caddy, venv, установка Node 20 LTS либо prebuilt `frontend/dist`,
  сборка фронтенда, каталог снапшота, сервис).
  Сервис слушает `127.0.0.1:EDGE_PORT`; наружу — только Caddy с TLS.
- **DNS**: A-запись `.ru` домена → московский сервер; Caddy выпускает
  Let's Encrypt.
- **Мониторинг**: `/healthz` на edge с возрастом снапшота; алерт админам на
  origin при провале публикации (возраст edge origin-у недоступен).
- `manage.sh` — опциональная команда `edge`, делегирующая в `install.sh`.

## 10. Безопасность

- Ingest защищён HMAC + timestamp; origin не обязан быть публичным для
  снапшота.
- `/api/push/subscribe|unsubscribe` на origin защищены `X-Edge-Auth`;
  `/api/push/vapid-public-key` публичен по природе.
- Валидация входных данных push-подписок; rate-limit API с группировкой по
  реальному клиентскому IP за прокси. Публичный subscribe на edge лимитируется,
  чтобы не забить FileDB мусором.
- Секреты только в `.env`, в репозиторий не коммитятся.

## 11. Тестирование

- `tests/test_snapshot_export.py` — формат, HMAC, ретраи, изоляция сбоя.
- `tests/test_edge_ingest.py` — приём/отклонение (подпись, timestamp, версия,
  размер), атомарность.
- `tests/test_edge_app.py` — отдача расписания без бота, `/api/schools` из
  снапшота, `/healthz`.
- `tests/test_push_service.py` — подписка/отписка, отправка, удаление
  мёртвых подписок, выбор совпавших.
- `tests/test_push_api.py` — эндпоинты, `X-Edge-Auth`.
- Фронтенд: vitest для stores/утилит; `npm run build` как проверка.
- CI: edge/backend-тесты — в общем pytest; отдельная frontend-джоба
  (`npm ci`, vitest, build).

## 12. Порядок работ

1. Спек и план (этот документ + план реализации).
2. Экспорт снапшота на origin.
3. Edge-сервер (ingest + отдача API).
4. Web Push (backend).
5. Фронтенд Svelte PWA.
6. Деплой `deploy/edge/` + обновление `.env`.
7. Документация и CI.

## Границы работы

- Бот и его Telegram-функциональность не меняются (кроме интеграции
  снапшота и Web Push в `BackgroundUpdater`).
- Веб-управление Telegram-подписками/настройками не входит.
- Аутентификация и личные кабинеты на сайте не входят (сайт публичный,
  без входа).
- Миграция `FileDB` на SQLite не входит (parked T42).

## Открытые вопросы

- Имя `.ru` домена и `VAPID_SUBJECT` (e-mail).
- Порт edge (`EDGE_PORT`, по умолчанию 8090).
- Оставлять ли старую Mini App-статику на origin как fallback.
