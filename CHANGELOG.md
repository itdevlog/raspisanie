# Changelog

История исправлений Telegram-бота расписания. Хронологический порядок (новое — вверху).
«Что осталось сделать» — см. [roadmap.md](roadmap.md).

## 05.10.2026

### Публичный сайт расписания — MVP (план `2026-10-02-public-schedule-site`, W1–W31)

Завершён базовый MVP публичного (без входа) мобильного сайта расписания на отдельном
`.ru`-домене: **origin (Германия)** публикует снапшот, **edge (Москва)** отдаёт сайт из
локальной копии. Поведение Telegram-бота не менялось (кроме хуков снапшота и Web Push).
Паритет с оригиналом Nikasoft (W32–W41) закрыт в том же релизе 2026-10-05 — см.
раздел ниже и [roadmap.md](roadmap.md) §4.1.

#### Конфиг, снапшот, хранилище (W1–W3)

- **W1.** `AppConfig`/`Config` расширены edge/snapshot/push-полями (`EDGE_*`, `SNAPSHOT_*`, `VAPID_*`).
- **W2.** `services/snapshot.py` — формат v1 (`version`, `generated_at`, `schools`, `schools_config`), сериализация, HMAC-подпись (`compare_digest`), атомарная запись.
- **W3.** `services/snapshot_store.py` — потокобезопасное хранилище на edge (`apply`/`load`, `age_seconds`, `is_stale`).

#### Публикация снапшота на origin (W4–W7)

- **W4.** `services/snapshot_exporter.py` — `POST` на `EDGE_INGEST_URL` с `X-Snapshot-Signature`/`X-Snapshot-Timestamp`, gzip, ретраи, лимит `SNAPSHOT_MAX_BYTES`.
- **W5–W7.** Публикация из `BackgroundUpdater._perform_update` (через `asyncio.to_thread`), при старте и из ручного admin-refresh.

#### Edge-сервер (W8–W11)

- **W8.** `create_app` параметризован (`schools_config`, `static_dir`, `enable_telegram_routes`, health-провайдер); rate-limit группирует по реальному IP из `X-Forwarded-For` доверенного прокси.
- **W9.** `web/edge_ingest.py` — `POST /internal/snapshot`: размер → `413`, HMAC, timestamp ±300 с, `version`; запись атомарна.
- **W10.** `web/edge_server.py` — `create_edge_app` + `python -m web.edge_server` (uvicorn).
- **W11.** `GET /healthz` на edge с возрастом снапшота (`ok`/`stale` по `SNAPSHOT_MAX_AGE`).

#### Web Push (W12–W17)

- **W12.** `services/push_store.py` — коллекция `web_push_subscriptions` (валидация endpoint/keys, upsert, `remove_dead`, `cleanup_stale`).
- **W13.** `services/push_service.py` — отправка через `pywebpush` в `to_thread`, удаление мёртвых подписок по `404/410`.
- **W14.** Генерация VAPID-пары (`python -m services.push_keys`).
- **W15.** Публичное push-API origin (`/api/push/subscribe|unsubscribe`), защищено `X-Edge-Auth` + rate-limit. ⚠️ проводка `push_store` в `run_webapp` отложена — в продакшене origin пока не регистрирует `/api/push/*` (см. [docs/EDGE.md](docs/EDGE.md) §6 / [WIKI.md](WIKI.md) §13.1).
- **W16.** Push при заменах в `BackgroundUpdater._check_exchange_updates` (подписки класса, ссылка на share-страницу).
- **W17.** `web/edge_push.py` — `vapid-public-key` локально и прокси push на origin.

#### Фронтенд Svelte PWA (W18–W25)

- **W18–W25.** Каркас Svelte 5 + Vite + TS, типизированный API-клиент и stores, экраны расписания (сегодня/завтра/неделя, вкладки класс/учитель/кабинет), поиск и свободные кабинеты, share-ссылки `/s/…` + History-роутинг + SPA-fallback, PWA (push opt-in, офлайн, Service Worker), Telegram-интеграция, vitest + `npm run verify`.

#### Деплой edge и CI (W26–W30)

- **W26–W28.** `deploy/edge/` (Caddy, systemd, `install.sh`, `edge.env.example`), `./manage.sh edge`, документация DNS/NTP/переменных — [docs/EDGE.md](docs/EDGE.md).
- **W29.** CI-джоба `frontend` (Node 20, `npm ci/test/build`).
- **W30.** e2e-тест контракта origin→edge (`tests/test_snapshot_e2e.py`): HMAC, timestamp, `version`, размер, gzip.

#### Документация и статусы (W31)

- Обновлены [WIKI.md](WIKI.md) (§13.1), [README.md](README.md), [roadmap.md](roadmap.md) (§4.1), [CHANGELOG.md](CHANGELOG.md); спека и план отмечены как реализованные по MVP (W1–W31), паритет W32–W41 — запланирован.
- **Отметка деплоя**: сотрудник и дата указываются при развёртывании (placeholders в плане/спеке, а также в README и WIKI) — здесь реальное имя не фиксируется.

### Публичный сайт расписания — паритет с оригиналом Nikasoft (W32–W41)

Закрыта **фаза 9** плана (W32–W41): публичный API и Svelte-PWA приведены к
оригиналу Nikasoft по данным, уже присутствующим в выгрузке. Поведение
Telegram-бота и тексты сообщений не менялись (только публичный API/фронтенд).

- **W32.** `SchoolData` дополнен паритетными ключами (`WEEKDAYNUM`, `CLASS_SHIFT`,
  `CLASSGROUPS`, флаги `SHOW_*` и т.д.); `/api/schools` отдаёт `city` (конфиг →
  `CITY_NAME`), `updated` (`EXPORT_DATE`+`EXPORT_TIME`), `homepage_url` и
  `features` `{teachers, classrooms, rooms, homepage}` (default `True`).
- **W33.** Дневной payload: `period` (`b`/`e`/`name`), `shift` (вторая смена из
  `CLASS_SHIFT`), в item — `groups` (названия из `CLASSGROUPS`) и `is_method_hour`
  (предмет `M`). Только структурный `get_day`; Telegram-формат не тронут.
- **W34.** `/week` — Пн–Сб по `WEEKDAYNUM` (default 5, clamp 1..6) + `weekday_num`;
  шестидневные школы видят субботу как учебный день. Telegram-формат прежний.
- **W35.** `GET …/schedule/{kind}/{name}/calendar?year=&month=` — запись на каждый
  календарный день `{date, day_name, weekend, vacation, no_period, has_exchange,
  has_cancelled, lesson_count}`.
