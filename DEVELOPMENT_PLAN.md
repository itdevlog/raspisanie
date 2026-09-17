# План развития и улучшения проекта raspisanie

**Дата анализа:** 17 сентября 2026
**Статус проекта:** Production-зрелая база; найден ряд критических багов, не видимых в локальных прогонах

---

## 📊 Резюме анализа (17.09.2026)

### Проверено фактически

| Проверка | Результат |
|---|---|
| `ruff check .` | ✅ чисто |
| `mypy .` | ✅ 0 ошибок (112 файлов) |
| `python -m pytest` (локально) | ✅ 288 passed |
| `pytest -q` (как в CI) | ❌ INTERNALERROR: `ModuleNotFoundError: No module named 'handlers'` (exit 3) |
| CI на GitHub (все 23 запуска) | ❌ **все красные**, шаг pytest падает |
| `web/static/*.png` (иконки PWA) | ❌ отсутствуют, хотя указаны в manifest.json |
| Схема данных widget API | ❌ читает ключи, которых нет в payload |

### Контекст: что уже сделано (16.09.2026)

- ✅ `FileDB`: `flush` + `fsync` файла и директории, `.bak`, корректная очистка temp
- ✅ `DataLoader`: `ETag`/`If-Modified-Since`, `304` → кэш; кэш имени файла
- ✅ Параллельная загрузка школ: `ThreadPoolExecutor`, `MAX_PARALLEL_SCHOOLS` (default 4)
- ✅ Исправлены 10 mypy-ошибок в тестах; починен дато-зависимый тест кэша замен
- ✅ 288 тестов проходят локально, ruff/mypy чистые

### Главная проблема проекта

**CI красный во всех 23 запусках.** `.github/workflows/ci.yml:27` запускает `pytest -q` (консольный скрипт): в этом режиме cwd не попадает в `sys.path`, а в проекте нет `conftest.py`, `pyproject.toml` или `PYTHONPATH`. Локально всё работает только через `python -m pytest` (внутренние прогоны документированы с `PYTHONPATH=.` — `docs/superpowers/plans/2026-09-13-modernization-webapp.md:16,19`). В CI тесты физически не запускались ни разу: любой сломанный код проходил «проверки».

---

## 🐛 Найденные ошибки (17.09.2026)

### 🔴 Критические

#### 1. CI красный — тесты в CI не работают
**Файл:** `.github/workflows/ci.yml:27` (воспроизведено локально: `pytest -q` → exit 3)
**Причина:** нет `conftest.py`/`pyproject.toml`; консольный `pytest` не добавляет cwd в `sys.path`.
**Решение:** добавить пустой `tests/conftest.py` (или `conftest.py` в корне) — однострочный фикс; проверить CI зелёным.

#### 2. Widget API нерабочий: несовместимая схема данных
**Файлы:** `web/api.py:154-194` ↔ `services/base_schedule_service.py:167-174`
`/api/widget/{user_id}` читает `lesson.get('time'/'subject'/'room'/'was_subject')`, но `_lessons_payload` возвращает `{num, start, end, items[{subject, teacher, room, class_name}], has_exchange, is_cancelled}`. Следствия:
- `lesson_time` всегда `''` → `next_lesson` **всегда null** (api.py:154-170);
- `subject`/`room`/`was_subject` всегда пустые → виджет показывает «—» вместо предметов.
Тест `tests/test_widget_api.py:63-72` проверяет только наличие ключей, не значения — баг не пойман.

#### 3. IDOR: `/api/widget/{user_id}` без аутентификации
**Файл:** `web/api.py:123-137`
Любой, зная (или перебирая) Telegram user_id, получает привязку «пользователь → школа → класс» и расписание. Контраст с `/api/me` (114-121), где проверяется HMAC-подпись `initData`. В `docs/WIDGET.md:201-203` рекомендация добавить HMAC есть, но не реализована.

#### 4. XSS в widget.html
**Файл:** `web/static/widget.html:203-209`
`lesson.num/time/subject/room` интерполируются в `container.innerHTML` без `escapeHtml` (в отличие от `app.js`, где экранируется всё). Источник — названия предметов/кабинетов из внешней выгружаемой расписалки: компрометация выгрузки = stored-XSS с доступом к Cache Storage, API, Service Worker.

