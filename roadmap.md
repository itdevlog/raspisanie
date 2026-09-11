# Roadmap: анализ и план улучшений Telegram-бота расписания

> Полный аудит проекта от 03.09.2026. ~2700 строк Python, стек: python-telegram-bot 20.7, requests, pytz, JSON-БД.
> Приоритеты: 🔴 P0 — падения/потеря данных, 🟠 P1 — некорректное поведение, 🟡 P2 — качество и поддержка.

## 0. Статус на 11.09.2026 (после PR «Fix critical bugs»)

**Исправлено (коммит `80434ed`):**

| Что | Где |
|-----|-----|
| `AttributeError` на `self.moscow_tz` в `log_update_activity` — updatelog.txt теперь заполняется | `core/background_updater.py` |
| Хак `context = ContextTypes.DEFAULT_TYPE` (мутация класса PTB) → заменён на `SimpleNamespace` | `core/background_updater.py` |
| Дублирующийся метод `stop()` | `core/background_updater.py` |
| Краш `show_class_selection` при вводе несуществующего класса текстом (`query=None`) | `handlers/common/callback_handler.py` |
| Блокирующий sync-IO в админ-callback'ах → `asyncio.to_thread` (бот больше не замирает при обновлении из админки) | `handlers/callbacks/admin_callbacks.py`, `handlers/admin/admin_panel.py` |
| `FileDB.delete_one` удалял ВСЕ подходящие документы, а не один | `database/file_db.py` |
| Дублирующийся `FileDB.get_collection`, `except (…, Exception)` → `(json.JSONDecodeError, OSError)`, `print` → `logger` | `database/file_db.py` |
| Команды `/week` и `/school` не были зарегистрированы | `bot.py` |
| Понятная ошибка при незаданном `TELEGRAM_TOKEN` вместо падения внутри PTB | `bot.py` |
| `ExchangeDetector.clear_school_cache` не сохранял файл (возвращалось после рестарта); мусорный лог в `clear_cache` | `services/exchange_detector.py` |
| `Message is not modified` уходит в error handler → тихо игнорируется (частично: `main_menu`, `class_callbacks`, `callback_handler`; в `teacher_menu`/`room_schedule`/`school_info` — ещё нет) | `handlers/common/main_menu.py`, `handlers/callbacks/class_callbacks.py` |
| Заголовок с датой для «Сегодня/Завтра» (классы/преподаватели/кабинеты) | `services/schedule_service.py`, `services/teacher_service.py`, `services/room_service.py` |
| `CacheService.delete/delete_prefix`; `state_service.clear_user_state` реально удаляет ключи (была утечка: значения ставились в `None`) | `services/cache_service.py`, `services/state_service.py` |
| Недостающие `__init__.py` во всех пакетах (11 шт.) | `config/`, `core/`, `database/`, `handlers/*`, `services/` |

**Ещё исправлено ранее** (до аудита, отражено в WIKI §8, §16): глубокие копии замен, строковые ключи уроков, `sent_count > 0`, потокобезопасный `FileDB`, `bot_data['background_updater']`, `asyncio` в фоновом обновлении.

**Найдено при тестовом запуске 11.09** (см. §2, «Данные школ»):

- У школы 181 `SCHOOL_NAME` в выгрузке Nikasoft — **пустая строка**. `.get('SCHOOL_NAME', 'Неизвестно')` не срабатывает (ключ есть, значение `''`) → в стартовом списке `bot.py` выводится `- Загружено`, пустое имя в `/status`, «О школе», меню выбора класса. → ✅ **исправлено 11.09**: центральный helper `config/schools.py::get_display_name(school_id, school_data)` применён во всех 6 местах (`bot.py`, `status.py`, `school_info.py`, `callback_handler.py`, `background_updater.py`, `notification_service.py`).
- Косметика: кривой отступ в стартовом `print` (bot.py, `load_schools_data`). → ✅ **исправлено 11.09**: выровнен («• Имя - Загружено»).

**Осталось открытым** — см. таблицы ниже: детектор «только сегодня» в заменах, инвалидация кэша расписания, `remove_school`/висячий `current_school`, `Message is not modified` в легаси-`callback_handler` (вне роутера), пагинация «Все классы» (✅ 11.09), тесты. П.4, п.9, п.10, п.11, двойной `query.answer()`, залипшие флаги, уведомление-дефолты, `print`→`logger`, лог-ротация, конфиг-настройки, дубли `admin_panel.py`↔`admin_callbacks.py` и пагинация «Все классы» — ✅ закрыты.