- **W36.** `GET …/schedule/{kind}/{name}/now?date=` → `{server_time, current, next}`
  (единый `select_current_and_next`, переиспользован виджетом).
- **W37.** `/search` возвращает также `classes`.
- **W38–W40.** Фронтенд: экран календаря месяца, главная с метаданными и `/now`,
  избранное, показ периода/смены/групп/метод-часа и зачёркивание свободных уроков.
- **W41.** `tests/test_parity_e2e.py` — e2e через `TestClient` на представительной
  фикстуре в форме `school_133` (метаданные, день, неделя, календарь, `/now`,
  поиск, мандат «группы по индексу == по реальному `g`»). Расширение:
  `features.strikeout_free_lsn` (`STRIKEOUT_FREE_LSN`, default `True`) — гейт
  зачёркивания свободных уроков на фронтенде; при `true` поведение прежнее.
- Документация: обновлены спека, [WIKI.md](WIKI.md) §13.1, [roadmap.md](roadmap.md)
  §4.1, план (все W1–W41 — `[x]`).

## 17.09.2026

### Полное выполнение [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) (T1–T45)

31 коммит (`e8bf2a9..44ffc37`). CI впервые зелёный (ранее 23/23 красных), **514 тестов**, покрытие **67%** (порог 60%), ruff/mypy чистые. Единственный пункт, оставленный как parked, — T42.

#### CI и тест-инфраструктура

- **T1. CI починен** — `tests/conftest.py` добавляет корень репозитория в `sys.path` (пустой файл проблему не решал: `tests/` без `__init__.py`); `pytest` в CI впервые реально запускает тесты.
- **T22–T24. Тест-окружение и CI** — pytest/pytest-asyncio актуализированы, явный пин `anyio`, добавлен `pytest-cov`; coverage с порогом и badge; матрица Python 3.11/3.12/3.13; кэш pip; `shellcheck` для `manage.sh`.
- **T25/T26. `filterwarnings` и общие фикстуры** — PTB-депрекейшен `retry_after` переведён в error, `RetryAfter(0)` → `timedelta`; общие фикстуры в `tests/conftest.py`.
- **T27. Покрытие** — тесты на `web/server.py`, `state_service`, `status_service`, `week_command`, callback-хендлеры; тестов 346→424, покрытие 61%→67%.

#### Web / widget / PWA

- **T2–T4. Widget API** — реальная схема payload (`num/start/end/items`), HMAC/подписанная ссылка (token) вместо обязательного `initData`, экранирование в `widget.html`; тест проверяет значения, а не ключи.
- **T5. PWA-иконки** — сгенерированы `icon-192/512.png`; установка Mini App работает.
- **T15. Rate limiting API** — stdlib token bucket, без новых зависимостей.
- **T16–T18, T39, T45. Frontend** — гигиена Service Worker (не кэшировать приватные пути, ревалидация), «Свободные кабинеты» без `window.prompt`, навигация по неделям, TZ сервера, cache-first + офлайн-режим с TTL-кэшем.

#### Надёжность данных и рассылок

- **T8. Атомарный `notifications_cache.json`** — tmp + `os.replace`.
- **T9. Не терять уведомления о заменах** — baseline фиксируется после попытки доставки (осознанный tradeoff: retry-окно при смене набора замен описан в отчётах).
- **T10. Тихие часы** больше не «глотают» замены; **T38** — окно тихих часов с минутной точностью.
- **T6/T11/T12. Напоминания и дайджест** — учитывают замены, переносы праздников и `current_school`.
- **T14. Единый `NotificationService`**; **T33/T34** — дедуп замен per-замена и релевантные замены подписчикам entity.
- **T37. Ретрай стартовой загрузки** при недоступном сайте.
- **T44. Алертинг админам** при повторяющихся ошибках + метрики рассылок, с подавлением повторов.

#### Производительность

- **T13. Блокирующий I/O вынесен из event loop** — записи `FileDB` и кэшей в `asyncio.to_thread`, батч-сохранение рассылок.
- **T35/T36. O(N×M) напоминаний/дайджестов** — индекс preferences одним проходом, snapshot без deep-copy; убран дублирующий `sleep` троттлинга.

#### Конфигурация и деплой

- **T19/T21. Валидация конфига** — понятная ошибка `TIMEZONE`, диапазоны `UPDATE_INTERVAL`/`WEBAPP_PORT`, doctor-предупреждение о `WEBAPP_HOST=0.0.0.0`/портах 80/443.
- **T20. Права бэкапа** — архив с `.env` создаётся с `umask 077`.
- **T28/T29. `manage.sh`** — откат зависимостей, бэкап текущих данных перед restore, `mkdir -p logs`, предупреждение о `User=root`, проверка локальных изменений в bootstrap-install.

#### UX и handlers

- **T7. Экранирование `first_name`** в `/start`.
- **T30–T32. FSM/callback UX** — TTL и сброс sibling-флагов, `callback_data` ≤ 64 байт, `query.answer()` на успешных путях.

#### Архитектура

- **T40. `JobQueue`** вместо ручных asyncio-циклов (требует `apscheduler`).
- **T41. `UserRepository` + `TypedDict`** для `school_data`.
- **T43. `AppConfig.from_env()`** и внешний JSON школ.
- **T42. Отложенная запись `FileDB` / SQLite — PARKED** (deferred-write снизил бы долговечность; мотивация снята T13; миграция рискованна для живой системы).

#### Действия при деплое

- `pip install -r requirements.txt` (для T40 нужен `apscheduler`).
- Поправить живой `.env`: `WEBAPP_HOST=127.0.0.1`, `WEBAPP_PORT=8080` + Caddy (правки на сервере сознательно не делались).

## 16.09.2026

### Надёжность данных и производительность (по [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md))

