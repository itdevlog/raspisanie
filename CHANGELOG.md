# Changelog

История исправлений Telegram-бота расписания. Хронологический порядок (новое — вверху).
«Что осталось сделать» — см. [roadmap.md](roadmap.md).

## 13.09.2026

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