---

## 1. 🔴 Критические баги (P0)

### Данные и корректность

| # | Место | Проблема | Исправление |
|---|-------|----------|-------------|
| 1 | `services/exchange_service.py:39,48,52,56` | Неглубокая копия `lesson.copy()` при применении замен → мутируется **вложенный** `lesson['data']`, общий с `bot_data['schools_data']`. Исходное расписание перезаписывается кодами замен, замены применяются повторно, сравнение old/new в апдейтере даёт ложные срабатывания | Копировать глубоко: `updated_lesson = {**lesson, 'data': {**lesson['data']}}` |
| 2 | `core/background_updater.py` | `context = ContextTypes.DEFAULT_TYPE` — атрибуты присваиваются **классу**, а не объекту. Глобальная мутация, гонка со всеми апдейтами | ✅ **исправлено 11.09**: `SimpleNamespace(application, bot_data, bot)` в `_make_context()` |
| 3 | `core/background_updater.py:193` | `log_update_activity()` использует несуществующий `self.moscow_tz` → `AttributeError` глотается, `updatelog.txt` **никогда не заполняется** | ✅ **исправлено 11.09**: `self.moscow_tz = pytz.timezone('Asia/Yekaterinburg')` в `__init__` |
| 4 | `database/file_db.py:17-19, 35-38` | При битом `database.json` загрузка возвращает `{}`, и первая же запись **перезаписывает файл пустым** — полная потеря пользователей. Запись не атомарна | ✅ **исправлено 11.09**: битый файл сохраняется в `database.json.corrupt` (с ротацией `.corrupt.N`) до перезаписи; запись атомарна через temp-файл + `os.replace()` |
| 5 | `services/exchange_detector.py:86,90,147-148, 26` | Ключи-`int` (номер урока) после JSON-раунд-трипа становятся `str` → `previous.get(lesson_num)` всегда `None` → **после каждого рестарта все замены рассылаются повторно** | ✅ сделано ранее: сравнение ключей как строк |
| 6 | `services/notification_service.py:147-150` | Уведомление помечается отправленным даже при 0 успешных доставок → замена **теряется навсегда**, если Telegram был недоступен | ✅ сделано ранее: `if sent_count > 0: _mark_notification_sent(...)` |

### Падения в обработчиках

| # | Место | Проблема | Исправление | Статус |
|---|-------|----------|-------------|--------|
| 7 | `bot.py:45` | `background_updater` не кладётся в `bot_data` → админ-кнопка «Принудительное обновление» **всегда падает** (`admin_callbacks.py:173` получает `None`) | Добавить `bot_data['background_updater'] = self.background_updater` | ✅ сделано ранее |
| 8 | `handlers/common/class_schedule.py:92` → `callback_handler.py` | Ввод несуществующего класса текстом: `show_class_selection` вызывает `query.edit_message_text` при `query=None` → `AttributeError` | Ветвиться: `if update.callback_query: edit else: reply_text` | ✅ **исправлено 11.09** |
| 9 | `handlers/common/class_schedule.py:99-103` | «Сегодня + завтра» одним сообщением без проверки длины → на старших классах `BadRequest: Message is too long` (>4096). То же для недельного расписания (`week_command.py:78`, `class_callbacks.py:83`, `teacher_menu.py:156`, `room_schedule.py:158`) | Нарезка сообщений по 4096 или отправка частями | ✅ **исправлено 11.09**: единый хелпер `handlers/common/messaging.py` (`split_long_message` + `edit_long_message`/`reply_long_message`); применён в `class_schedule`, `week_command`, `class_callbacks`, `teacher_menu`, `room_schedule`. Нарезка по границам строк, чтобы не рвать разметку Markdown |
| 10 | `handlers/teachers/teacher_menu.py:364, 378` и `handlers/rooms/room_schedule.py:378, 392` | **Два бага поиска:** (а) индексы из поиска применяются к полному списку (`teacher_callbacks.py:84` читает `'teachers'` вместо `'search_teachers'`) → клик по результату даёт **чужого** учителя/кабинет; (б) `callback_data=f"teacher_search_{запрос}_{page}"` с кириллицей превышает лимит 64 байта → поиск «зависает» | ✅ **исправлено 11.09**: результаты поиска хранятся под отдельными ключами `search_teachers`/`search_rooms`; источник списка закодирован в callback (`sidx_` = поиск vs `idx_` = полный) в `teacher_callbacks`/`room_callbacks` и дневных кнопках; запрос поиска переехал в `user_data` (`teacher_search_query`/`room_search_query`), пагинация — `teacher_search_page_N`/`room_search_page_N` (все ≤64 байт) |
| 11 | `handlers/common/callback_handler.py:120` | Проверка наличия классов по префиксу: цифра `1` матчится и с `11а` → кнопка «1» показывается, даже если классов `1x` нет | ✅ **исправлено 11.09**: новый хелпер `_class_matches_digit` сравнивает по сегментам — цифра матчится только если за ней стоит буква (не десяток); применён в `show_class_selection` и `_get_class_letters_for_digit` |
| 12 | `services/schedule_service.py:131`, `exchange_service.py:65` | Поиск класса по подстроке: `"5"` матчится с `"10Б"` → расписание/замены могут примениться **не к тому классу** | Точное сравнение + нормализация, либо явный `class_id` | ✅ сделано ранее |
| 13 | `services/schedule_service.py:115`, `room_service.py:86`, `teacher_service.py:86` | Ключ урока `f"{day_num}0{lesson_num}"` даёт `"4010"` для дня 4/урока 10 — конфликт форматов при `LESSONSINDAY > 9` (дефолт 12) | Явный формат `f"{day_num}{lesson_num:02d}"` | ✅ сделано ранее |

