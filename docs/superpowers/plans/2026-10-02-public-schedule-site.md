# Публичный сайт расписания — план реализации

**Дата:** 2 октября 2026
**Статус:** ✅ MVP (W1–W31) реализован 2026-10-05; ✅ паритет (W32–W41) реализован 2026-10-05 (все 41 задача закрыта)
**Деплой:** сотрудник — «(указывается при деплое)», дата — «(указывается при деплое)»
**Спека:** [docs/superpowers/specs/2026-09-24-public-schedule-site-design.md](../specs/2026-09-24-public-schedule-site-design.md)
**Стиль:** как T1–T45 в [DEVELOPMENT_PLAN.md](../../../DEVELOPMENT_PLAN.md) — фазы, сквозные ID, файлы и критерии готовности.
**Нумерация:** `W1…W41` (Website), чтобы не путаться с закрытыми `T1–T45`:
`W1–W31` — базовый публичный сайт (MVP), `W32–W41` — паритет с оригиналом Nikasoft.
**Как исполнять:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (задача на субагента + ревью) или `superpowers:executing-plans` (самому по шагам); закрытые задачи отмечать `- [x]`.

---

## Review Focus (на что смотреть в первую очередь)

- **Rate-limit за reverse-proxy.** За Caddy `request.client.host` — всегда `127.0.0.1`; лимит обязан группировать по реальному IP (W8), иначе 100 req/min на весь сайт.
- **Устаревший снапшот / дрейф часов.** Timestamp старше ±300 с отвергается; часы origin/edge — на NTP, UI показывает возраст данных (W4/W9/W11/W23/W28).
- **Бомба в теле снапшота.** Oversized/битый JSON не должен ронять edge или писать на диск: лимит размера + проверка `version` (W2/W3/W9/W30).
- **Спам на публичный subscribe.** `POST /api/push/subscribe` на edge открыт; без валидации и лимита FileDB забивается мусором (W12/W15/W17).
- **Мёртвые подписки.** `404/410` удаляем; прочие (transient) ошибки не должны стирать живую подписку (W13).
- **Паритет на реальных данных.** Новые поля (`shift`, `groups`, `period`, метод-час, календарь, Пн–Сб) обязаны строиться из фактической выгрузки Nikasoft, а не из предположений о формате (W33/W34/W41).

---

## Цель

Выпустить публичный (без входа) мобильный сайт расписания на отдельном `.ru`-домене,
доступный и быстрый из России, не затрагивая бота в Германии: просмотр расписания,
избранное, share-ссылки, Web Push о заменах, связь с Telegram-ботом.

## Архитектура (из спеки)

- **Origin (Германия, текущий сервер)** — не переезжает. Бот, Nikasoft, `ExchangeDetector`,
  Web Push, публикация снапшота. Публично отдаёт только `/api/push/subscribe|unsubscribe`
  (защищены `X-Edge-Auth`).
- **Edge (Москва, Debian)** — публичный сайт и read-only API из локальной копии данных
  (снапшот). Отвечает даже при устаревшем снапшоте, показывая возраст данных.
- Снапшот передаётся `HTTPS POST` + `HMAC-SHA256` + timestamp, записывается атомарно.

## Технологический стек

- **Backend:** Python 3.11+ (FastAPI + uvicorn, `httpx`, `pywebpush` + `cryptography`).
- **Frontend:** Svelte 5 + Vite + TypeScript, PWA (Service Worker + manifest).
- **Edge-хостинг:** Caddy (авто-TLS) + systemd.
- **Хранилище подписок:** существующий `FileDB` (коллекция `web_push_subscriptions`).

## Global Constraints

- Python 3.11+; `ruff` line-length 120; `mypy .` — 0 ошибок; CI зелёный.
- Проверка после каждой задачи: `ruff check . && mypy . && pytest -q`
  (`TELEGRAM_TOKEN=dummy` уже в CI).
- Поведение бота и Telegram-функциональность **не меняются** (кроме интеграционных
  хуков снапшота и push в `BackgroundUpdater`). Существующие тексты сообщений не трогаем.