- **`FileDB` — долговечная запись** — перед атомарным `os.replace` временный файл сбрасывается на диск (`flush` + `os.fsync`), а директория — `fsync` после замены: на диске всегда целая старая или целая новая версия, даже при отключении питания. Перед заменой предыдущая целая версия сохраняется как `<db_path>.bak` (best-effort). Дескриптор temp-файла корректно закрывается и подчищается в любом случае (`database/file_db.py`).
- **`DataLoader` — условные HTTP-запросы** — добавлено кэширование `ETag`/`Last-Modified`: повторная загрузка неизменённого JS-файла отвечает `304 Not Modified` и берётся из кэша (`copy.deepcopy`, чтобы потребители не мутировали кэш), снижая нагрузку на Nikasoft и трафик. Имя файла из check-страницы также кэшируется и переиспользуется на 304 (`core/data_loader.py`).
- **Параллельная загрузка школ** — `load_all_schools_data` грузит активные школы через `ThreadPoolExecutor` (по умолчанию 4, настраивается `MAX_PARALLEL_SCHOOLS`, `1` — последовательно). Один общий `httpx.Client` переиспользует пул соединений и потокобезопасен; ошибка одной школы не влияет на остальные (`core/data_loader.py`, `config/config.py`, `.env.example`).
- **Тесты** — `tests/test_file_db.py` (+2: `.bak`-бэкап и отсутствие temp-мусора), `tests/test_data_loader.py` (+5: ETag/304, deepcopy, парсер имени, параллельная и последовательная ветки). Починлен дато-зависимый тест `test_persist_flag_controls_disk_write` — в `ExchangeDetector` добавлена точка подмены времени `_now()` (`services/exchange_detector.py`).
- **mypy** — устранены 10 ошибок в `tests/test_teacher_exchanges.py` и `tests/test_integration.py`; `mypy .` — 0 ошибок на 111 файлах. Тестов: 285, ruff чистый.

## 13.09.2026

### Мульти-инстанс: несколько ботов на одном сервере

- **Имена на инстанс** — `manage.sh` больше не хардкодит `tg-schedule-bot`: имя сервиса, PID-файла и Caddy-фрагмента выводится из имени каталога (или `--instance`/`RASPISANIE_INSTANCE`), чтобы боты в разных каталогах не перезаписывали друг друга (`tg-schedule-bot-<instance>.service`, `bot.<instance>.pid`, `/etc/caddy/conf.d/<instance>.caddy`).
- **Общий Caddy** — базовый `/etc/caddy/Caddyfile` с `import conf.d/*.caddy` создаётся один раз; каждый бот пишет только свой фрагмент. Убран общий systemd drop-in `webapp.conf`, который затирал домен/порт при втором боте. `caddy reload` вместо `restart`.
- **Порты** — `WEBAPP_PORT=80`/`443` отклоняются (эти порты слушает Caddy), занятый порт предупреждается; `WEBAPP_HOST` по умолчанию `127.0.0.1` — боты доступны только через reverse proxy.
- **Миграция** — старый единый `tg-schedule-bot.service` для того же каталога автоматически переносится в инстансный; `uninstall` удаляет свой Caddy-фрагмент.
- **Шаблон** — `deploy/Caddyfile` → `deploy/Caddyfile.site` (справка; конфиг генерируется `manage.sh caddy`).

### Модернизация: PTB 22.8, Mini App, новые фичи Telegram

- **python-telegram-bot 20.7 → 22.8** (Bot API 10.0) — async API, `AIORateLimiter` и `Defaults`; в билдере `bot.py` добавлены `.defaults(Defaults(link_preview_options=LinkPreviewOptions(is_disabled=True)))` (превью ссылок отключено глобально) и `.rate_limiter(AIORateLimiter(max_retries=3))` (требует extra `[rate-limiter]`). Ручной `RetryAfter`-цикл в `NotificationService._send_message` сохранён как вторая линия защиты.
- **`requests` → `httpx`** — `DataLoader` переведён на `httpx.Client` (загрузка JS-файлов Nikasoft, переиспользование сессии, `close()`).
- **`pytz` → `zoneinfo`** (stdlib) — `config.get_timezone()` возвращает `ZoneInfo`.
- **Mini App** — FastAPI + uvicorn (`web/`) в процессе бота: API `/api/schools`, `/api/{school}/schedule/{class|teacher|room}/{name}`, free-rooms, search, `/api/me`; фронтенд на vanilla JS + Telegram WebApp SDK; кнопка «🌐 Веб-расписание» в главном меню и MenuButton (`set_chat_menu_button`, ставится автоматически при `WEBAPP_URL`); HMAC-валидация `initData`; `/healthz` для проверки живости.
- **Структурный слой сервисов** — `get_day`/`get_week` в `schedule_service`/`teacher_service`/`room_service` возвращают JSON-payload (уроки, замены, отмены, каникулы/выходные) для API; Markdown-вывод бота не изменился.
- **CopyTextButton** — кнопка «📋 Скопировать» к расписанию на день (≤256 симв.).
- **Реакции** — 👀 при обработке текстового запроса, 👍 после ответа.
- **Inline-режим** — `@bot 9а` в любом чате (включить через @BotFather `/setinline`).
- Тесты: 268 (юнит + интеграционные), ruff чистый, mypy без новых ошибок.

## 12.09.2026 (вечер)

### Функционал с сайта Nikasoft: замены учителей, переносы праздников, свободные кабинеты

- **Замены в расписании преподавателей (`TEACH_EXCHANGE`)** — расписание учителя теперь учитывает его собственные замены: запись `TEACH_EXCHANGE[учитель][дата][урок]` перекрывает слот (новый предмет, классы, кабинет), `"s": "F"` помечает слот отменённым; замены корректно сосуществуют с классными `CLASS_EXCHANGE`. В строках расписания учителя появился класс урока: `6. 13:00-13:40 • Литературное чтение (2д)` (`services/teacher_service.py`).
- **Отображение класса и кабинета в расписании учителя** — `_format_lesson_line` показывает `class_name` урока в скобках; кабинет, не найденный в `ROOMS` (в заменах приходят имена, не id), показывается как есть вместо «?» (`services/base_schedule_service.py`).
- **Переносы праздников (`HOLIDAY_TRANSFER`)** — как на сайте: `vacation` — «Каникулы/праздник — занятий нет»; `transfer` — день работает по расписанию другого дня недели (`daynum`), с поддержкой префикса учебной недели (`weeknum`, ключи `{week}{день}{урок}`) и переопределения периода (`period`). Проверка выходных идёт по реальному дню: перенесённый на субботу день показывает занятия. Действует для классов, учителей и кабинетов (`services/base_schedule_service.py::_get_effective_day`, `schedule_service.py`, `teacher_service.py`, `room_service.py`).
- **Поиск свободных кабинетов** — аналог «Найти свободный кабинет» на сайте: кнопка «🔍 Свободный кабинет» в меню кабинетов показывает список свободных кабинетов на текущий (идущий) или следующий урок с учётом всех замен и отмен; сортировка по номеру (`services/room_service.py::get_free_rooms`, `handlers/rooms/room_schedule.py::free_rooms_handler`, callback `room_free_now`).
- Тесты: `tests/test_teacher_exchanges.py` (+8), `tests/test_holiday_transfer.py` (+7), `tests/test_free_rooms.py` (+8), `test_integration.py` (+2). Итого 227. ruff и mypy чистые; смоук на живых данных школы №133 (учитель с 4 заменами, 13 свободных кабинетов из 65) сверен с ручным пересчётом.

