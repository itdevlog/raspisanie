# Changelog

История исправлений Telegram-бота расписания. Хронологический порядок (новое — внизу, как в git-логе).
«Что осталось сделать» — см. [roadmap.md](roadmap.md).

## 11.09.2026

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