- Секреты (HMAC, VAPID private) — только в `.env`, в репозиторий не коммитятся.
- Edge — **отдельный процесс** с тем же кодом, но **без бота**: только FastAPI из снапшота.
- Origin не обязан быть публично доступен для публикации снапшота.
- Публичные маршруты edge — без авторизации, с существующим rate-limit; CORS не нужен
  (фронтенд общается только со своим доменом).
- Frontend: Node 20 LTS; сборка обязана проходить (`npm ci && npm run build`).
- Коммиты: `Feat: …`, `Fix: …`, `Docs: …`, `Test: …`, `Deploy: …`.

---

## Фаза 1 — Конфиг, снапшот, хранилище (фундамент)

- [x] **W1. Расширить `AppConfig` edge/snapshot/push-полями.** Добавить в `AppConfig.from_env()`
  и фасад `Config` (UPPER_CASE): `EDGE_HOST` (127.0.0.1), `EDGE_PORT` (8090),
  `SNAPSHOT_PATH` (./data/snapshot.json), `SNAPSHOT_MAX_AGE` (7200),
  `SNAPSHOT_MAX_BYTES` (20 MiB, положительный int), `SNAPSHOT_MAX_RETRIES` (3, ≥1 —
  **отдельно** от `MAX_RETRIES`, который задаёт ретраи `DataLoader`),
  `EDGE_INGEST_URL`, `EDGE_INGEST_SECRET`, `EDGE_AUTH_SECRET`,
  `EDGE_ORIGIN_URL` (нужен только edge — прокси push на origin; на origin может быть пустым),
  `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`
  (`mailto:admin@example.ru`). Порт — через `_parse_port`; возраст и размер — положительные int.
  В `.env.example` пометить edge-only поля.
  *Файлы: config/config.py, .env.example, tests/test_app_config.py, tests/test_config_validation.py.*

- [x] **W2. Модуль снапшота `services/snapshot.py`.** Формат v1
  `{version, generated_at, schools, schools_config}` с константой `SNAPSHOT_VERSION = 1`;
  функции `build_snapshot(schools_data, schools_config, now=None)` (проставляет `version`),
  `serialize_snapshot(snapshot) -> bytes` (компактный UTF-8, `ensure_ascii=False`),
  `sign_payload(secret, body) -> hex`,
  `verify_signature(secret, body, sig)` (через `hmac.compare_digest`),
  `write_snapshot_atomic(path, snapshot)` (tmp + `fsync` + `os.replace`, по образцу
  `database/file_db.py`) и `read_snapshot(path) -> dict | None`.
  `serialize_snapshot` возвращает и логирует размер; тела сверх `SNAPSHOT_MAX_BYTES`
  не публикуются (W4) и отвергаются на edge (W9).
  *Файлы: services/snapshot.py, tests/test_snapshot_format.py.*

- [x] **W3. Хранилище снапшота на edge `services/snapshot_store.py`.** Класс
  `SnapshotStore(path, max_age)`: `load()` со старта, `apply(payload)` под `threading.RLock`
  (применяет только `version == SNAPSHOT_VERSION`, иначе не подменяет данные),
  `schools_data`, `schools_config`, `generated_at`, `version`, `age_seconds()`, `is_stale`.
  Потокобезопасно (читает FastAPI, пишет ingest). *Файлы: services/snapshot_store.py,
  tests/test_snapshot_store.py.*

## Фаза 2 — Экспорт снапшота на origin

- [x] **W4. `services/snapshot_exporter.py` — публикация на edge.** `httpx.Client` POST на
  `EDGE_INGEST_URL` с заголовками `X-Snapshot-Signature` (HMAC-SHA256 сырого тела, hex) и
  `X-Snapshot-Timestamp` (unix seconds). Тело — `serialize_snapshot`; если размер превышает
  `SNAPSHOT_MAX_BYTES` — не публиковать, залогировать и вернуть `False`; большие тела сжимать
  (`Content-Encoding: gzip`, edge декомпрессирует). Ретраи с backoff (`SNAPSHOT_MAX_RETRIES`),
  таймаут, best-effort: ошибку логирует и возвращает `False`, не бросает. Метрики
  `snapshot_published` / `snapshot_publish_errors`. *Файлы: services/snapshot_exporter.py,
  tests/test_snapshot_export.py.*