#### 5. PWA полностью сломано: иконок нет на диске
**Файлы:** `web/static/manifest.json:11-22`, `web/static/index.html:10-11`
Ссылаются на `icon-192.png`/`icon-512.png`, которых нет в `web/static/` → 404, установка PWA невозможна, `beforeinstallprompt` никогда не сработает, весь код install-prompt (`index.html:76-99`) мёртв.

#### 6. Напоминания не применяют замены и переносы праздников
**Файл:** `services/reminder_service.py:112-115`
`get_due_reminders_detailed` берёт `day_num = now.isoweekday()` и вызывает `_get_schedule_data` **без** `apply_exchanges_to_schedule` и **без** `_get_effective_day`/`week_num` (сравните с `digest_service.py:73-75` и `schedule_service.py:101-120`). Пользователь получит напоминание об **отменённом** уроке, о заменённом предмете, а в день переноса — по расписанию «настоящего» дня недели.

#### 7. Блокирующее дисковое I/O в event loop на каждом клике
**Файлы:** `database/file_db.py:49-93` + вызовы из async-хэндлеров
Каждая запись FileDB = полный `json.dump` всей БД + `fsync` + `shutil.copy2` (.bak) + `os.replace` + fsync директории. Вызывается синхронно из async-кода: `handlers/callbacks/class_callbacks.py:72` (каждый выбор класса), `handlers/schools/school_selection.py:88`, все тогглы `handlers/common/settings.py`, `entity_menu.py:308,311`, `_save_sent_reminders`/`_save_sent_digests` на каждого получателя в рассылках (`core/background_updater.py:130,139,240,249`), `save_notifications_cache()` из async-рассылки (`services/notification_service.py:330`). Event loop один на бота и веб (`bot.py:358-360`, `web/server.py:44-61`) — пики дисковой латентности бьют по всем пользователям и Mini App.

---

### 🟠 Серьёзные

#### 8. Дайджест не учитывает перенос праздников и weeknum
**Файл:** `services/digest_service.py:73`
Замены применяются, но `_get_schedule_data(period_id, class_id, now.isoweekday())` без `_get_effective_day` и `week_num` — в перенесённый день дайджест покажет расписание не того дня.

#### 9. Тихие часы: пользователи навсегда теряют уведомления о заменах
**Файл:** `services/notification_service.py:313-317, 328-330`
Если `sent_count > 0` (или все получатели в тихих часах), замена помечается отправленной **для всех** — пропущенные по тихим часам никогда не получат её. Для напоминаний/дайджестов это осознанно корректно (теряют актуальность), для замен — потеря важных данных.

#### 10. Потеря уведомлений при сбое отправки
**Файл:** `core/background_updater.py:525-551`
`detect_exchanges` мутирует baseline до отправки, `save_cache` (571) фиксирует его независимо от результата notify. Если Telegram был недоступен и все отправки упали, замены уже не «новые» — уведомление не повторится никогда.

#### 11. Неатомарная запись notifications_cache.json
**Файл:** `services/notification_service.py:112-130`
Единственный кэш, пишущийся прямым `open('w')` + `json.dump` (остальные — tmp+`os.replace`). Крах в момент записи → битый JSON → при старте `json.load` падает → кэш сбрасывается → **массовые дубли уведомлений**.

#### 12. Мультишкольные пользователи: напоминания по «случайной» школе
**Файл:** `services/reminder_service.py:27-35`
`to_user_classes` оставляет класс последней школы в порядке обхода; `current_school` игнорируется. Пользователь с классами в двух школах получает напоминания/дайджесты не по той, что выбрал текущей.

