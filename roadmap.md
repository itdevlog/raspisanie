# Roadmap — что осталось сделать

> То, что уже сделано, перенесено в [CHANGELOG.md](CHANGELOG.md).
> Аудит от 03.09.2026. Стек: python-telegram-bot 20.7, requests, pytz, JSON-БД.
> Приоритеты: 🔴 P0 — падения/потеря данных, 🟠 P1 — некорректное поведение, 🟡 P2 — качество и поддержка.

---

## 1. 🔴 Критические баги (P0)

### Падения в обработчиках

| # | Место | Проблема | Исправление |
|---|-------|----------|-------------|
| 9 | `handlers/teachers/teacher_menu.py:156,267`, `handlers/rooms/room_schedule.py:158,274` | `Message is not modified` — повторное нажатие «Обновить»/«Назад» в этих файлах ещё уходит в error handler | Применить `safe_edit_message` (есть в `messaging`, применён в `class_callbacks`/`school_info`/`main_menu`, тут ещё нет) |

---

## 2. 🟠 Серьёзные баги (P1)

### Telegram-протокол

- **Обрезка Markdown посередине** — `admin_panel.py:278-279`, `admin_callbacks.py:278-279` (`text[:4000]`) ломает `*...*`/`` `...` `` → `Can't parse entities`. Обрезать по границе строки.
- **Неполное экранирование** — `base_schedule_service.py`: не экранируются `[`, `]`, `(`, `)` для legacy Markdown → сообщение не уйдёт. → ✅ **исправлено 11.09**: единый хелпер `BaseScheduleService._escape_markdown` (экранирует `_ * [ ] ( ) \``), применён во всех 6 местах.
- **Экранирование до бизнес-логики** — `room_service.py`/`teacher_service.py`: `class_name` экранируется и сравнивается с «чистыми» именами → замены для учителей/кабинетов не находились. → ✅ **исправлено 11.09**: для `apply_exchanges_to_schedule` и сохранения в уроке используется чистое имя класса; экранирование осталось только для отображения.
- **`await query.answer()` без проверки** — `room_schedule.py:365`, `teacher_menu.py:351` при вызове из текстового ввода (`query=None`). → ✅ устранено: неусловных `query.answer()`/`edit_message_text` по `query=None`-пути (текстовый ввод) уже нет — `handle_*_selection` вызываются только из callback'ов, а текстовый путь идёт через `handle_*_search_results` с ветвлением `if query`.

### Логика состояния

- **Сохранение списка до сортировки по ссылке** — `room_schedule.py:201-206`, `teacher_menu.py:198-203`: в `state_service` кладётся ссылка, затем `sort()` мутирует её. Скрытый рассинхрон индексов кнопок. → ✅ фактически устранено: в текущем коде и `teacher_menu`, и `room_schedule` сортируют **до** `set_user_list` (teachers: 344→369, rooms: 204→218, 349→374).
- **TTL кэша ломает кнопки** — списки в `CacheService(ttl=600)` живут 10 минут, индексные кнопки потом «мёртвые» навсегда. Хранить в `context.user_data` или имена в callback_data. → ✅ **исправлено 11.09**: `state_service` переведён на отдельный долгий кэш (24 ч), который не инвалидируется вместе с расписанием; списки учителей/кабинетов/классов и их индексные кнопки больше не «протухают» через 10 минут.

### Замены и уведомления

- **Экранирование до бизнес-логики** — `room_service.py:95-100`, `teacher_service.py:95-100`: `class_name` экранируется (`replace('*','\\*')…`) и затем передаётся в `apply_exchanges_to_schedule`, где `_find_class_id` сравнивает его с «чистыми» именами → замены для расписаний учителей/кабинетов **не находятся**. → ✅ **исправлено 11.09**: в `teacher_service`/`room_service` для поиска замен и хранения имени используется чистое `class_name`.
- **`ExchangeService` создаётся в цикле** — `exchange_detector.py:102`: на каждую школу каждый тик.
- **`ExchangeService` создаётся в цикле** — `exchange_detector.py:102`: на каждую школу каждый тик.

### Инфраструктура