## 12.09.2026

### Утренний дайджест и навигация по неделям

- **Утренний дайджест (`services/digest_service.py`)** — расписание на день приходит за 60 мин до **первого урока** (а не в фиксированный час): привязка к уроку автоматически покрывает обе смены (вторая получает дайджест в обед) и не шлётся в выходные/праздники/каникулы (нет уроков). Окно догона 15 мин после триггера, дедуп-ключ `digest:{user}:{school}:{class}:{ГГГГММДД}` (один дайджест в день). Текст — расписание класса с заменами (через `ScheduleService`).
- **Отправка в существующем минутном цикле** — `BackgroundUpdater._reminder_loop` вызывает `_send_digests` рядом с `_send_reminders` (без третьего asyncio-цикла). Отдельный кэш `data/sent_digests.json` (атомарная запись, чистка старше 48 ч, переживает рестарт); тихие часы и троттлинг `_send_message` уважаются.
- **Тумблер `daily_digest`** — `UserPreferencesService` (`enable/disable/toggle_daily_digest`, дефолт выкл) и кнопка «📋 Дайджест дня (за час до 1-го урока)» в `/settings`; callback `toggle_daily_digest_{on|off}` зарегистрирован в роутере.
- **Навигация по неделям** — в недельном расписании класса кнопки «◀️ Прошлая / 📅 Текущая / Следующая ▶️» (лимит ±2 недели), callback `class_week_{класс}_o{N}`; кнопка «Обновить» сохраняет смещение. Если данных на будущую неделю ещё нет — понятное сообщение «расписание обычно публикуется ближе к концу текущей недели». Старый callback `class_week_{класс}` (offset 0) продолжает работать.
- Тесты: `tests/test_digest.py` (+11) и `tests/test_week_navigation.py` (+7), дополнен `test_callback_router.py`. Итого 202.

### Информативный формат уведомлений о заменах (вариант «до → после»)

- **Реальный исходный урок вместо заглушки «Урок N»** — `ExchangeDetector._get_original_lesson` находит исходный предмет/преподавателя/кабинет в базовом расписании (`CLASS_SCHEDULE[period][class_id][день+урок]`, период по дате); `_get_original_subject` делегирует ему. Если базового урока нет (нет периода/класса/записи) — деградация к прежней заглушке.
- **Время урока в уведомлении** — `lesson_time` (`LESSON_TIMES`, напр. `13:00-13:45`) добавлено в formatted-словарь замены и рендер.
- **Формат строки «до → после»** — `_format_exchange_notification` теперь рендерит `🔄 6. 13:00-13:45 • Математика (Ищенко К.А., каб. 301) → Биология (Усольцева А.Д., каб. 4022)`; отмена — `❌ N. время • Предмет (Фамилия И.О., каб.) — ОТМЕНЕНО`; снятие — `↩️ N. … — замена снята` (тоже с исходными деталями и временем, если они есть в кэше).
- **`short_name` (Фамилия И.О.)** — новый хелпер `services/text_utils.py`; сокращает полные ФИО (в т.ч. несколько преподавателей через запятую) и маскирует обрезанные на стороне Nikasoft ФИО («Александрова Валентина Александровн…» → «Александрова В.А.»).
- **Фикс: кабинеты в кавычках** — `_convert_codes_to_names` больше не оборачивает неизвестное значение в `'кавычки'`: кабинеты в `CLASS_EXCHANGE` приходят уже именами (не id), поэтому значение без словаря показывается как есть. Мёртвый параметр `type_name` удалён.
- **Экранирование компонентов, а не всей строки** — `_format_before_after` экранирует предмет/ФИО/кабинет по отдельности (`escape_markdown`), структурные скобки и запятые остаются литеральными.
- Обратная совместимость: старый кэш замен (без `original_teacher`/`original_room`/`lesson_time`) рендерится без этих деталей — деградация, не падение.
- Тесты: `test_exchange_detector.py` (+5: поиск исходного урока, formatted с деталями), `test_exchange_removed.py` (+4: рендер «до → после», отмена, снятие, деградация без времени), `test_text_utils.py` (+5: `short_name`). Итого 180.

## 11.09.2026

### mypy-чистота репозитория + CI

- `mypy .` проходит без ошибок на всём репозитории (93 файла) — неявные `Optional`-дефолты, `union-attr`/`arg-type`/`index`/`var-annotated` устранены типами и сужениями, поведение не менялось.
- Хелперы сужения PTB в `handlers/common/typing.py` (`require_user`, `require_message`, `require_query`, `require_user_data`) — заменяют `update.effective_user`/`effective_message`/`callback_query`/`context.user_data` без разбросанных `assert`.
- В CI добавлен шаг `mypy .` после ruff (`.github/workflows/ci.yml`).
- Счётчик тестов в документации синхронизирован: 165.

### Фаза 1 — критические исправления (P0)

- **Кэш расписания привязан к школе** — ключи кэша теперь включают `school_id`, поэтому расписание одной школы больше не отдаётся в другой (`services/schedule_service.py`).
- **Кэш замен привязан к дате** — детектор хранит данные по датам и пишет файл атомарно (temp + `os.replace`), перезапуск больше не «забывает» и не путает замены (`services/exchange_detector.py`).
- **Блокирующий детект замен вынесен из event loop** — синхронная проверка выполняется в `asyncio.to_thread`, кэш замен сохраняется на диск один раз за цикл (`core/background_updater.py`).
- **`KeyError` при длинном запросе поиска** — защита от слишком длинного ввода больше не падает на отсутствующем флаге: `del` заменён на `pop(..., None)` для обоих `waiting_for_*` (`handlers/common/class_schedule.py`).
- **`update.message` в callback-обработчиках** — ветка с отсутствующим `state_service` в `search_results` теперь идёт через `_edit_or_reply` вместо `update.message.reply_text`, чтобы обработка не падала на callback-обновлениях (`handlers/common/entity_menu.py`).
- **Пагинация списка классов сохраняет тип расписания** — формат кнопок `all_classes_page_{type}_{page}`, переходы больше не сбрасывают «Сегодня/Завтра/Неделю» (`handlers/common/callback_handler.py`).
- **Валидация несуществующей школы + сброс флагов поиска** — выбор несуществующей школы отклоняется, «залипшие» флаги `waiting_for_*` сбрасываются при входе в меню (`handlers/schools/school_selection.py`, `handlers/common/messaging.py`).
- **Общий текст ошибки** — глобальный обработчик использует `GENERIC_ERROR_MSG` вместо дублирующего литерала (`bot.py`, `handlers/common/messaging.py`).