- [x] **W5. Публикация в `BackgroundUpdater`.** Вызвать экспортёр в `_perform_update`
  **после выхода из `async with self._update_lock`** (у `_perform_update_locked` нет
  возвращаемого признака успеха) и **только если** `new_schools_data` непустой; свежие
  `schools_data` + `schools_config` берутся из `bot_data`. Синхронный `publish` вызывать
  через `asyncio.to_thread`, независимо от результата рассылок. Ошибка публикации не ломает
  цикл обновления; повторяющиеся сбои — через существующий `_alert_repeated_error` (антиспам).
  *Файлы: core/background_updater.py, tests/test_background_updater_snapshot.py.*

- [x] **W6. Публикация при старте и регистрация сервисов.** В `setup_services()` создать
  `SnapshotExporter` (по `Config`) и положить в `bot_data`; в `_post_init` опубликовать
  снапшот после первичной загрузки `schools_data` (она синхронна и идёт до event loop —
  `load_schools_data()`), вызовом через `asyncio.to_thread`, чтобы не блокировать loop.
  Если `EDGE_INGEST_URL` пуст — сервис выключен, в логи info.
  *Файлы: bot.py, tests/test_startup_snapshot.py.*

- [x] **W7. Ручное обновление админа тоже публикует снапшот.** После успешного
  admin-refresh (существующий flow) вызвать `snapshot_exporter.publish(...)`, чтобы
  ручная правка сразу доезжала до edge. *Файлы: handlers/callbacks/admin_callbacks.py,
  tests/test_admin_refresh_invalidation.py.*

## Фаза 3 — Edge-сервер (ingest + публичный API)

- [x] **W8. Переиспользовать `create_app` на edge.** Параметризовать `create_app`:
  `schools_config` из `services` (fallback на импорт `SCHOOLS_CONFIG`), `static_dir`
  (default `web/static`), флаг `enable_telegram_routes` (для edge — off: без `/api/me`,
  `/api/widget`), health-провайдер для доп. полей. **Rate-limit должен группировать по
  реальному клиенту:** за Caddy `request.client.host` — это `127.0.0.1`; брать IP из первого
  доверенного `X-Forwarded-For` (прокси в белом списке), иначе лимит схлопывается в один
  bucket на весь сайт. Поведение origin не меняется (существующие тесты зелёные).
  *Файлы: web/api.py, web/rate_limit.py (при необходимости), tests/test_webapp_api.py,
  tests/test_rate_limit.py.*

- [x] **W9. Ingest-эндпоинт `POST /internal/snapshot`.** Отдельный роутер
  `web/edge_ingest.py`: читает сырое тело (с декомпрессией gzip), проверяет размер
  (`SNAPSHOT_MAX_BYTES` → `413`), `X-Snapshot-Signature` (`hmac.compare_digest`),
  `X-Snapshot-Timestamp` (±300 с) и `version == SNAPSHOT_VERSION`; при ошибке —
  `401/409/413/422` без деталей; при успехе — `write_snapshot_atomic` + `store.apply`,
  ответ `{ok: true}`. Роутер вне rate-limit middleware (тот смотрит только `/api/`).
  *Файлы: web/edge_ingest.py, tests/test_edge_ingest.py.*

- [x] **W10. Edge-приложение и раннер `web/edge_server.py`.** `create_edge_app(store)` =
  `create_app` c `schools_config` из снапшота, `enable_telegram_routes=False`, статика
  собранного фронтенда; ingest-роутер; `GET /api/schools` берёт активные школы из
  `schools_config` снапшота. `python -m web.edge_server` поднимает uvicorn на
  `EDGE_HOST:EDGE_PORT`. *Файлы: web/edge_server.py, tests/test_edge_app.py.*