### Блокировка event loop

| # | Место | Проблема | Исправление | Статус |
|---|-------|----------|-------------|--------|
| 14 | `core/background_updater.py:96`, `admin_callbacks.py:122-123,150-151` | Синхронный `requests` (`load_all_schools_data`, до минут с ретраями) вызывается прямо в async-обработчиках → **весь бот перестаёт отвечать** всем пользователям | `await asyncio.to_thread(loader.load_all_schools_data)` | ✅ **исправлено 11.09** (в т.ч. в `admin_panel.py`) |
| 15 | `core/background_updater.py:57-59` | Приватный `application.update_queue._loop` + поток стартует до `run_polling()` | Перейти на `application.job_queue.run_repeating()` (устраняет заодно #2, #16) | ✅ сделано ранее (asyncio.create_task); JobQueue — рекомендация на будущее |

---

## 2. 🟠 Серьёзные баги (P1)

### Telegram-протокол

- **Двойной `query.answer()`** — `handlers/callbacks/__init__.py:36` отвечает на query сразу, поэтому все тосты об ошибках внутри обработчиков (`class_callbacks.py:17,31`, `room_callbacks.py:25,49`, `teacher_callbacks.py:25,49,61`, `navigation_callbacks.py:35,37,112`) **не показываются вообще**. → ✅ **исправлено 11.09**: роутер больше не отвечает на query заранее — ответ берёт на себя обработчик (`query.answer(...)` для тостов, `edit_message_text` для успешных действий). PTB-objects заморожены, поэтому отследить «уже ответил» из роутера нельзя; вместо этого просто убран авто-answer.
- **`Message is not modified`** — повторное нажатие «Обновить»/«Назад» уходит в error handler с «непредвиденной ошибкой» (`class_callbacks.py:83`, `teacher_menu.py:156,267`, `room_schedule.py:158,274`, `main_menu.py:101`, `school_info.py:59`, `callback_handler.py:144,187,270`). Обработано только в админ-панели. → ✅ **исправлено 11.09**: добавлен хелпер `messaging::safe_edit_message` (глотает BadRequest «not modified»), применён в `school_info` и во всех рендер-путях через `edit_long_message` (`class_callbacks`, `teacher_menu`, `room_schedule`).
- **Кнопки-заглушки без обработчика** — `teacher_menu.py:240,380`, `room_schedule.py:247,394` (`*_pages_info`) → «Неизвестная команда навигации». → ✅ **исправлено 11.09**: `teacher_pages_info`, `room_pages_info` (и `*_search_pages_info`) отвечают тостом «Используйте кнопки навигации по страницам».
- **Обрезка Markdown посередине** — `admin_panel.py:278-279`, `admin_callbacks.py:278-279` (`text[:4000]`) ломает `*...*`/`` `...` `` → `Can't parse entities`. Обрезать по границе строки.
- **Неполное экранирование** — `base_schedule_service.py:67,91,100,109`: не экранируются `[`, `]`, `(`, `)` для legacy Markdown → сообщение не уйдёт.
- **`await query.answer()` без проверки** — `room_schedule.py:365`, `teacher_menu.py:351` при вызове из текстового ввода (`query=None`).

### Логика состояния

- **Залипшие флаги поиска** — `class_schedule.py:36-41`: флаг `waiting_for_teacher_search`/`waiting_for_room_search` не сбрасывается при выходе в меню → следующий любой текст интерпретируется как поиск. → ✅ **исправлено 11.09**: хелпер `messaging::clear_search_flags(context)` сбрасывает все `waiting_for_*` флаги; вызывается в точках входа — `main_menu_handler`, `teacher_menu_handler`, `room_menu_handler`, `show_all_teachers`, `show_all_rooms`.
- **Утечка `class_digit`** — `callback_handler.py:113,152`: выбор цифры класса не сбрасывается при смене школы → пустой список букв. → ✅ **исправлено 11.09**: `class_digit` сбрасывается в `handle_school_selection` и в `main_menu_handler`.
- **Сохранение списка до сортировки по ссылке** — `room_schedule.py:201-206`, `teacher_menu.py:198-203`: в `state_service` кладётся ссылка, затем `sort()` мутирует её. Скрытый рассинхрон индексов кнопок.
- **TTL кэша ломает кнопки** — списки в `CacheService(ttl=600)` живут 10 минут, индексные кнопки потом «мёртвые» навсегда. Хранить в `context.user_data` или имена в callback_data.

### Замены и уведомления

- **Детектор смотрит только «сегодня»** — `background_updater.py:216`, `exchange_detector.py:126`: замены на завтра/неделю не обнаруживаются; после полуночи вчерашние исчезают. Дата в заголовке уведомления подменяется текущей (`notification_service.py:99`).
- **Две независимые системы настроек уведомлений** — `user_service.py:100-150` vs `user_preferences.py:12-19`, дефолты противоречат друг другу (`False` vs `True`). → 🟡 **частично исправлено 11.09**: системы остались для разных целей (пользовательские уведомления vs админские update-уведомления), но дефолт в `background_updater._get_admin_notification_settings` синхронизирован с UI (`update_notifications: False`): раньше админ-уведомления слались хотя UI показывал «Выкл».
- **`clear_school_cache` не сохраняет файл** — `exchange_detector.py:264-267`: после рестарта «очищенное» возвращается. → ✅ **исправлено 11.09** (теперь вызывает `save_cache()`).
- **Экранирование до бизнес-логики** — `room_service.py:95-100`, `teacher_service.py:95-100`: `class_name` экранируется (`replace('*','\\*')…`) и затем передаётся в `apply_exchanges_to_schedule`, где `_find_class_id` сравнивает его с «чистыми» именами → замены для расписаний учителей/кабинетов **не находятся**.
- **`ExchangeService` создаётся в цикле** — `exchange_detector.py:102`: на каждую школу каждый тик.

### Данные школ (найдено при запуске 11.09)

- **Пустой `SCHOOL_NAME` у школы 181** — в выгрузке Nikasoft ключ есть, но значение `''`; везде `school_data.get('SCHOOL_NAME', 'Неизвестно')` молча даёт пустую строку (`bot.py` стартовый список, `status.py:22`, `school_info.py:28`, `callback_handler.py` → меню выбора класса, `admin_*.py`). → ✅ **исправлено 11.09**: helper `get_display_name(school_id, school_data)`.
- **Косметика**: лишний отступ в стартовом `print` списка школ (`bot.py`, `load_schools_data`). → ✅ **исправлено 11.09**.

### Инфраструктура

- **Сломанный startup-уведомитель** — `bot.py:198-220`: ручной `asyncio.get_event_loop()` + `run_until_complete` до `run_polling()`, `Bot` ещё не инициализирован. → ✅ **исправлено ранее**: `_post_init` через `Application.builder().post_init(...)` (см. WIKI §4).
- **`FileDB` без потокобезопасности** — read-modify-write в `user_service.py:65-97` из event loop и фонового потока → потерянные обновления. → ✅ **исправлено ранее**: `threading.RLock` + атомарная запись через temp-файл (`WIKI §3`). Осталась проблема п.4 (битый файл перезатирается).
- **Настройки конфига игнорируются** — `UPDATE_INTERVAL` (захардкожен `1800` в `background_updater.py:17`), `MAX_RETRIES`, `CACHE_PATH` не читаются нигде. → ✅ **исправлено 11.09**: `UPDATE_INTERVAL` → `BackgroundUpdater.update_interval`; `MAX_RETRIES` → дефолты `DataLoader.get_current_filename/download_schedule_data/load_school_data`; пути кэшей/логов (`exchange_cache.json`, `notifications_cache.json`, `updatelog.txt`) выводятся из `DB_PATH`, а не из cwd.
- **Падение при невалидном `.env`** — `config/config.py:11-15`, `bot.py:51`: `ValueError`/`AttributeError` на импорте без понятного сообщения.
- **`remove_school` оставляет висячий `current_school`** — `database/models/user_school.py:21-31`; сам класс `UserSchool` нигде не используется — удалить или подключить.

### Мёртвый код (удалить)

- `handlers/admin/admin_panel.py` — **частично** дублирует `admin_callbacks.py` (callback-часть мертва, но `setup_admin_handlers` регистрирует `/admin`, `/stats` — живой код). Требует аккуратного слияния, а не простого удаления. → ✅ **исправлено 11.09**: из `admin_panel.py` удалён мёртвый callback-код (`admin_callback_handler`, `_force_update`, `_refresh_all_schools`, `_refresh_school`, `_show_users_with_classes` — они жили/живут в `AdminCallbackHandler` в `handlers/callbacks/admin_callbacks.py`, куда роутер и направляет `admin_*`). Файл сокращён 306→130 строк, остался только живой код `/admin`/`/stats`. Бот больше не импортирует несуществующий `admin_callback_handler`.
- `handlers/common/week_command.py` — команда `/week` **не регистрировалась**. → ✅ **исправлено 11.09**: `/week` и `/school` зарегистрированы в `bot.py`.
- `callback_handler.py:282-333` (`handle_school_info`), `class_schedule.py:36-41` (флаг `waiting_for_teacher`), `navigation_callbacks.py:69-76,114-122` (недостижимые ветки), закомментированный блок `notification_service.py:247-317`, заглушка `_get_user_service:242-245`, `UserSchool`, `['order']` в конфиге школ. → открыто

---

## 3. 🟡 Улучшения (P2)

### Дублирование кода (главная проблема поддержки)

1. **`teacher_menu.py` ↔ `room_schedule.py` — ~90% совпадений** (423 и 437 строк): меню, поиск, пагинация. Абстрактный `EntityMenuHandler` сэкономит ~400 строк и устранит рассинхрон багов.
2. **Главное меню** — `start.py:44-104` ↔ `main_menu.py:31-101`. Вынести в `build_main_menu()`.
3. **Текст помощи** — `start.py:110-146` ↔ `callback_handler.py:339-378` (уже расходятся по содержанию). Один `HELP_TEXT`.
4. **Поиск школы по id** — 6 мест (`start.py:32`, `main_menu.py:19`, `callback_handler.py:99`, `teacher_menu.py:45`, `room_schedule.py:45`, `admin_callbacks.py:78`). Одна функция `get_school_by_id()`.
5. **Пагинация** — 4 одинаковых реализации. Функция `paginate(items, page, per_page)`.
6. **Проверки `if not user_service or not schools_data`** — 20+ повторов. Декоратор `@requires_school`.
7. **Проверка админа** — 4 разных способа. Один `is_admin()`.
8. **Часовой пояс** — `Asia/Yekaterinburg` в 5 местах, везде назван `moscow_tz` (реально UTC+5). В конфиг как `TIMEZONE`.

### UX

- Пагинация «Все классы» отсутствует (`callback_handler.py:208-278`) — при 60+ классах клавиатура упрётся в лимит 100 кнопок. → ✅ **исправлено 11.09**: `handle_show_all_classes` разбит на страницы (60 кнопок/стр.), список кэшируется в `state_service`, навигация через `all_classes_page_N`, общий хелпер `messaging::paginate`.
- Ошибки показывают `str(e)` пользователю (`class_callbacks.py:90` и др.) — утекают внутренности. Общий текст + лог.
- «Список устарел» оставляет мёртвую клавиатуру — перерисовывать актуальный список вместо тоста.
- Нет кнопки «Обновить» в клавиатурах учителей/кабинетов (в классах есть).
- Ввод поиска без ограничения длины и кнопки «Отмена» (только «Назад», не сбрасывающая флаг).
- Прогресс для долгих админ-операций: `ChatAction.TYPING` или статус по школам.

### Данные и производительность

- **Кэш расписания не инвалидируется после фонового обновления** — ключи без версии данных, пользователи до 10 минут видят старое (`schedule_service.py:20-93`, TTL в `bot.py:62`). Добавить в ключ хэш данных + явный `cache_service.clear()` в `_perform_update`.
- **O(N²) в подборе получателей** — `notification_service.py:159-184`: полный проход по всем пользователям на каждый класс. Собрать индекс `(school_id, class) → [user_id]` одним проходом.
- **`FileDB` перезаписывает весь JSON на каждую операцию** (`file_db.py:72,80,96`) — dirty-флаг + отложенная запись, или перейти на `sqlite3` (stdlib).
- **Кэш уведомлений** — `notification_service.py:337-344`: «последние 100» через `list(set)[-100:]` — порядок не гарантирован; обещанной очистки по 24 ч нет. Хранить `Dict[key, timestamp]`.
- **Дублирование запросов в `data_loader`** — вложенные ретраи дают до 9 запросов на школу; нет ETag/If-Modified-Since; `except Exception` ловит и `JSONDecodeError` (ретрай бессмысленен); парсинг по `'var NIKA='` хрупок; `Session` не закрывается.
- **Относительные пути от cwd** — `exchange_detector.py:18`, `notification_service.py:21`, `config.py:31-33`: запуск не из корня молча создаст новую пустую `data/`. Пути от `__file__`/Config. → 🟡 **частично исправлено 11.09**: `exchange_cache.json`, `notifications_cache.json`, `updatelog.txt` выводятся из `DB_PATH`; `setup_directories` по-прежнему от cwd.
- **`CacheService`** — нет лимита размера и потокобезопасности; `get_stats` сериализует весь кэш в строки.

### Логирование и безопасность

- Токен бота пишется в `logs/bot.log` в URL httpx — не публиковать логи; настроить `RotatingFileHandler` (сейчас файл растёт бесконечно, `bot.py:49-53`). → ✅ **исправлено 11.09**: `RotatingFileHandler` (5 МБ x 3) + `StreamHandler`; httpx приглушён до WARNING (в debug не пишутся URL-ы с токеном).
- ~36 `print()` вперемешку с `logger` (`data_loader`, `background_updater`, `bot.py`, `status_service.py:84-85`, `school_selection.py:89`; `file_db.py` — ✅ очищен 11.09). Унифицировать на logging. Плюс stdout буферизуется при systemd/перенаправлении — теряется диагностика. → ✅ **исправлено 11.09**: все `print()` заменены на `logger` (`data_loader`, `background_updater`, `bot.py`, `status_service`, `room_schedule`, `school_selection`).
- `ADMIN_LOG_FILE` объявлен в конфиге (`config.py:26`), но нигде не используется.
- `logging.basicConfig(filename=...)` глушит консоль — не видно работы под systemd. → ✅ **исправлено 11.09**: добавлен `StreamHandler`, консоль работает вместе с файлом.

---

## 4. Архитектурные рекомендации

1. **`JobQueue` вместо ручного потока** — заменить `threading.Thread` + `run_coroutine_threadsafe` + приватный `_loop` на `application.job_queue.run_repeating(...)`, а блокирующий `DataLoader` — на `asyncio.to_thread`. Устраняет сразу п.2, 14, 15 и проблемы `stop()`.
2. **`ConversationHandler` вместо FSM-флагов** — флаги `waiting_for_*` в `user_data` — источник «залипаний». Регистрировать до общего `MessageHandler(TEXT & ~COMMAND)` в `bot.py:127`.
3. **Слой данных** — `NotificationService` лезет в `user_service.db` напрямую (`notification_service.py:163`). Завести `UserRepository` с методами вроде `get_users_by_class(school_id, class_name)`.
4. **Форматирование/экранирование** — размыто по 4 файлам. Вынести в `render.py`, перейти на `HTML` parse_mode.
5. **Конфигурация** — `@dataclass(frozen=True)` c `from_env()` и валидацией; `SCHOOLS_CONFIG` в JSON/YAML, чтобы добавление школы не требовало правки кода.
6. **Типизация** — `TypedDict`/dataclass для структуры school_data (формат Nikasoft сейчас известен только «по месту»); `mypy` для `services/`; исправить аннотации `_get_room_index(...) -> int` (реально `Optional[int]`).
7. **Структура handlers** — регистрировать `CallbackRouter` напрямую, builders клавиатур вынести в `handlers/keyboards.py`; зависимости прокидывать одним `Services`-объектом вместо 20 повторов `context.bot_data.get(...)`.

---

## 5. Тесты (их сейчас нет вообще)

Приоритетные юнит-тесты (чистые функции, без Telegram):

- `ExchangeService.apply_exchanges_to_schedule` — тест «исходные данные не изменились» (ловит п.1);
- `ExchangeDetector._compare_class_exchanges` с раунд-трипом через `json.dumps/loads` (ловит п.5);
- `FileDB` — битый файл, upsert, параллельная запись (ловит п.4);
- `_find_class_id` — однозначность матчинга классов (ловит п.12);
- `_get_class_letters_for_digit` — `11а` vs `1а` (ловит п.11);
- роутинг callback-префиксов `_get_handler_key`;
- пагинация: 0/1/30/31 элементов, page=-1, page=999;
- генератор длинного недельного расписания → проверка нарезки ≤4096 (ловит п.9).

Интеграционные (pytest-asyncio + мок): ввод несуществующего класса текстом (п.8), клик по результату поиска (п.10), двойное нажатие «Обновить», `admin_force_update` (п.7).

---

## 6. Порядок работ (предлагаемый)

| Этап | Что | Закрывает | Статус |
|------|-----|-----------|--------|
| **1. Стабилизация** | Баги п.1, 3, 4, 5, 6, 7 — мутация данных, потеря БД, дубли уведомлений, мёртвый апдейт-лог, кнопка админа | П.1, 3, 5, 6, 7 ✅ сделаны (п.3, 5, 6, 7 — ранее; п.2 частично); **п.4 (битый database.json) — ✅ закрыто 11.09** | 🟡 почти |
| **2. Отзывчивость** | П.14, 15 + JobQueue вместо потока | П.14 ✅ **исправлено 11.09** (в т.ч. admin callbacks); JobQueue — рекомендация | 🟡 частично |
| **3. Telegram-протокол** | Двойной answer (✅ 11.09), `Message is not modified` (✅ частично), нарезка 4096 (✅ 11.09), callback_data 64 байт (✅ 11.09), кнопки-заглушки | Тосты, падения на кликах | 🟡 частично |
| **4. Поиск и состояния** | П.10 (✅ 11.09), заливание флагов (✅ 11.09), `class_digit` (✅ 11.09), TTL-кнопки | Корректный поиск учителей/кабинетов | 🟡 частично |
| **5. Замены** | Строковые ключи (✅ ранее), завтра/неделя, две системы настроек, инвалидация кэша | Достоверные уведомления | ❌ открыто |
| **6. Чистка** | Мёртвый код (`admin_panel.py` — слияние, `UserSchool`), дублирование, `print`→logging (✅ 11.09 все), `RotatingFileHandler` | Поддерживаемость | 🟡 частично |
| **7. Тесты и инструменты** | pytest, ruff, mypy, CI | Регрессии | ❌ открыто |

> **11.09.2026**: выполнен этап 2 целиком (в рамках текущей архитектуры) и часть этапа 1 (п.8), этапа 3 (Message is not modified — 3 файла) и этапа 6 (FileDB: дубли/логирование; /week и /school зарегистрированы; __init__.py во всех пакетах). Добавлен smoke-тест импортов и unit-проверки `delete_one`/`log_update_activity`/`clear_user_state` (временно, вне репозитория — нужен pytest, см. этап 7).

---

## 7. Мелочи из проверки окружения (03.09.2026)

- `venv/` в каталоге проекта — добавить `.gitignore` (venv, `data/`, `logs/`, `cache/`, `__pycache__`), зависимости зафиксировать в `requirements.txt`.
- В `requirements.txt` закомментированные мёртвые зависимости — удалить.
- Школа №133: сервер Nikasoft отдаёт экспорт от 25.05.2026 — это не баг бота (проверено напрямую); админ-панель при этом пишет «✅ Обновлено 2/2 школ» — стоит считать «обновлёнными» только школы со свежими данными.
- Статус старше 24 ч должен показывать 🔴 «Устарело» (`status_service.py:68`), в админке выводится ⚠️ — привести к единому виду.