- **`remove_school` оставляет висячий `current_school`** — `database/models/user_school.py:21-31`; сам класс `UserSchool` нигде не используется — удалить или подключить. → ✅ **исправлено 11.09**: `database/models/user_school.py` удалён — модель нигде не использовалась (логика школы/класса — в `UserService`); `remove_school`/висячий `current_school` ушли вместе с ней.

### Мёртвый код (удалить)

- ✅ **исправлено 11.09**: удалены мёртвые `callback_handler.py::handle_school_info` (дублировал `school_info_handler`), флаг `waiting_for_teacher` (никогда не устанавливался) из `class_schedule.py`/`messaging::clear_search_flags`, заглушка `notification_service::_get_user_service` и закомментированный блок `notification_service.py`, поле `['order']` из конфига школ; исправлено случайное дублирование `callback_handler.py` (434→780→434 строки). Осталось: проверить недостижимые ветки `navigation_callbacks.py` (сместились с исходного аудита).

---

## 3. 🟡 Улучшения (P2)

### Дублирование кода (главная проблема поддержки)

1. **`teacher_menu.py` ↔ `room_schedule.py` — ~90% совпадений** (423 и 437 строк): меню, поиск, пагинация. → ✅ **исправлено 11.09**: вынесено в `handlers/common/entity_menu.py::EntityMenuHandler` (параметризуется `EntityConfig`); `teacher_menu.py`/`room_schedule.py` стали тонкими обёртками (~60 строк каждая) с прежней публичной API.
2. **Главное меню** — `start.py:44-104` ↔ `main_menu.py:31-101`. → ✅ **исправлено 11.09**: вынесено в `handlers/common/menu_builder.py` (`build_main_menu_keyboard`/`build_main_menu_text`/`resolve_school_name`); `start.py` и `main_menu.py` используют общий построитель.
3. **Текст помощи** — `start.py:110-146` ↔ `callback_handler.py:339-378` (уже расходятся по содержанию). → ✅ **исправлено 11.09**: единые `HELP_TEXT` и `build_help_keyboard()` в `menu_builder.py`; оба хендлера используют их.
4. **Поиск школы по id** — 6 мест. → ✅ **исправлено 11.09**: `config/schools.py::get_school_by_id()`.
5. **Пагинация** — реализация унифицирована в `EntityMenuHandler` (teacher/room) и `handle_show_all_classes`; `messaging::paginate` существует как общий хелпер. Осталось: подключить в оставшихся местах, если такие найдутся.
6. **Проверки `if not user_service or not schools_data`** — 20+ повторов. Декоратор `@requires_school`.
7. **Проверка админа** — 4 разных способа. → ✅ **исправлено 11.09**: единый `Config.is_admin()`, подключён в `admin_panel`, `admin_callbacks`, `settings`, `bot`.
8. **Часовой пояс** — `Asia/Yekaterinburg` в 5 местах, везде назван `moscow_tz` (реально UTC+5). → ✅ **исправлено 11.09**: конфиг `TIMEZONE` (`.env`, по умолчанию `Asia/Yekaterinburg`); единый хелпер `config.get_timezone()`, применён в 6 сервисах.

### UX

- Ошибки показывают `str(e)` пользователю — утекают внутренности. → ✅ **исправлено 11.09**: `messaging::log_user_error` логирует реальное исключение и возвращает общее сообщение; применён в `class_callbacks`, `week_command`, `callback_handler`, `admin_callbacks`. `str(e)` пользователю больше нигде не показывается.
- «Список устарел» оставляет мёртвую клавиатуру — перерисовывать актуальный список вместо тоста.
- Нет кнопки «Обновить» в клавиатурах учителей/кабинетов (в классах есть).
- Ввод поиска без ограничения длины и кнопки «Отмена» (только «Назад», не сбрасывающая флаг).
- Прогресс для долгих админ-операций: `ChatAction.TYPING` или статус по школам.

### Данные и производительность