### Фаза 2 — надёжность и консистентность (P1)

- **`FileDB` сообщает об ошибках записи** — `_save_data()` и операции `Collection` (`insert_one`/`update_one`/`delete_one`) теперь возвращают `bool`; ошибка логируется с `exc_info=True` и не проглатывается молча. `_save_data` работает и с «голым» именем файла без директории (`os.path.dirname(...) or '.'`) (`database/file_db.py`).
- **Общий `escape_markdown`** — новый хелпер `services/text_utils.py` (экранирует `_ * [ ] ( ) \``); `BaseScheduleService._escape_markdown` делегирует ему, а динамический текст прогоняется через него в уведомлениях (`notification_service`), поиске (`entity_menu`), информации о школе (`school_info`) и главном меню (`menu_builder`). Метки inline-кнопок не экранируются (`ff84ff6`).
- **Пакетные настройки уведомлений** — `UserService.get_notification_settings_batch(school_id)` строит `{user_id: enabled}` одним проходом; `NotificationService` строит `_settings_for_school` вместе с индексом `(school_id, класс) → [user_id]` и фильтрует получателей через `get_users_for_exchange`, убирая линейный `find_one` на каждого получателя (`services/user_service.py`, `services/notification_service.py`).
- **Частичная загрузка не теряет школы** — `BackgroundUpdater._merge_schools_data` накладывает свежие данные поверх last-known-good; `_perform_update` сериализован `asyncio.Lock` (повторный запуск сообщает о пропуске) и вызывает единый хук `_on_data_replaced()` (сброс кэша расписания + индекса уведомлений) вместо дублирующих блоков (`core/background_updater.py`).
- **Ручной refresh админа** — `_refresh_all_schools`/`_refresh_school` используют `_invalidate_data()` (делегирует в `_on_data_replaced`) и защищены `_refresh_lock` от наложений; «Принудительное обновление» честно сообщает, если обновление уже идёт (`handlers/callbacks/admin_callbacks.py`).
- **`RetryAfter` и троттлинг** — `NotificationService._send_message` пережидает Telegram `RetryAfter` (429) и повторяет; broadcast троттлится паузой `asyncio.sleep(0.05)` между отправками (`services/notification_service.py`).
- **`DataLoader`: один слой ретраев + сессия на вызов** — `load_school_data` передаёт `max_retries=1` в `get_current_filename`/`download_schedule_data` (ретрай остаётся только на внешнем уровне); `load_all_schools_data` использует локальную `requests.Session` и закрывает её в `finally` (`core/data_loader.py`).
- **mypy-аннотация** — `Optional[str]` для `_index_loaded_for_school` вместо неявного `None` (`services/notification_service.py`).

> Сознательно отложено: параллельная загрузка школ через `Semaphore` не реализована — `load_all_schools_data` уже уходит из event loop через `asyncio.to_thread`, а усложнение ради часовой задачи с двумя школами неоправданно. Нарезка недельного сообщения уже покрыта `handlers/common/messaging.py`.

### Фаза 3 — рефакторинг и качество (P2)

- **Единая админ-панель** — `handlers/admin/admin_panel.py` больше не дублирует построители панели: команды `/admin` и `/stats` делегируют в `AdminCallbackHandler` (`show_panel` / `_show_statistics`). Удалены дубли `_show_admin_panel`, `_build_admin_panel_text`, `_build_admin_keyboard`, `_get_schools_status`, `_update_callback_message`. `/stats` теперь показывает статистику (всего пользователей с классами + разбивка по школам), а `/admin` — ту же клавиатуру, что и callback'и (`0a21706`).
- **`/cancel` и единый сброс состояния** — добавлена команда `/cancel`; общий `reset_user_flow(context)` сбрасывает `waiting_for_*`, `class_digit` и поисковые запросы. Переиспользован в `handle_change_class` (`c68467d`).
- **Удалён мёртвый код** — дублирующие обработчики `menu_teacher`/`menu_room` удалены из `teacher_callbacks.py`/`room_callbacks.py` (маршруты остаются живыми в `navigation_callbacks.py`), недостижимая ветка цифры класса (`parts[1] == "digit"`, роутер перехватывает раньше), неиспользуемые методы `ExchangeDetector` (`get_current_exchanges_for_class`, `_get_teacher_name`) (`3c53378`).
- **Ошибки не утекают пользователю** — `str(e)` в ответах `entity_menu.py` заменён на `log_user_error` с общим `GENERIC_ERROR_MSG`; добавлен поведенческий тест на отсутствие текста исключения (`3c53378`, `51f5a7a`).
- **Общие хелперы времени и класса** — `format_time_ago` и `find_class_id` вынесены в `services/base_schedule_service.py`; `ScheduleService`, `ExchangeService`, `StatusService` делегируют им вместо дублей (`3c7c478`).
- **Разделение хранилищ настроек уведомлений** — модульный docstring `services/user_preferences.py` фиксирует: exchange (per-school) пишется только через `UserService`, update (админ) — только через `UserPreferencesService`; удалены мёртвые `enable/disable_exchange_notifications`. `BackgroundUpdater._get_admin_notification_settings` учитывает **всех** админов (`any(...)`, настройки второго больше не игнорируются) (`2bdded3`).

> Сознательно отложено в Фазе 3 (записано в [roadmap.md](roadmap.md)): слой данных `UserRepository`/`TypedDict` и инъекция часов (clock) не реализованы — это крупные сквозные рефакторинги с низкой пользовательской ценностью.

### Фаза 4 — новый функционал