- [x] **W11. `/healthz` с возрастом снапшота.** На edge `GET /healthz` →
  `{status, snapshot_age_seconds, generated_at, version, schools_count}`; `status` =
  `ok`/`stale` по `SNAPSHOT_MAX_AGE`. Origin **не видит** возраст на edge, поэтому алертит
  админов при **провале публикации** (W4/W5); edge-порог — информативный (мониторинг/UI).
  *Файлы: web/edge_server.py, web/api.py, tests/test_edge_app.py.*

## Фаза 4 — Web Push (backend origin)

- [x] **W12. Хранилище подписок `services/push_store.py`.** Коллекция FileDB
  `web_push_subscriptions` (`endpoint` уникален, `keys`, `school_id`, `kind`, `name`,
  `created_at`): `upsert` (по `endpoint` через `update_one(..., upsert=True)`),
  `remove_by_endpoint`, `find_matching(school_id, kind, name)`,
  `remove_dead(endpoints)`, `cleanup_stale(older_than)`. Валидация: `endpoint` — https-URL
  разумной длины, `keys.p256dh`/`keys.auth` непустые, `kind ∈ {class, teacher, room}`.
  MVP создаёт только `kind='class'` (фронтенд предлагает opt-in класса); `kind`/`name`
  оставлены под будущие entity-подписки. *Файлы: services/push_store.py, tests/test_push_store.py.*

- [x] **W13. `services/push_service.py` — отправка.** Читает VAPID из конфига;
  `send_exchange_notifications(subscriptions, title, body, url)` через `pywebpush.webpush`
  в `asyncio.to_thread`; ответы `404/410` удаляют мёртвую подписку; payload
  `{title, body, url}`. Ключи для ECE — `pywebpush` + `cryptography` в `requirements.txt`.
  *Файлы: services/push_service.py, requirements.txt, tests/test_push_service.py.*

- [x] **W14. Генерация VAPID-пары.** Модуль/CLI
  (`python -m services.push_keys`) печатает `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`
  (base64url, P-256) и безопасно подсказывает записать их в `.env`; опциональная
  команда `./manage.sh vapid`. *Файлы: services/push_keys.py, manage.sh,
  tests/test_push_keys.py.*

- [x] **W15. Публичное push-API origin.** `POST /api/push/subscribe` и
  `POST /api/push/unsubscribe`, защищены `X-Edge-Auth` (`compare_digest`); при
  несовпадении — `403`. Валидация подписки; включены, только если заданы VAPID-ключи и
  `EDGE_AUTH_SECRET`. Дополнительно ограничить частоту subscribe (переиспользовать
  `RateLimiter`), чтобы публичный edge-proxy не мог забить FileDB мусором.
  `/api/push/vapid-public-key` на origin не обязателен (публичный — на edge).
  — ⚠️ проводка origin `push_store` в `run_webapp` отложена (см. docs/EDGE.md §6 / WIKI §13.1).
  *Файлы: web/push_api.py, web/api.py, tests/test_push_api.py.*

- [x] **W16. Отправка push при заменах.** В `BackgroundUpdater._check_exchange_updates`
  после Telegram-рассылки вызвать push для подписок класса-источника замен
  (`find_matching(school_id, 'class', class_name)`); URL ведёт на share-страницу класса.
  Entity-push (teacher/room) в MVP не рассылаем — фронтенд таких подписок не создаёт
  (см. W12). Ошибки push не влияют на Telegram-доставку и не меняют baseline замен.
  *Файлы: core/background_updater.py, tests/test_background_updater_push.py.*

## Фаза 5 — Edge push-proxy

- [x] **W17. Push-маршруты на edge.** `GET /api/push/vapid-public-key` отдаёт локально
  `VAPID_PUBLIC_KEY`; `POST /api/push/subscribe|unsubscribe` проксирует на
  `EDGE_ORIGIN_URL` с заголовком `X-Edge-Auth` через `httpx`, пробрасывая статус/тело.
  Ограничение на размер тела и таймаут; маршруты под общим `/api/` rate-limit
  (покрыты middleware, см. W8). *Файлы: web/edge_push.py, web/edge_server.py,
  tests/test_edge_push_proxy.py.*