#### 13. Markdown-инъекция имени пользователя валит /start
**Файл:** `handlers/start.py:23-24, 47`
`user.first_name` вставляется в welcome-текст без `escape_markdown`, отправка с `parse_mode='Markdown'`. Имя с `*`/`_`/`` ` ``/`[` → «Can't parse entities» → вместо меню GENERIC_ERROR_MSG. Имя пользователь контролирует сам.

#### 14. Залипание FSM-флагов `waiting_for_*`
**Файл:** `handlers/common/entity_menu.py:367-369`, `handlers/common/class_schedule.py:53-94`
`search_input()` ставит флаг поиска, не сбрасывая sibling-флаг и без TTL: клики по старым кнопкам «Поиск» учителя и кабинета оставляют оба флага активными; клик по старой кнопке + любой текст спустя неделю интерпретируется как поисковый запрос.

#### 15. callback_data >64 байт ломает клавиатуру «Обновить»
**Файл:** `handlers/common/entity_menu.py:276-281`
При `idx is None` (state-кэш истёк, кнопка на старом сообщении) callback строится с полным ФИО; кириллица ×2 байта + префикс `teacher_today_` легко превышают лимит → Telegram отклоняет всю клавиатуру → «❌ Произошла непредвиденная ошибка».

#### 16. O(N×M)-сканы каждую минуту в event loop
**Файл:** `core/background_updater.py:97-105, 209-217`
`_send_reminders` и `_send_digests` (раз в минуту оба): полный проход users + для каждого — линейный скан всей коллекции preferences с deep-copy. Синхронно в event loop.

#### 17. `window.prompt` в Telegram WebApp — «Свободные кабинеты» мертвы на мобильных
**Файл:** `web/static/app.js:134-137`
WebView Telegram (iOS/десктоп) не поддерживает `window.prompt`, молча возвращает null → фича недоступна без объяснения.

#### 18. Режим «Неделя» игнорирует навигацию по датам
**Файл:** `web/static/app.js:110`
`const off = 0; // неделя — всегда текущая`: стрелки «‹ ›» меняют подпись, но контент всегда текущая неделя.

#### 19. manage.sh: откат при неудачном обновлении неполный
**Файлы:** `manage.sh:489-497, 524`
`pip install -r requirements.txt` выполняется до рестарта; при провале health-check откатывается только код (`git reset --hard`), зависимости остаются новыми поверх старого кода. Созданный бэкап при откате не применяется и даже не предлагается.

#### 20. Отсутствие rate limiting на API
**Файл:** `web/api.py` — все маршруты без лимитера. Дефолтный `127.0.0.1` предполагает reverse proxy, но защиты в приложении нет.

#### 21. Конфиг живого сервера расходится с безопасными дефолтами
**Файлы:** `.env:19-20` (`WEBAPP_HOST=0.0.0.0`, `WEBAPP_PORT=80`) vs `config/config.py:97`, `.env.example:27-29`
API торчит в интернет без TLS; команда `manage.sh caddy` заблокирована собственной защитой (`manage.sh:819-822`). Ни `Config`, ни `doctor` не предупреждают о расхождении.

#### 22. Бэкапы с токеном читаются всеми
**Файл:** `manage.sh:599-602`
tar.gz с `.env` (токен бота) создаётся с дефолтным umask → обычно chmod 644, читается всеми локальными пользователями сервера.

---

### 🟡 Средние

#### 23. Service Worker: персональный кэш без TTL и ошибки жизненного цикла
**Файл:** `web/static/service-worker.js:18, 41-58, 62-66`
`/api/*` (включая `/api/me`) кладётся в Cache Storage без срока; `skipWaiting()` вне `event.waitUntil` (гонка активации); статику отдаёт cache-first навсегда — обновления не применяются до смены `CACHE_NAME`.

#### 24. Два независимых экземпляра NotificationService
**Файлы:** `core/background_updater.py:121, 231` + `bot.py:168`
Fallback `bot_data.get(...) or self.notification_service` поднимает второй экземпляр на тот же файл кэша: два писателя, last-write-wins.

#### 25. TOCTOU-гонка на `_update_lock`
**Файлы:** `core/background_updater.py:361-364`, `handlers/callbacks/admin_callbacks.py:206-210, 258-262`
`if lock.locked(): return` перед `async with` — между проверкой и захватом другую корутину можно пропустить вперёд. Последствия мягкие, но паттерн «пропустить, если занято» не гарантируется.

#### 26. DataLoader без close() в ручном refresh
**Файлы:** `handlers/callbacks/admin_callbacks.py:214, 266`, `bot.py:193`
Создаётся `DataLoader()` (httpx.Client) и не закрывается — на GC.

#### 27. Деактивированные школы остаются в bot_data
**Файл:** `core/background_updater.py:338-343`
`_merge_schools_data` только добавляет/обновляет: школа с `active=False` живёт до рестарта.

#### 28. Старт без ретрая при недоступном сайте
**Файл:** `bot.py:205-207`
Провал начальной загрузки → `schools_data = {}` до первого планового цикла (по умолчанию час).

#### 29. Спам админам при длительном сбое
**Файл:** `core/background_updater.py:413-421`
Все школы недоступны → одно и то же сообщение на каждый плановый цикл.

#### 30. Подписчикам преподавателя приходит текст всех замен класса
**Файлы:** `core/background_updater.py:614` + `notification_service.py:207`
Один `text` из всего `class_exchanges` — информационный шум для подписчика конкретного учителя.

#### 31. Дедуп замен по md5 всего набора
**Файл:** `services/notification_service.py:291-295`, `core/background_updater.py:578-596`
Ключ строится из подписи **всех** замен класса: новая замена → повторное уведомление со всеми старыми заменами класса.

#### 32. Тройной троттлинг рассылок
`notification_service.py:34, 171-177, 233, 322` поверх `AIORateLimiter(max_retries=3)` (`bot.py:81`): массовая рассылка идёт минуты **под `_update_lock`**, блокируя ручные обновления.

#### 33. manage.sh: ложный «бот запущен», User=root, restore без бэкапа
- `manage.sh:263` — `>> logs/bot.log` без `mkdir -p logs`: PID-файл с мёртвым PID, сообщение об успехе;
- `manage.sh:435` — `User=${USER}` в systemd-юните: при sudo часто root, без подтверждения;
- `manage.sh:620-622` — restore распаковывает бэкап поверх live-данных без предварительного бэкапа текущего состояния;
- `manage.sh:963` — bootstrap-install делает `git reset --hard @{upstream}` без проверки локальных изменений (в отличие от `cmd_update:463`);
- `manage.sh:210-224` — TOCTOU между `kill -0` и `kill` в do_stop.

#### 34. Валидация конфига
- `config/config.py:11` — `TIMEZONE=мусор` → необработанный `ZoneInfoNotFoundError` на импорте (у int-переменных понятные сообщения, у TZ нет);
- `config/config.py:74,98` — нет диапазонов: `UPDATE_INTERVAL ≤ 0`, `WEBAPP_PORT > 65535` падают только в рантайме;
- `config/config.py` — нет предупреждения о `WEBAPP_HOST=0.0.0.0`.

#### 35. requirements-dev устарел, coverage не измеряется
- `pytest==7.4.0` (актуальна 9.x), `pytest-asyncio==0.23.0` (актуальна 1.x; в `__pycache__` лежат .pyc от двух разных версий pytest — окружение нестабильно);
- `tests/test_integration.py:5` — `pytest_plugins = ['anyio']` без явного пина anyio (транзитивная зависимость FastAPI);
- `pytest-cov` отсутствует: покрытие не измеряется ни локально, ни в CI;
- `pytest.ini` — нет `filterwarnings`: депрекейшен PTB `retry_after` → `tests/test_notification_retry.py:14` молча сломается при апгрейде PTB.

#### 36. Часовой пояс UI ≠ серверный
**Файл:** `web/static/app.js:32-35, 98` — «сегодня» по TZ устройства, сервер по `TIMEZONE`. Для пользователя в другой TZ подпись даты и данные разойдутся.

#### 37. Мелочи UX
- `handlers/callbacks/class_callbacks.py:75` — `query.answer()` не вызывается на успешном пути → спиннер ~15 с;
- `web/static/app.js:26-27` — 422 (detail-массив) отображается как список словарей;
- `handlers/callbacks/navigation_callbacks.py:126-137` — невалидируемый `schedule_type` из callback → generic-error вместо понятного сообщения;
- `bot.py:1` — мусорный заголовок `# File: c:\Users\set\...`;
- `moscow_tz` содержит `Asia/Yekaterinburg` (`background_updater.py:28`, `status_service.py:25`) — вводящее имя.

#### 38. Низко-приоритетные технические долги
- `services/cache_service.py:32-41` — O(n²) вытеснение при заполненном кэше (state_cache TTL 24 ч, лимит 10 000);
- `core/data_loader.py:145, 168` — `copy.deepcopy` всей расписалки на каждый 304 (2× память в `_http_cache`);
- `services/state_service.py:39` — `cache.get(key) or default`: сохранённый `0` неотличим от отсутствия записи;
- `core/background_updater.py:331-334` — после ошибки цикла двойное ожидание (300 с + полный интервал);
- `core/background_updater.py:434` — f-string с `` ` `` в Markdown-уведомлении админам: исключение с бэктиками → «Can't parse entities»;
- `services/exchange_detector.py:187-199 vs 216-218` — двойное форматирование всех замен на каждый цикл;
- `notification_service.py:35` — `_last_sent_at` растёт неограниченно;
- `mypy.ini:3` — `ignore_missing_imports` глобально;
- `.gitignore` — кэши инструментов не перечислены (держатся только на внутренних .gitignore).

### Проверено и НЕ является проблемой

- HMAC-валидация `initData` (`web/auth.py:21-40`) — корректна (`compare_digest`, freshness `auth_date`); заметьте: окно 24 ч допускает replay — для GET с публичными данными приемлемо;
- XSS в `app.js` отсутствует — все 9 innerHTML через `escapeHtml`;
- `file_db.find_one` возвращает deep-copy — мутации безопасны;
- httpx.Client в ThreadPoolExecutor потокобезопасен;
- RetryAfter-ретраи в `_send_message` корректны;
- CSRF не применим (API только GET, без cookies);
- `.env` никогда не коммитился (в истории только `.env.example`).

---

## 🎯 To-do план

### Фаза 0 — критические исправления (эта неделя)

- [ ] **T1. Починить CI.** Добавить `tests/conftest.py` (пустой) или `conftest.py` в корень; убедиться, что `pytest -q` работает без `PYTHONPATH`. Проверить зелёный раннер на GitHub. *Файл: tests/conftest.py, .github/workflows/ci.yml*
- [ ] **T2. Починить widget API.** Переписать `web/api.py:153-194` под реальный payload `{num, start, end, items, has_exchange, is_cancelled}`: `lesson_time` из `start/end`, `subject/room` из `items[0]`, `was_subject` — из exchange-данных. Усилять тест `test_widget_api.py` проверками **значений**, не только ключей. *Файлы: web/api.py, tests/test_widget_api.py*
- [ ] **T3. Закрыть IDOR.** Валидировать `X-Telegram-Init-Data` в `/api/widget/{user_id}` (как в `/api/me`) и сверять `user_id` из подписи с запрошенным; 403 при несовпадении. *Файлы: web/api.py, tests/test_widget_api.py, tests/test_webapp_auth.py*
- [ ] **T4. Экранировать widget.html.** Добавить `escapeHtml` (как в app.js) для `lesson.num/time/subject/room` в блоке уроков (widget.html:203-209). *Файл: web/static/widget.html*
- [ ] **T5. Добавить иконки PWA.** Сгенерировать `icon-192.png`, `icon-512.png` (+ favicon/apple-touch-icon) в `web/static/`; проверить установку PWA. *Файлы: web/static/**
- [ ] **T6. Напоминания: применять замены и переносы.** В `get_due_reminders_detailed` — `apply_exchanges_to_schedule` + `_get_effective_day`/`week_num` по образцу `schedule_service.py:101-120`; тест на отменённый урок и день переноса. *Файлы: services/reminder_service.py, tests/test_reminders.py*
- [ ] **T7. Экранировать first_name в /start.** `escape_markdown(user.first_name)`. *Файл: handlers/start.py*

### Фаза 1 — надёжность данных и рассылок (недели 1-2)

- [ ] **T8. Атомарная запись notifications_cache.json** — tmp + `os.replace` (по образцу sent_reminders). Тест: крах в момент записи не рвёт кэш. *Файл: services/notification_service.py:112-130*
- [ ] **T9. Не терять уведомления о заменах при сбое.** Обновлять baseline/`save_cache` только после попытки доставки; либо хранить pending и ретраить. *Файл: core/background_updater.py:525-571*
- [ ] **T10. Тихие часы не глотают замены.** Не помечать отправленным для тех, кто пропущен по тихим часам (напоминания/дайджесты оставить как есть). *Файл: services/notification_service.py:313-330*
- [ ] **T11. Дайджест: переносы праздников и weeknum** (`_get_effective_day`), тест на перенесённый день. *Файл: services/digest_service.py:73*
- [ ] **T12. Мультишкольные пользователи: уважать `current_school`** в напоминаниях/дайджестах. *Файл: services/reminder_service.py:27-35*
- [ ] **T13. Снять блокирующее I/O с event loop.** Обернуть записи FileDB из async-хэндлеров в `asyncio.to_thread` (или добавить `FileDB.aio`-обёртки); batch-запись `_save_sent_reminders`/`_save_sent_digests` (одна запись на проход, не на получателя). *Файлы: database/file_db.py, handlers/callbacks/*, core/background_updater.py, services/notification_service.py:330*
- [ ] **T14. Убрать дубль NotificationService** — всегда один экземпляр из bot_data. *Файлы: core/background_updater.py, bot.py*

### Фаза 2 — безопасность и web-функциональность (недели 2-3)

- [ ] **T15. Rate limiting на API.** `slowapi` (или простой in-memory token bucket): `/api/*` 100/min, `/api/widget/*` строже. *Файлы: web/api.py, requirements.txt, tests/*
- [ ] **T16. Service Worker гигиена.** `/api/me` не кэшировать (или TTL); `skipWaiting` в `waitUntil`; для статики — stale-while-revalidate вместо вечного cache-first; bump `CACHE_NAME` при каждом деплое. *Файл: web/static/service-worker.js*
- [ ] **T17. «Свободные кабинеты» в WebApp без window.prompt** — inline-выбор номера урока (кнопки/селект). *Файл: web/static/app.js*
- [ ] **T18. Навигация по неделям в WebApp** — передавать `week_offset` в API (сейчас `off = 0` захардкожен). *Файлы: web/static/app.js:110, web/api.py*
- [ ] **T19. Исправить `.env` живого сервера**: `WEBAPP_HOST=127.0.0.1`, корректный `WEBAPP_PORT`; предупреждающий `doctor`-check для `0.0.0.0`/порта 80/443. *Файлы: .env, manage.sh (doctor), config/config.py*
- [ ] **T20. Бэкапы с токеном: `chmod 600`** (umask 077 при создании tar). *Файл: manage.sh:599*
- [ ] **T21. Валидация конфига**: понятная ошибка для TIMEZONE; диапазоны `UPDATE_INTERVAL > 0`, `WEBAPP_PORT ≤ 65535`. *Файл: config/config.py*

### Фаза 3 — качество инфраструктуры (недели 3-4)

- [ ] **T22. Обновить requirements-dev и стабилизировать тест-окружение**: pytest 9.x, pytest-asyncio 1.x (проверить семантику `asyncio_mode=auto`), явный пин anyio, добавить `pytest-cov`. *Файл: requirements-dev.txt, pytest.ini*
- [ ] **T23. Coverage в CI** с порогом (например fail < 60%, цель 80%); badge в README. *Файлы: .github/workflows/ci.yml, pytest.ini*
- [ ] **T24. Матрица Python 3.11/3.12/3.13 в CI** (manage.sh уже умеет ставить 3.13), pip-cache, шаг shellcheck для manage.sh. *Файл: .github/workflows/ci.yml*
- [ ] **T25. `filterwarnings`** в pytest.ini (минимум — PTB `retry_after` deprecation как error) + фикс `RetryAfter(0)` → timedelta. *Файлы: pytest.ini, tests/test_notification_retry.py*
- [ ] **T26. conftest.py**: общие фикстуры (TZ, `_make_db`) вместо дублей в 4+ тест-файлах. *Файл: tests/conftest.py*
- [ ] **T27. Покрыть тестами**: `web/server.py`, `services/state_service.py`, `services/status_service.py`, `handlers/common/week_command.py`, поведение `room_callbacks.py`/`teacher_callbacks.py` (сейчас только test_dead_code). *Файлы: tests/**
- [ ] **T28. Управление зависимостями обновления**: откат также переустанавливает старые requirements (или пиннинг версий в venv перед обновлением); при откате предлагать восстановление data/ из созданного бэкапа. *Файл: manage.sh:489-524*
- [ ] **T29. manage.sh мелкие баги**: `mkdir -p logs` перед стартом; предупреждение о User=root в systemd; restore только после бэкапа текущих данных; bootstrap-install — проверка локальных изменений перед `reset --hard`. *Файл: manage.sh*

### Фаза 4 — UX и архитектура (месяц 2)

- [ ] **T30. FSM: TTL и сброс sibling-флагов** в `search_input` (или переход на ConversationHandler — см. roadmap §4.2). *Файлы: handlers/common/entity_menu.py, class_schedule.py*
- [ ] **T31. callback_data ≤ 64 байт**: для «Обновить» без idx — короткий идентификатор (хэш/индекс в state-кэше). *Файл: handlers/common/entity_menu.py:276-281*
- [ ] **T32. `query.answer()` на успешных путях** (спиннер не висит 15 с). *Файл: handlers/callbacks/class_callbacks.py*
- [ ] **T33. Дедуп замен per-замена**, а не md5 всего набора. *Файлы: services/notification_service.py:291-295, core/background_updater.py:578-596*
- [ ] **T34. Подписчикам entity — только релевантные замены** (фильтрация по учителю/кабинету). *Файл: core/background_updater.py:614*
- [ ] **T35. O(N×M) напоминаний/дайджестов**: индекс preferences одним проходом, snapshot users без deep-copy каждого документа; вынести из event loop. *Файл: core/background_updater.py:97-105, 209-217*
- [ ] **T36. Троттлинг рассылок**: убрать дублирующие слои (свой `_min_send_interval` + sleep поверх AIORateLimiter), вынести рассылку из-под `_update_lock`. *Файлы: services/notification_service.py, core/background_updater.py*
- [ ] **T37. Ретрай начальной загрузки при старте** (например 3 попытки с backoff), чтобы бот не жил час без данных при кратком сбое сайта. *Файл: bot.py:205-207*
- [ ] **T38. Тихие часы с минутной точностью** (datetime.time, миграция данных, UI). *Файлы: services/user_preferences.py, handlers/common/settings.py*
- [ ] **T39. Уважать TZ сервера в WebApp** (`today` передавать с сервера или API-параметром). *Файл: web/static/app.js*

### Фаза 5 — долгосрочные архитектурные (месяцы 2-3, по roadmap §4)

- [ ] **T40. `JobQueue`** вместо ручных asyncio-циклов (`background_updater`, reminder/digest loops). *Файлы: bot.py, core/background_updater.py*
- [ ] **T41. Слой `UserRepository`** (закрыть прямой доступ NotificationService к user_service.db) + TypedDict для school_data. *Файлы: services/, database/*
- [ ] **T42. Отложенная запись FileDB** (dirty-флаг + периодический flush) или миграция на sqlite3 (stdlib) — отдельно, с бэкапом и тестом миграции. *Файл: database/file_db.py*
- [ ] **T43. Конфигурация через dataclass** (`AppConfig.from_env()`, SCHOOLS_CONFIG → JSON/YAML). *Файлы: config/*
- [ ] **T44. Sentry** (или минимальный алертинг админам при повторяющихся ошибках), метрики рассылок. *Файлы: bot.py, services/*
- [ ] **T45. Cache-first рендер расписания в WebApp + офлайн-режим** (SW уже есть — осмысленно использовать после T16).

---

## 📈 Метрики качества

| Метрика | Сейчас | Цель (1 мес) |
|---|---|---|
| CI | ❌ красный (23/23) | ✅ зелёный, обязательный |
| Тесты | 288 (локально) | 300+ и реально запускаются в CI |
| ruff / mypy | ✅ / ✅ | держать |
| Coverage | не измеряется | измеряется, ≥60% → 80% |
| Блокирующее I/O в event loop | на каждом клике | устранено (T13) |
| Widget API | нерабочий | рабочий + тест значений |
| PWA | сломано (нет иконок) | устанавливается |

---

## ⚠️ Риски

**Высокие (тестировать тщательно):**
- T13 (I/O в to_thread) — гонки записи, порядок операций; менять постепенно, под тестами;
- T42 (FileDB/SQLite) — живая система, только с бэкапом и откатом;
- T28 (откат зависимостей) — сценарий обновления/отката прогнать на копии.

**Средние:** T9-T10 (логика дедупа — риск дублей или повторных потеряний), T30 (FSM — риск новых залипаний), T40 (JobQueue).

**Низкие:** T4, T5, T7, T21, T26 — локальные фиксы.

---

## 🔗 Связанные документы

- [roadmap.md](roadmap.md) — исторические фазы и архитектурные рекомендации
- [CHANGELOG.md](CHANGELOG.md) — история изменений
- [WIKI.md](WIKI.md) — устройство проекта
- [docs/WIDGET.md](docs/WIDGET.md) — виджет (в т.ч. рекомендация HMAC, реализуемая в T3)

---

**Дата обновления:** 17 сентября 2026
**Основа:** анализ кода тремя независимыми проходами (services/core, web/handlers, тесты/инфраструктура) + ручная верификация критических находок (CI, widget API, PWA-иконки)