- **Уведомления о снятии замен** — детектор распознаёт снятые замены (урок, который был в замене, исчез) (`Fix: detect removal when a class's only exchange disappears`), а уведомление по такой позиции формируется как `↩️ N. <предмет> — *замена снята*` вместо нового варианта (`services/notification_service.py`, `services/exchange_detector.py`).
- **Подписки на преподавателей и кабинеты** — новый `SubscriptionService` (коллекция `subscriptions`, документ на пару `user_id`+`school_id` со списком `items`): `subscribe`/`unsubscribe`/`is_subscribed`/`get_subscriptions`/`get_subscribers`. В расписании преподавателя/кабинета появляется кнопка «🔔 Подписаться»/«🔕 Отписаться»; `NotificationService.notify_subscribers` рассылает подписчикам уведомления о заменах; активные подписки перечислены в `/settings` с кнопкой отписки (`services/subscription_service.py`, `handlers/common/entity_menu.py`, `handlers/common/settings.py`).
- **Напоминания об уроках** — новый чистый `ReminderService` вычисляет уроки, начинающиеся в ближайшее окно, и тексты «через N мин начнётся урок …»; отправкой занимается отдельный цикл `BackgroundUpdater._reminder_loop` (`asyncio.create_task`, без новых зависимостей — `JobQueue`/APScheduler не подключались). Дедуп — стабильный ключ `user:school:class:дата:номер_урока` на 24 ч. Тумблер `⏰ Напоминания об уроках` в `/settings` (`services/reminder_service.py`, `core/background_updater.py`, `handlers/common/settings.py`).
- **Тихие часы и анти-флуд** — `NotificationService._is_quiet_hours` учитывает интервал через полночь (по умолчанию 22–7) и не шлёт уведомления в это окно; `_send_message` не дропает сообщения, а выжидает остаток интервала анти-флуда (сверху ограничен), продолжая пережидать `RetryAfter`. Тумблер `🌙 Тихие часы` в `/settings` (`services/notification_service.py`, `services/user_preferences.py`).
- **Смещение недели и helper «текущий/следующий урок»** — `_get_week_schedule(..., week_offset)` и `ScheduleService.get_class_schedule_week(..., week_offset)` умеют строить соседние недели, а `BaseScheduleService.get_next_lesson` возвращает текущий или ближайший урок по `LESSON_TIMES`. Пользовательских команд/кнопок под это не добавлено — только внутренние хелперы (`services/base_schedule_service.py`, `services/schedule_service.py`).

### PR «Fix critical bugs» `80434ed`

- `AttributeError` на `self.moscow_tz` в `log_update_activity` — `updatelog.txt` теперь заполняется (`core/background_updater.py`).
- Хак `context = ContextTypes.DEFAULT_TYPE` (мутация класса PTB) → `SimpleNamespace` (`core/background_updater.py`).
- Дублирующийся метод `stop()` (`core/background_updater.py`).
- Краш `show_class_selection` при вводе несуществующего класса текстом (`query=None`) (`handlers/common/callback_handler.py`).
- Блокирующий sync-IO в админ-callback'ах → `asyncio.to_thread` (`handlers/callbacks/admin_callbacks.py`, `handlers/admin/admin_panel.py`).
- `FileDB.delete_one` удалял ВСЕ подходящие документы, а не один (`database/file_db.py`).
- Дублирующийся `FileDB.get_collection`; `except (…, Exception)` → `(json.JSONDecodeError, OSError)`; `print` → `logger` (`database/file_db.py`).
- Команды `/week` и `/school` не были зарегистрированы (`bot.py`).
- Понятная ошибка при незаданном `TELEGRAM_TOKEN` (`bot.py`).
- `ExchangeDetector.clear_school_cache` не сохранял файл (возвращалось после рестарта) (`services/exchange_detector.py`).
- `Message is not modified` → тихо игнорируется в `main_menu`, `class_callbacks`, `callback_handler` (`handlers/common/main_menu.py`, `handlers/callbacks/class_callbacks.py`).
- Заголовок с датой для «Сегодня/Завтра» (классы/преподаватели/кабинеты) (`services/schedule_service.py`, `services/teacher_service.py`, `services/room_service.py`).
- `CacheService.delete/delete_prefix`; `state_service.clear_user_state` реально удаляет ключи (`services/cache_service.py`).
- Недостающие `__init__.py` во всех пакетах (11 шт.).

### Исправлено ранее (до аудита; см. WIKI §8, §16)

- Глубокие копии замен, строковые ключи уроков, `sent_count > 0`, потокобезопасный `FileDB`, `bot_data['background_updater']`, `asyncio` в фоновом обновлении.

### p.4 — битый `database.json` `5b0c82f`

- При повреждённом файле БД сохраняется копия `database.json.corrupt` (с ротацией `.corrupt.N`) до перезаписи; запись атомарна через temp-файл + `os.replace()` (`database/file_db.py`).

### Пустой `SCHOOL_NAME` (школа 181) + косметика `5b0c82f`

- Центральный helper `config/schools.py::get_display_name(school_id, school_data)` применён во всех 6 местах (`bot.py`, `status.py`, `school_info.py`, `callback_handler.py`, `background_updater.py`, `notification_service.py`).
- Выровнен отступ в стартовом `print` списка школ (`bot.py`, `load_schools_data`).

### p.9 — нарезка сообщений по 4096 `5b0c82f`

- Новый `handlers/common/messaging.py`: `split_long_message` + `edit_long_message`/`reply_long_message`. Применён в `class_schedule`, `week_command`, `class_callbacks`, `teacher_menu`, `room_schedule`. Нарезка по границам строк, чтобы не рвать разметку Markdown.

### p.10 — поиск учителей/кабинетов (чужие индексы + 64-байт callback) `5b0c82f`

- Результаты поиска хранятся под отдельными ключами `search_teachers`/`search_rooms`; источник списка закодирован в callback (`sidx_` = поиск vs `idx_` = полный) в `teacher_callbacks`/`room_callbacks` и дневных кнопках; запрос поиска переехал в `user_data` (`teacher_search_query`/`room_search_query`); пагинация — `teacher_search_page_N`/`room_search_page_N` (все ≤64 байта).

### Двойной `query.answer()` + кнопки-заглушки `0f87ec0`

- Роутер больше не отвечает на query заранее — ответ берёт на себя обработчик (`query.answer(...)` для тостов, `edit_message_text` для успешных действий). PTB-objects заморожены, поэтому отследить «уже ответил» из роутера нельзя; вместо этого просто убран авто-answer.
- `teacher_pages_info`, `room_pages_info` (и `*_search_pages_info`) отвечают тостом «Используйте кнопки навигации по страницам».

### Залипшие флаги поиска `c5696d7`

- Хелпер `messaging::clear_search_flags(context)` сбрасывает все `waiting_for_*` флаги; вызывается в точках входа — `main_menu_handler`, `teacher_menu_handler`, `room_menu_handler`, `show_all_teachers`, `show_all_rooms`.