## Фаза 6 — Фронтенд Svelte PWA

- [x] **W18. Каркас Svelte 5 + Vite + TS.** Каталог `frontend/`, сборка в `frontend/dist`
  (потребляется edge), `package.json` (`dev`/`build`/`test`), tsconfig, линт/формат;
  `node_modules/`/`dist/` в `.gitignore`. *Файлы: frontend/**, .gitignore.*

- [x] **W19. API-клиент и stores.** Типизированный клиент публичных маршрутов
  (`/api/schools`, `/classes|teachers|rooms`, `/schedule/...`, `/search`, `/free-rooms`),
  store выбранной школы/класса в `localStorage`, TZ-корректное «сегодня» (по серверу).
  *Файлы: frontend/src/lib/**, tests (vitest).*

- [x] **W20. Экраны расписания.** Главная (выбор школы, «сегодня» для сохранённого
  класса); расписание: сегодня/завтра/неделя, вкладки класс/учитель/кабинет, подсветка
  замен и отмен, каникулы/переносы. *Файлы: frontend/src/routes/**, tests.*

- [x] **W21. Поиск и свободные кабинеты.** Поиск учителей/кабинетов и «свободные
  кабинеты» без `window.prompt` (inline-выбор урока), как в Mini App. *Файлы:
  frontend/src/**, tests.*

- [x] **W22. Share-ссылки и маршрутизация.** `/s/{school}/{kind}/{name}?date=…`
  открывает нужный экран; history + SPA-fallback на edge (см. W26). *Файлы:
  frontend/src/**, deploy/edge/Caddyfile.*

- [x] **W23. PWA: push opt-in, офлайн, SW.** Кнопка «Включить уведомления» → permission →
  `pushManager.subscribe` (ключ с `/api/push/vapid-public-key`) → POST на edge; офлайн-
  индикатор и TTL-кэш расписания (логику `web/static/service-worker.js` переиспользовать);
  manifest + иконки. *Файлы: frontend/**, frontend/public/**.*

- [x] **W24. Telegram-интеграция.** Определять Telegram WebApp, учитывать тему/BackButton
  при наличии SDK; «Открыть в Telegram» — deep link `t.me/<bot>?start=…`; в обычном
  браузере всё работает без SDK. *Файлы: frontend/src/**, tests.*

- [x] **W25. Тесты фронтенда.** vitest для stores/утилит/API-клиента; `npm run build` как
  обязательная проверка. *Файлы: frontend/**, package.json.*

## Фаза 7 — Деплой edge

- [x] **W26. `deploy/edge/`.** `Caddyfile` (домен `.ru`, авто-TLS, `try_files`/SPA-fallback,
  прокси на `127.0.0.1:EDGE_PORT`, статика `frontend/dist`), systemd-юнит,
  `install.sh` (Caddy, venv, **установка Node 20 LTS**, если его нет — nodesource/nvm, либо
  доставка собранного `frontend/dist` из CI; затем `npm ci && npm run build`, каталог
  снапшота, сервис). Без этого шага сборка на чистом Debian-хосте не пройдёт.
  *Файлы: deploy/edge/**.*

- [x] **W27. Команда `./manage.sh edge`.** Делегирует в `deploy/edge/install.sh`,
  добавляется в `cmd_help` и `doctor` (подсказка для edge-хоста); проходит `shellcheck`.
  *Файлы: manage.sh, tests (shellcheck в CI).*

- [x] **W28. DNS/`.env`/окружения.** Документировать A-запись `.ru` → московский сервер
  (+ NTP на обоих хостах — от него зависит допуск ±300 с), origin-переменные (VAPID,
  `EDGE_INGEST_*`, `EDGE_AUTH_SECRET`, `WEBAPP_URL` → `.ru`, `SNAPSHOT_MAX_RETRIES`) и
  edge-переменные (`EDGE_*`, `SNAPSHOT_PATH`, `SNAPSHOT_MAX_AGE`, `SNAPSHOT_MAX_BYTES`,
  `VAPID_PUBLIC_KEY`; `EDGE_ORIGIN_URL` — только edge). *Файлы: .env.example,
  docs/EDGE.md, WIKI.md.*

## Фаза 8 — Документация и CI

- [x] **W29. CI: frontend-джоба.** Отдельный job `frontend` (`actions/setup-node` 20,
  `npm ci`, `npm run test`, `npm run build`) рядом с backend; backend-матрица не меняется.
  Кэш npm. *Файлы: .github/workflows/ci.yml.*

- [x] **W30. End-to-end тест контракта origin→edge.** Прогнать `build_snapshot` →
  HMAC → ingest (через `TestClient`/мок httpx) → отдача расписания edge-приложением;
  проверить отклонение просроченного timestamp, битой подписи, неподдерживаемого `version`
  и тела сверх `SNAPSHOT_MAX_BYTES`, а также приём gzip. *Файлы:
  tests/test_snapshot_e2e.py.*

- [x] **W31. Документация и статусы.** Обновить `WIKI.md`, `README.md`, `CHANGELOG.md`,
  `roadmap.md`; проставить статус спеки и плана; отметить сотрудника/дату деплоя.
  *Файлы: WIKI.md, README.md, CHANGELOG.md, roadmap.md.*

## Фаза 9 — Паритет с оригиналом Nikasoft (W32–W41)

> Источник — оригинальный сайт `raspisanie.nikasoft.ru/55812556.html`. Данные уже
> есть: `DataLoader.download_schedule_data` (`core/data_loader.py:161`) сохраняет
> **весь** словарь `NIKA`, поэтому `CLASS_SHIFT`, `CLASSGROUPS`, `CLASS_COURSES`,
> `TEACH_SCHEDULE`, `WEEKDAYNUM`, флаги `SHOW_*` попадают и в снапшот. Не хватает
> только типов, API-полей и фронтенда. Telegram-формат сообщений не меняется.

- [x] **W32. Типы и метаданные школы.** Дополнить `SchoolData` (`services/school_types.py`):
  `WEEKDAYNUM: int`, `FIRSTLESSONNUM: int`, `CLASS_COURSES: dict[str, int]`,
  `CLASSGROUPS: dict[str, dict[str, str]]`, `CLASS_SHIFT: dict`,
  `TEACH_SCHEDULE: dict[str, dict[str, LessonData]]` и флаги
  `SHOW_TEACHERS/SHOW_CLASSROOMS/USEROOMS/HOMEPAGE_BTN/SECOND_RELATIVE/SHOW_EXCHANGES_TERM: bool`.
  В `/api/schools` (`web/api.py`) на каждую школу добавить `city` (из `SCHOOLS_CONFIG`,
  fallback `CITY_NAME`), `updated` (`EXPORT_DATE` + `EXPORT_TIME`), `homepage_url`
  (`HOMEPAGE_URL`) и `features` `{teachers, classrooms, rooms, homepage}` из флагов
  (default `True`). *Файлы: services/school_types.py, web/api.py, tests/test_webapp_api.py.*

- [x] **W33. День: смена, период, группы, метод-час.** В `BaseScheduleService`:
  `get_period_info(date) -> dict | None` (b/e/name из `PERIODS`); `_day_payload`
  добавляет `period` (name + b/e) и `shift` (номер второй смены из `CLASS_SHIFT`
  для класса, иначе `None`); в `_lessons_payload` каждый item получает `groups`
  (названия групп из `CLASSGROUPS` по division-ключу урока, выровненные с
  параллельными списками; иначе `None`) и `is_method_hour` (предмет урока —
  метод-час `'M'`). Влияет только на payload `get_day` (Telegram-формат не трогаем).
  *Файлы: services/base_schedule_service.py, tests/test_schedule_payload_parity.py.*

- [x] **W34. Неделя Пн–Сб по `WEEKDAYNUM`.** `_week_dates` берёт число учебных дней из
  `school_data['WEEKDAYNUM']` (default 5, clamp 1..6) вместо жёсткого `range(5)`;
  свойство `weekday_num`; route `/week` возвращает `{days: [...], weekday_num: n}`.
  Telegram-кэш `_get_week_schedule` **не трогаем** — поведение бота прежнее.
  *Файлы: services/base_schedule_service.py, web/api.py, tests/test_week_payload.py.*

- [x] **W35. Календарь месяца (API).** `BaseScheduleService.get_month(entity, year, month)
  -> list[dict]`: по каждому дню месяца `{date, day_name, weekend, vacation, no_period,
  has_exchange, has_cancelled, lesson_count}` на основе `self.get_day`. Route
  `GET /api/{school_id}/schedule/{kind}/{name}/calendar?year=&month=`
  (`year>=2020`, `month 1..12`). *Файлы: services/base_schedule_service.py,
  web/api.py, tests/test_schedule_calendar.py.*

- [x] **W36. Текущий/следующий урок (публичный API).** Вынести выбор в
  `BaseScheduleService.select_current_and_next(lessons, date, now=None)` и
  переиспользовать в `/api/widget/{user_id}` вместо inline-кода (поведение виджета
  не меняется). Route `GET /api/{school_id}/schedule/{kind}/{name}/now?date=` →
  `{server_time, current, next}`. *Файлы: services/base_schedule_service.py,
  web/api.py, tests/test_schedule_now.py, tests/test_webapp_api.py.*

- [x] **W37. Поиск классов.** `ScheduleService.search_classes(q) -> list[str]` (по
  `CLASSES`, как `search_teachers`/`search_rooms`); route `/search` добавляет
  `'classes'`. *Файлы: services/schedule_service.py, web/api.py, tests/test_webapp_api.py.*

- [x] **W38. Фронтенд: календарь месяца.** Экран месяца для класса/учителя с
  API-клиентом `getCalendar`, маркерами замен/каникул и переходом в день;
  навигация по неделям/месяцам. *Файлы: frontend/src/**, tests (vitest).*

- [x] **W39. Фронтенд: главная и избранное.** Главная: город + «Обновлено» + ссылка
  на сайт школы (`features.homepage`); виджет «идёт урок / до начала» из `/now`;
  избранное для класса/учителя/кабинета (обобщить store `localStorage` из W19);
  кнопка «Свободные кабинеты». *Файлы: frontend/src/**, tests.*

- [x] **W40. Фронтенд: смена/группы/метод-час/период.** Показывать учебный период
  («на период»), вторую смену, названия групп, «Метод. час» и зачёркивание
  свободных уроков (`STRIKEOUT_FREE_LSN`). *Файлы: frontend/src/**, tests.*

- [x] **W41. Паритет: e2e и документация.** Проверить новые поля на реальном
  снапшоте `school_133` (метаданные, `shift`, `groups`, `period`, календарь, `/now`,
  поиск классов); обновить спеку, `WIKI.md`, `CHANGELOG.md`, `roadmap.md`.
  *Файлы: tests/test_parity_e2e.py, WIKI.md, CHANGELOG.md, roadmap.md,
  docs/superpowers/specs/2026-09-24-public-schedule-site-design.md.*

---

## Порядок работ (соответствие спеке §12)

1. Спека и план — ✅ спека утверждена, ✅ этот план (MVP W1–W31 закрыт 2026-10-05).
2. ✅ W1–W3 — конфиг и снапшот.
3. ✅ W4–W7 — экспорт снапшота на origin.
4. ✅ W8–W11 — edge-сервер (ingest + API).
5. ✅ W12–W16 — Web Push backend. ⚠️ проводка origin `push_store` в `run_webapp` отложена (docs/EDGE.md §6 / WIKI §13.1).
6. ✅ W17 — push-proxy на edge.
7. ✅ W18–W25 — фронтенд Svelte PWA.
8. ✅ W26–W28 — деплой `deploy/edge/`.
9. ✅ W29–W31 — CI и документация.
10. ✅ W32–W41 — паритет с оригиналом Nikasoft (закрыт 2026-10-05).

## Границы работы

- Бот и Telegram-функциональность не меняются (кроме хуков снапшота и push).
- Веб-управление Telegram-подписками/настройками не входит.
- Аутентификация и личные кабинеты на сайте не входят (сайт публичный).
- Миграция `FileDB` на SQLite не входит (parked T42).

## Риски

| Риск | Уровень | Смягчение |
|---|---|---|
| Edge отдаёт устаревший снапшот | Средний | `/healthz` + возраст в UI + алерт origin при сбоях публикации (W4/W5/W11) |
| Утечка/подмена снапшота | Высокий | HMAC + timestamp ±300 с, сравнение через `compare_digest`, секреты только в `.env` (W2/W9) |
| Push-эндпоинты origin открыты для всех | Высокий | `X-Edge-Auth` на origin, проксирование только с edge (W15/W17) |
| Мёртвые push-подписки копятся | Низкий | Удаление по 404/410 + `cleanup_stale` (W13) |
| `pywebpush` тянет `requests`/сложную криптографию | Средний | Синхронный вызов только через `to_thread`, изоляция сбоя (W13) |
| Svelte/Node усложняют CI | Средний | Отдельная frontend-джоба, пин Node 20, кэш npm (W29) |
| Расхождение формата снапшота origin/edge | Средний | Поле `version`, e2e-тест контракта (W2/W30) |
| Rate-limit за Caddy схлопывается в один bucket | Высокий | Группировать по `X-Forwarded-For` доверенного прокси (W8) |
| Снапшот большого размера (мегабайты, раз в час) | Средний | Лимит `SNAPSHOT_MAX_BYTES`, gzip, лог размера (W2/W4/W9) |
| Расхождение часов Germany/Moscow > ±300 с | Средний | NTP на обоих хостах; допуск задаётся константой (W9/W28) |
| Спам-подписки через публичный subscribe | Средний | Валидация + rate-limit на origin/edge, `cleanup_stale` (W12/W15/W17) |
| Установка Node на чистом edge-хосте | Средний | install.sh ставит Node 20 LTS или принимает prebuilt dist (W26) |
| Школы с 6-дневной неделей обрезаются до Пн–Пт | Средний | `_week_dates` по `WEEKDAYNUM`; Telegram-формат не трогаем (W34) |
| Формат `CLASSGROUPS`/метод-часа `'M'` в выгрузке непроверен | Низкий | e2e на реальной выгрузке `school_133` (W33/W41) |
| Паритет расширяет публичный API/фронтенд | Низкий | отдельная фаза после MVP, тесты полей на снапшоте (W32–W41) |

## Открытые вопросы (из спеки)

- Имя `.ru`-домена и `VAPID_SUBJECT` (e-mail).
- Порт edge (`EDGE_PORT`, по умолчанию 8090).
- Оставлять ли старую Mini App-статику на origin как fallback.
- Провайдер/сервер в Москве и порядок DNS-переключения.
- Собирать `frontend/dist` на edge (`install.sh` ставит Node) или в CI артефактом.
- ✅ Какие паритетные пункты (W32–W41) обязательны для запуска — решено: все
  W32–W41 реализованы 2026-10-05.
- ✅ Точный формат `CLASSGROUPS`/поля `g` и признака метод-часа `'M'` подтверждён
  на выгрузке `school_133` (W33/W41).

---

**Связанные документы:** [спека](../specs/2026-09-24-public-schedule-site-design.md),
[DEVELOPMENT_PLAN.md](../../../DEVELOPMENT_PLAN.md), [roadmap.md](../../../roadmap.md),
[CHANGELOG.md](../../../CHANGELOG.md), [WIKI.md](../../../WIKI.md), [docs/WIDGET.md](../../WIDGET.md).