- **O(N²) в подборе получателей** — полный проход по всем пользователям на каждый класс. → ✅ **исправлено 11.09**: `NotificationService` строит индекс `(school_id, class_lower) → [user_id]` одним проходом и кэширует его на школу (`_build_user_class_index`/`get_users_by_class_indexed`), сброс — в `_perform_update`; читает `school_classes` без per-user `find_one`.
- **`FileDB` перезаписывает весь JSON на каждую операцию** (`file_db.py:72,80,96`) — dirty-флаг + отложенная запись, или перейти на `sqlite3` (stdlib).
- **Кэш уведомлений** — `notification_service.py:337-344`: «последние 100» через `list(set)[-100:]` — порядок не гарантирован; обещанной очистки по 24 ч нет. Хранить `Dict[key, timestamp]`.
- **Дублирование запросов в `data_loader`** — вложенные ретраи дают до 9 запросов на школу; нет ETag/If-Modified-Since; `except Exception` ловит и `JSONDecodeError` (ретрай бессмысленен); парсинг по `'var NIKA='` хрупок; `Session` не закрывается.
- **`CacheService`** — нет лимита размера и потокобезопасности; `get_stats` сериализует весь кэш в строки.

### Логирование и безопасность

- `ADMIN_LOG_FILE` объявлен в конфиге, но нигде не использовался. → ✅ **исправлено 11.09**: `bot.py::setup_logging` создаёт отдельный ротируемый `admin_panel`-логгер в `ADMIN_LOG_FILE` (действия админов пишутся туда).

---

## 4. Архитектурные рекомендации

1. **`JobQueue` вместо ручного потока** — заменить `threading.Thread` + `run_coroutine_threadsafe` + приватный `_loop` на `application.job_queue.run_repeating(...)`, а блокирующий `DataLoader` — на `asyncio.to_thread`.
2. **`ConversationHandler` вместо FSM-флагов** — флаги `waiting_for_*` в `user_data` — источник «залипаний». Регистрировать до общего `MessageHandler(TEXT & ~COMMAND)` в `bot.py`.
3. **Слой данных** — `NotificationService` лезет в `user_service.db` напрямую (`notification_service.py`). Завести `UserRepository` с методами вроде `get_users_by_class(school_id, class_name)`.
4. **Форматирование/экранирование** — размыто по 4 файлам. Вынести в `render.py`, перейти на `HTML` parse_mode.
5. **Конфигурация** — `@dataclass(frozen=True)` c `from_env()` и валидацией; `SCHOOLS_CONFIG` в JSON/YAML, чтобы добавление школы не требовало правки кода.
6. **Типизация** — `TypedDict`/dataclass для структуры school_data; `mypy` для `services/`; исправить аннотации.
7. **Структура handlers** — регистрировать `CallbackRouter` напрямую, builders клавиатур вынести в `handlers/keyboards.py`; зависимости прокидывать одним `Services`-объектом вместо повторов `context.bot_data.get(...)`.

---

## 5. Тесты

Есть базовый pytest (см. `tests/`, CHANGELOG `8782ee5`). Добавить:

Приоритетные юнит-тесты (чистые функции, без Telegram):

- `ExchangeService.apply_exchanges_to_schedule` — тест «исходные данные не изменились»;
- `ExchangeDetector._compare_class_exchanges` с раунд-трипом через `json.dumps/loads`;
- `FileDB` — битый файл, upsert, параллельная запись;
- `_find_class_id` — однозначность матчинга классов;
- роутинг callback-префиксов `_get_handler_key`;
- генератор длинного недельного расписания → проверка нарезки ≤4096.

Интеграционные (pytest-asyncio + мок): ввод несуществующего класса текстом, клик по результату поиска, двойное нажатие «Обновить», `admin_force_update`.

Инструменты: ruff, mypy, CI.

---

## 6. Мелочи из проверки окружения (03.09.2026)

- Школа №133: сервер Nikasoft отдаёт экспорт от 25.05.2026 — это не баг бота (проверено напрямую); админ-панель при этом пишет «✅ Обновлено 2/2 школ» — стоит считать «обновлёнными» только школы со свежими данными.
- Статус старше 24 ч должен показывать 🔴 «Устарело» (`status_service.py:68`), в админке выводится ⚠️ — привести к единому виду.