### Дефолты уведомлений (UI ↔ поведение) `91c4008`

- `background_updater._get_admin_notification_settings` возвращает `update_notifications: False` для админов без сохранённых настроек — раньше админ-уведомления слались, хотя UI показывал «Выкл».

### `print` → `logger` (~36 вызовов) `5359adc`

- Все `print()` заменены на `logger` в `data_loader`, `background_updater`, `bot`, `status_service`, `room_schedule`, `school_selection`. Диагностика не теряется при буферизации stdout под systemd.

### `Message is not modified` + утечка `class_digit` `fd48b82`

- Новый `messaging::safe_edit_message` (глотает BadRequest «not modified»); применён в `school_info` и через `edit_long_message` (`class_callbacks`, `teacher_menu`, `room_schedule`).
- `class_digit` сбрасывается в `handle_school_selection` и `main_menu_handler`.

### Конфиг-настройки игнорировались `615a196`

- `UPDATE_INTERVAL` → `BackgroundUpdater.update_interval`; `MAX_RETRIES` → дефолты `DataLoader`; пути `exchange_cache.json`, `notifications_cache.json`, `updatelog.txt` выводятся из `DB_PATH`, а не из cwd.

### Логирование: ротация + консоль + тишина httpx `5e4d773`

- `RotatingFileHandler` (5 МБ x 3) + `StreamHandler` вместо `basicConfig(filename=...)`.
- httpx приглушён до WARNING — в debug не логируются URL-ы запросов с токеном бота.

### Дубли `admin_panel.py` ↔ `admin_callbacks.py` `d24662e`

- Из `admin_panel.py` удалён мёртвый callback-код (`admin_callback_handler`, `_force_update`, `_refresh_all_schools`, `_refresh_school`, `_show_users_with_classes` — живут в `AdminCallbackHandler`). Файл сокращён 306→130 строк, осталось только `/admin`/`/stats`. Убран импорт `admin_callback_handler` в `bot.py`.

### Пагинация «Все классы» `be8f1bf`

- `handle_show_all_classes` разбит на страницы (60 кнопок/стр.), список кэшируется в `state_service`, навигация через `all_classes_page_N`, общий хелпер `messaging::paginate`.

### p.11 — матчинг цифры класса `30410c6`

- Новый `_class_matches_digit` сравнивает по сегментам: цифра матчится только если за ней буква (не десяток) — «1» больше не матчит «11а». Применён в `show_class_selection` и `_get_class_letters_for_digit`.

### Валидация `.env` `6869d03`

- `_parse_int`/`_parse_admin_ids` дают понятный `ValueError` с именем переменной и примером вместо молчаливого краха на импорте.

### Детектор замен: сегодня + завтра, корректная дата `4ab3f8f`

- `_check_exchange_updates` и `force_check_exchanges` проверяют замены на сегодня **и завтра** (было «только сегодня»).
- Дата замены (`date`) пробрасывается в `_format_exchange_for_notification` и `timestamp` — заголовок уведомления показывает верный день.

### Инвалидация кэша расписания `0a12722`

- `_perform_update` вызывает `cache_service.clear()` после обновления данных — пользователи не видят старое расписание до истечения TTL.

### Юнит-тесты + безпотерьная нарезка + чистка requirements `8782ee5`

- Добавлен pytest (`pytest.ini`), тесты в `tests/`: безпотерьность `split_long_message` и границы, `paginate`, `get_display_name` (пустой `SCHOOL_NAME`), матчинг цифры класса (p.11).
- `split_long_message` переписан без потерь (`''.join(chunks) == text`).
- `requirements.txt` очищен от закомментированных мёртвых зависимостей.
- `.gitignore` покрывает `.venv-test/`, `data/`, `logs/`, `cache/`.

### P1: неполное экранирование Markdown + замены для учителей/кабинетов

- `BaseScheduleService._escape_markdown` — единый хелпер экранирования legacy Markdown (`_ * [ ] ( ) \``); применён во всех 6 местах (`base_schedule_service.py`) — раньше `[ ] ( )` не экранировались → сообщения с такими символами не уходили.
- `teacher_service`/`room_service`: для `apply_exchanges_to_schedule` и хранения имени используется ЧИСТОЕ `class_name` — раньше экранированное имя сравнивалось с чистыми именами в `_find_class_id`, из-за чего замены для расписаний учителей/кабинетов не находились.

### P1: обрезка списка пользователей в админке по границе строки

- `admin_callbacks.py::_show_users_with_classes` — усечение `text[:4000]` заменено на рез по границе строки (`rfind('\n')`), чтобы не рвать разметку `*...*`/`` `...` `` → не падает `Can't parse entities`.

### P2: вынос общего кода teacher_menu/room_schedule в EntityMenuHandler

- `handlers/common/entity_menu.py` — новый параметризованный `EntityMenuHandler` + `EntityConfig`: меню, поиск, пагинация, выбор, дневные кнопки «Сегодня/Завтра/Неделя», resolve источника (поиск vs полный список).
- `teacher_menu.py`/`room_schedule.py` — сведены к тонким обёрткам (~60 строк каждая) с прежней публичной API (callbacks-обработчики не менялись). Объём дублей: 913 → 500 строк суммарно.
- Юнит-тесты `tests/test_entity_menu.py` (resolve source).

### P1: UserSchool deleted + user-state TTL fix

- Удалён мёртвый `database/models/user_school.py` (модель нигде не использовалась; логика школы/класса — в `UserService`).
- `state_service` переведён на отдельный долгий кэш (24 ч) вместо общего `CacheService(ttl=600)` — индексные кнопки учителей/кабинетов/классов больше не «протухают» через 10 минут и не стираются при инвалидации кэша расписания.

### P2: единые построители главного меню и справки

- `handlers/common/menu_builder.py` — общие `build_main_menu_keyboard`/`build_main_menu_text`/`resolve_school_name`/`HELP_TEXT`/`build_help_keyboard`.
- `start.py` и `main_menu.py` используют общий построитель меню (дубль убран).
- `start.py::help_handler` и `callback_handler.py::handle_help` используют единый `HELP_TEXT` (тексты больше не расходятся).
- Юнит-тесты `tests/test_menu_builder.py`.

### P2: is_admin, get_school_by_id, время в конфиге

- `Config.is_admin(config, user_id)` — единая проверка админа; подключена в `admin_panel`, `admin_callbacks`, `settings`, `bot` (было 4 разных способа).
- `config/schools.py::get_school_by_id()` — единый поиск школы по id (было 6 ручных мест, сейчас подключён в `EntityMenuHandler`).
- `config.get_timezone()` + конфиг `TIMEZONE` (`.env`, по умолчанию `Asia/Yekaterinburg`) — вместо хардкода `'Asia/Yekaterinburg'` + ошибочного имени `moscow_tz` в 6 сервисах.

### P2: не показываем str(e) пользователю

- `messaging::log_user_error` — логирует реальное исключение (exc_info) и возвращает общее сообщение. Применён в `class_callbacks`, `week_command`, `callback_handler`, `admin_callbacks`; `str(e)` больше не утекает пользователю.

### P2: чистка мёртвого кода

- Удалён мёртвый `callback_handler.py::handle_school_info` (дублировал `school_info_handler`).
- Удалён никогда не устанавливавшийся флаг `waiting_for_teacher` (class_schedule.py, `messaging::clear_search_flags`).
- Удалены заглушка `_get_user_service` и большой закомментированный блок в `notification_service.py`.
- Удалено неиспользуемое поле `['order']` из конфига школ.
- Исправлено случайное дублирование всего `callback_handler.py` (434→780→434), внесённое скриптом в 422e91f.

### P2: ADMIN_LOG_FILE подключён

- `bot.py::setup_logging` создаёт отдельный ротируемый файловый логгер `admin_panel` (действия администраторов) в `logs/admin.log` — раньше `ADMIN_LOG_FILE` был объявлен, но не использовался.

### P2: O(N) индекс получателей замен (вместо O(N²))

- `NotificationService` строит индекс `(school_id, класс) → [user_id]` одним проходом по пользователям и кэширует на школу; читает `school_classes` из документа без per-user `find_one`. Сброс после обновления данных в `_perform_update`. Юнит-тесты `tests/test_notification_index.py`.

### P2: кэш уведомлений — TTL 24 ч вместо случайного среза

- `sent_notifications` хранит `{notification_key: timestamp}`, `_cleanup_old_notifications` удаляет записи старше 24 ч (было «последние 100» через `list(set)[-100:]` без гарантии порядка). Старый set-формат читается для совместимости. Юнит-тесты TTL и mark/is.

### P2: CacheService — потокобезопасность, лимит размера, честная статистика

- `CacheService` обёрнут в `threading.RLock`; добавлен параметр `max_entries` с вытеснением самых старых; `get_stats` больше не сериализует весь кэш в строки (O(n), оценочная память). Юнит-тесты (TTL/эviction/prefix/thread-safety).

### P2: data_loader — не ретраим некорректный JSON, закрываем Session

- `JSONDecodeError` при парсинге `var NIKA=` больше не уходит в ретрай (выход сразу) — раньше ловился `except Exception` и бесполезно повторялся.
- Добавлен `DataLoader.close()` для закрытия HTTP-сессии (пул соединений).

### P2: единая иконка статуса школы (admin + /status)

- `status_service::status_icon(status)` — единый источник иконки из `status['status']`; админ-панель больше не подменяет всё на ⚠️ и теперь показывает 🔴 «Устарело» для данных старше 24 ч (как `/status`).

### P2: кнопка «Обновить» в teacher/room + доп. юнит-тесты

- В `EntityMenuHandler::select` добавлена кнопка «🔄 Обновить» (перерисовка текущего расписания).
- Новые юнит-тесты: `test_exchange_service.py` (точный матчинг класса, нет мутации входных данных), `test_file_db.py` (битый файл → `.corrupt`, upsert, delete_one, round-trip).

### P2: убран лишний `ExchangeService` в детекторе замен

- `_get_current_exchanges`/`_get_class_exchanges` больше не создают/не принимают неиспользуемый `ExchangeService` (данные извлекаются напрямую из `school_data`) — меньше мусорных объектов на каждый тик.

### P2: кнопка «Отмена» поиска + ограничение длины запроса

- `EntityMenuHandler::search_input` — кнопка «❌ Отмена» (`{p}_search_cancel` → снимает флаг и возвращает в меню), маршрутизация в teacher/room callbacks.
- `class_schedule.py` — запрос поиска ограничен 80 символами (было без лимита).

### P2: «Список устарел» перерисовывает актуальный список

- teacher/room callbacks при устаревшем списке (поиск или полный) вместо тоста перерисовывают актуальный список через `handle_*_search_results`/`show_all_*`.

### P2: декоратор @requires_school

- Новый `handlers/common/requires_school.py` — убирает дублирующиеся проверки сервисов/школы; подкладывает в `context` ключи `user_service`, `current_school_id`, `school_data`. Применён к `school_info_handler` и `week_command_handler`; юнит-тесты в `tests/test_requires_school.py`.

### Тесты: exchange round-trip и callback роутинг

- `tests/test_exchange_detector.py` — round-trip JSON строковых ключей урока (п.5), новые замены.
- `tests/test_callback_router.py` — параметризованные случаи `_get_handler_key` (16 префиксов).

### P2: индикатор «печатает...» в долгих админ-операциях

- `admin_callbacks._typing_until` — периодически шлёт `ChatAction.TYPING`, пока выполняется длинная задача; применён в «Обновить все школы» и «Принудительное обновление».

### P2: счётчик свежести школ в админке

- «Обновить все школы» теперь считает «обновлёнными» только школы со свежими данными (статус «Актуально»), а не все загруженные — у школы с устаревшим экспортом (как №133) не пишется ложное «2/2».

### Проверено: неиспользуемых веток navigation_callbacks нет

- После рефакторинга все ветки `NavigationCallbackHandler` достижимы реальными callback_data.

### Инструменты: Ruff

- Добавлены `ruff.toml`, `mypy.ini`. Ruff-проверка кодовой базы: 841 автоисправление (импорты, стиль), вручную удалены 5 неиспользуемых переменных. `ruff check .` — чисто.
- mypy настроен (mypy.ini), но строгий проход по всему коду вне скоупа текущей чистки (211 Optional-замечаний на живом коде).

### Интеграционные mock-тесты + CI

- `tests/test_integration.py` — 3 mock-теста через pytest-asyncio (навигация, рендер меню сущности).
- `pytest.ini` — `asyncio_mode = auto`.
- `requirements-dev.txt` — pytest, pytest-asyncio, ruff, mypy.
- `.github/workflows/ci.yml` — CI: ruff + pytest на push/PR.
