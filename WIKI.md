# 📚 Wiki: Telegram-бот расписания занятий

> Дата создания: 2026-09-10, последнее обновление: 2026-09-11 (после большого рефакторинга)
> Назначение: единая точка знаний о проекте. Если что-то здесь не описано — это баг документации, дополняй.

---

## 1. Что это за проект

Telegram-бот для просмотра школьного расписания и автоматических уведомлений о заменах.

- **Источник данных**: система расписания [Nikasoft (Ника-Люкс)](https://raspisanie.nikasoft.ru).
- **Фреймворк**: `python-telegram-bot` v20.7 (асинхронный).
- **База данных**: локальный JSON-файл (`data/database.json`) через обёртку `FileDB`.
- **Язык**: Python 3.10+.
- **Поддерживаемые школы**: МАОУ СОШ №133, МАОУ СОШ №181 (г. Екатеринбург).

---

## 2. Высокоуровневая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         Telegram API                            │
└─────────────────────────────────────────────────────────────────┘
                                ▲
                                │
┌─────────────────────────────────────────────────────────────────┐
│  bot.py  ──  Application (python-telegram-bot)                    │
│  • регистрация обработчиков                                     │
│  • хранилище сервисов в application.bot_data                      │
│  • запуск фонового обновления + polling                         │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   handlers/   │     │    services/     │     │     core/       │
│  команды и    │     │ бизнес-логика    │     │ загрузка данных │
│  callback'и   │     │                  │     │ и фоновые задачи│
└───────────────┘     └──────────────────┘     └─────────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
                    ┌──────────────────┐
                    │  config/ + data/ │
                    │  .env, JSON БД,  │
                    │  кэш-файлы       │
                    └──────────────────┘
```

### 2.1 Главные потоки выполнения

1. **Пользовательский поток**: Telegram → `handlers/` → `services/` → ответ пользователю.
2. **Фоновый поток**: `core/background_updater.py` раз в `UPDATE_INTERVAL` (по умолчанию 3600 c = 1 ч, читается из конфига) загружает свежие данные и проверяет замены.
3. **Поток данных**: `core/data_loader.py` → `bot_data['schools_data']` → все `services` работают с этим словарём.

> ✅ 11.09: интервал теперь берётся из `Config.UPDATE_INTERVAL`, а не хардкодится.

---

## 3. Структура проекта

| Путь | Назначение |
|------|-----------|
| [bot.py](bot.py) | Точка входа. Создаёт приложение, инициализирует сервисы, запускает polling. |
| [config/config.py](config/config.py) | Чтение `.env`, настройки логирования, путей, админов. |
| [config/schools.py](config/schools.py) | Список поддерживаемых школ: `id`, имя, URL check-страницы, URL статики. |
| [core/data_loader.py](core/data_loader.py) | Скачивает JS-файл расписания с Nikasoft и парсит его в Python-словарь. |
| [core/background_updater.py](core/background_updater.py) | Фоновый поток обновления данных и детекции замен. |
| [database/file_db.py](database/file_db.py) | Простая JSON-обёртка «как MongoDB»: коллекции, `find`, `insert`, `update`. |
| [services/base_schedule_service.py](services/base_schedule_service.py) | Базовый класс с общей логикой форматирования расписания и единым экранированием `_escape_markdown`. |
| [services/schedule_service.py](services/schedule_service.py) | Расписание классов: сегодня, завтра, неделя. |
| [services/teacher_service.py](services/teacher_service.py) | Расписание преподавателей. |
| [services/room_service.py](services/room_service.py) | Расписание кабинетов. |
| [services/exchange_service.py](services/exchange_service.py) | Применяет замены к расписанию урока. |
| [services/exchange_detector.py](services/exchange_detector.py) | Обнаруживает *новые* замены, сравнивая текущее состояние с предыдущим. |
| [services/notification_service.py](services/notification_service.py) | Отправляет уведомления о заменах пользователям и админам; `_is_quiet_hours` (тихие часы), анти-флуд в `_send_message`; `notify_subscribers` для подписок. |
| [services/subscription_service.py](services/subscription_service.py) | Подписки на преподавателей/кабинеты (коллекция `subscriptions`): `subscribe`/`unsubscribe`/`is_subscribed`/`get_subscriptions`/`get_subscribers`. |
| [services/reminder_service.py](services/reminder_service.py) | Чистая логика напоминаний об уроках: `get_due_reminders`/`get_due_reminders_detailed` по времени `LESSON_TIMES`; отправляет `BackgroundUpdater._reminder_loop`. |
| [services/digest_service.py](services/digest_service.py) | Чистая логика утреннего дайджеста: за 60 мин до первого урока (`DIGEST_OFFSET_MINUTES`), окно догона 15 мин, дедуп `digest:{user}:{school}:{class}:{дата}`; текст — расписание дня с заменами. Отправляет `BackgroundUpdater._send_digests` из того же минутного цикла. |
| [services/user_service.py](services/user_service.py) | Работа с пользователями: школа, класс, настройки уведомлений. |
| [services/user_preferences.py](services/user_preferences.py) | Хранилище настроек поверх `FileDB` (коллекция `user_preferences`): `update_notifications`, `lesson_reminders`, `daily_digest`, `quiet_hours`. Используется в `background_updater` и `settings.py`. Настройки замен (exchange) здесь не хранятся — их единственный источник `UserService`. |
| [services/cache_service.py](services/cache_service.py) | In-memory кэш с TTL, потокобезопасный (`RLock`), с лимитом размера `max_entries` (вытеснение самых старых) и честной статистикой. |
| [handlers/common/entity_menu.py](handlers/common/entity_menu.py) | Параметризованный `EntityMenuHandler` — общая логика меню/поиска/пагинации для учителей и кабинетов. |
| [handlers/common/menu_builder.py](handlers/common/menu_builder.py) | Единые построители главного меню (`build_main_menu_keyboard`/`text`) и справки (`HELP_TEXT`). |
| [handlers/common/messaging.py](handlers/common/messaging.py) | Разбивка длинных сообщений ≤4096, `safe_edit_message`, `log_user_error`, `clear_search_flags`, `paginate`. |
| [handlers/common/requires_school.py](handlers/common/requires_school.py) | Декоратор `@requires_school` — убирает дублирующиеся проверки сервисов/школы. |
| [services/status_service.py](services/status_service.py) | Проверяет актуальность данных по времени экспорта из Nikasoft. |
| [services/state_service.py](services/state_service.py) | Временное хранилище состояний пользователей (FSM-подобное). |
| [handlers/start.py](handlers/start.py) | `/start`, `/help` и `/cancel`. |
| [handlers/common/main_menu.py](handlers/common/main_menu.py) | Отрисовка главного меню. |
| [handlers/common/callback_handler.py](handlers/common/callback_handler.py) | **Активный** callback-роутер. Делегирует в `CallbackRouter` из `handlers/callbacks/__init__.py`. Регистрируется в `bot.py` через `CallbackQueryHandler(callback_handler)`. `show_class_selection` работает и из callback, и из текстового ввода. |
| [handlers/callbacks/__init__.py](handlers/callbacks/__init__.py) | Реализация `CallbackRouter` и 5 специализированных обработчиков (`ClassCallbackHandler`, `TeacherCallbackHandler`, `RoomCallbackHandler`, `AdminCallbackHandler`, `NavigationCallbackHandler`). |
| [handlers/callbacks/class_callbacks.py](handlers/callbacks/class_callbacks.py) | Callback'и классов. |
| [handlers/callbacks/teacher_callbacks.py](handlers/callbacks/teacher_callbacks.py) | Callback'и учителей. |
| [handlers/callbacks/room_callbacks.py](handlers/callbacks/room_callbacks.py) | Callback'и кабинетов. |
| [handlers/callbacks/navigation_callbacks.py](handlers/callbacks/navigation_callbacks.py) | Навигация: главное меню, смена класса/школы, настройки. |
| [handlers/callbacks/admin_callbacks.py](handlers/callbacks/admin_callbacks.py) | Админ-панель и callback'и администратора. |
| [handlers/admin/admin_panel.py](handlers/admin/admin_panel.py) | Только команды `/admin` и `/stats` (`admin_panel_handler`, `setup_admin_handlers`). Делегируют в единую реализацию `AdminCallbackHandler`: `/admin` → `show_panel`, `/stats` → `_show_statistics`. Дублирующие построители панели удалены 11.09. |
| [handlers/common/class_schedule.py](handlers/common/class_schedule.py) | Обработка текстового ввода класса. |
| [handlers/common/week_command.py](handlers/common/week_command.py) | `/week <класс>` — недельное расписание. **Зарегистрирована** в `bot.py` с 11.09.2026. |
| [handlers/common/school_info.py](handlers/common/school_info.py) | Информация о школе. Команда `/school` зарегистрирована в `bot.py` с 11.09.2026. |
| [handlers/common/status.py](handlers/common/status.py) | Команда `/status`. |
| [handlers/common/settings.py](handlers/common/settings.py) | Команда `/settings`. |
| [handlers/schools/school_selection.py](handlers/schools/school_selection.py) | Выбор школы. |
| [handlers/teachers/teacher_menu.py](handlers/teachers/teacher_menu.py) | Тонкая обёртка над `EntityMenuHandler` (меню и расписание учителей). |
| [handlers/rooms/room_schedule.py](handlers/rooms/room_schedule.py) | Тонкая обёртка над `EntityMenuHandler` (меню и расписание кабинетов). |
| [logs/](logs/) | Лог-файлы (ротируемые): `bot.log`, `admin.log`, stdout. |
| [data/](data/) | JSON база и кэш-файлы. |
| [cache/](cache/) | Зарезервировано; `CACHE_PATH` объявлен в конфиге, но не используется сервисами. |

---

## 4. Как бот запускается

Последовательность в [bot.py](bot.py):

1. `Config()` читает `.env`; если `TELEGRAM_TOKEN` не задан — понятная ошибка вместо падения внутри PTB.
2. Создаётся `Application.builder().token(...).post_init(...).connect_timeout(30)...build()`.
3. `setup_services()` создаёт сервисы и кладёт их в `application.bot_data`:
   - `user_service`
   - `db`
   - `cache_service`
   - `notification_service`
   - `state_service`
   - `exchange_detector`
   - `schools_config`
4. `load_schools_data()` вызывает `DataLoader.load_all_schools_data()` — синхронно загружает данные всех школ.
5. `setup_handlers()` регистрирует обработчики команд и callback. Команды: `/start`, `/help`, `/status`, `/settings`, `/week <класс>`, `/school`, `/cancel`, `/admin`, `/stats`, `/check_exchanges`.
6. `background_updater.start_periodic_updates()` запускает фоновую задачу через `post_init` (после старта event loop, до polling).
7. `application.run_polling()` блокирует основной поток и начинает слушать Telegram.

> ⚠️ **Инициализация**: `BackgroundUpdater` создаётся в `bot.py` **до** построения `Application` (с `application=None`); ссылка на `application` устанавливается позже и дублируется в `bot_data['background_updater']`. До этого момента использование `self.application` в `__init__` упало бы с `AttributeError`.

> ✅ **Интервал из конфига**: `BackgroundUpdater.update_interval = Config.UPDATE_INTERVAL` (по умолчанию 3600 c = 1 ч). Жёсткий `1800` убран (см. §13).

> ✅ **Фоновое обновление стартует из `post_init`** (`.post_init(self._post_init)`), т.е. гарантированно внутри запущенного event loop — `asyncio.create_task` здесь корректен, синхронные HTTP-запросы оффлоадятся через `asyncio.to_thread`.

### 4.1 Что находится в `application.bot_data`

Это общее хранилище данных приложения, доступное из любого обработчика через `context.bot_data`.

| Ключ | Что хранится | Кто использует |
|------|-------------|----------------|
| `user_service` | Работа с пользователями | Все handlers |
| `db` | `FileDB` (потокобезопасный, атомарная запись, `delete_one` удаляет ровно один документ) | `user_service`, `admin_callbacks` |
| `config` | Объект `Config` (`.env`-настройки) | `notification_service`, `settings` |
| `cache_service` | In-memory кэш TTL | `schedule_service` |
| `notification_service` | Отправка уведомлений | `background_updater`, `admin_callbacks` |
| `subscription_service` | Подписки на преподавателей/кабинеты | `entity_menu`, `settings`, `background_updater` |
| `schools_config` | `SCHOOLS_CONFIG` | Везде |
| `state_service` | Временные состояния (на отдельном долгом кэше, 24 ч) — списки для пагинации/индексных кнопок не протухают за 10 мин | `class_schedule`, `teacher_menu`, `room_schedule` |
| `exchange_detector` | `ExchangeDetector` (детекция замен) | `background_updater` |
| `background_updater` | `BackgroundUpdater` | `admin_callbacks`, `force_check_exchanges` |
| `schools_data` | Распарсенные данные школ | Все сервисы расписания |

---

## 5. Как загружаются данные расписания

### 5.1 Источник

У каждой школы в [config/schools.py](config/schools.py) есть:

- `check_url` — страница с именем актуального JS-файла, например `55812556.html`.
- `base_url` — путь к статическим файлам, например `https://raspisanie.nikasoft.ru/static/public/`.

### 5.2 Алгоритм загрузки

Реализован в [core/data_loader.py](core/data_loader.py):

1. `get_current_filename(check_url)` — GET-запрос на check-страницу, регуляркой ищет `\d+_\d+\.js` (например, `124_20250910.js`).
2. `download_schedule_data(base_url, filename)` — скачивает JS-файл.
3. Парсинг: ищет подстроку `var NIKA=`, берёт всё после неё, отрезает `;` в конце, прогоняет через `json.loads()`.
4. Результат — гигантский словарь с ключами: `CLASSES`, `TEACHERS`, `ROOMS`, `SUBJECTS`, `CLASS_SCHEDULE`, `CLASS_EXCHANGE`, `PERIODS`, `LESSON_TIMES`, `EXPORT_DATE`, `EXPORT_TIME` и др.

### 5.3 Фоновое обновление

[core/background_updater.py](core/background_updater.py):

- Интервал: `Config.UPDATE_INTERVAL` (по умолчанию 3600 c = 1 ч).
- Работает внутри основного event loop (`asyncio.create_task`), а не в отдельном `threading.Thread`.
- Засыпает через `asyncio.sleep`, не блокируя polling.
- Синхронные HTTP-запросы `requests` оффлоадятся в отдельный поток через `asyncio.to_thread(...)`.
- Мержит свежие данные поверх last-known-good (`_merge_schools_data`), чтобы школа, чья загрузка не удалась, не исчезала до следующего цикла; замена `bot_data['schools_data']` сериализована `asyncio.Lock` (повторный запуск сообщает о пропуске).
- После замены данных единый хук `_on_data_replaced()` очищает кэш расписания и сбрасывает индекс уведомлений; тот же хук переиспользуется ручным refresh в админке.
- Параллельно с часовым циклом обновления работает минутный цикл `_reminder_loop`: `_send_reminders` (напоминания об уроках) и `_send_digests` (утренний дайджест). Оба дедуплицируются и уважают тихие часы; кэши — `data/sent_reminders.json` и `data/sent_digests.json`.

> ✅ **Исправлено 11.09.2026**: `self.moscow_tz` инициализирован в `BackgroundUpdater.__init__` (`core/background_updater.py`) — `log_update_activity()` работает, `updatelog.txt` заполняется. Дополнительно: дублирующийся `stop()` удалён; фейковый контекст `context = ContextTypes.DEFAULT_TYPE` (мутация класса PTB) заменён на `SimpleNamespace` в `_make_context()`; синхронные HTTP-запросы `requests` во всех async-путях (`_perform_update` + админ-callback'и) оффлоадятся через `asyncio.to_thread(...)`. В Фазе 2 добавлены merge частичной загрузки, `asyncio.Lock` на `_perform_update` и единый `_on_data_replaced()`.

---

## 6. Структура данных Nikasoft

После парсинга данные школы — это словарь. Основные ключи:

| Ключ | Содержимое | Пример |
|------|-----------|--------|
| `SCHOOL_NAME` | Название школы | `"МАОУ СОШ №133"` |
| `CLASSES` | `{class_id: class_name}` | `{"1001": "5А", "1002": "5Б"}` |
| `TEACHERS` | `{teacher_id: teacher_name}` | `{"2001": "Иванова А.А."}` |
| `ROOMS` | `{room_id: room_name}` | `{"3001": "201"}` |
| `SUBJECTS` | `{subject_id: subject_name}` | `{"4001": "Математика"}` |
| `PERIODS` | `{period_id: {b: start_date, e: end_date}}` | Учебные периоды |
| `LESSON_TIMES` | `{lesson_num: [start, end]}` | `{"1": ["8:30", "9:15"]}` |
| `DAY_NAMES` | Список дней недели | `["Понедельник", ...]` |
| `CLASS_SCHEDULE` | `{period_id: {class_id: {key: lesson_data}}}` | Основное расписание |
| `CLASS_EXCHANGE` | `{class_id: {date_str: {lesson_num: exchange}}}` | Замены |
| `EXPORT_DATE` | Дата экспорта | `"10.09.2026"` |
| `EXPORT_TIME` | Время экспорта | `"08:15:00"` |

### 6.1 Формат урока

```python
{
    's': ['subject_id', ...],   # предметы
    't': ['teacher_id', ...],   # преподаватели
    'r': ['room_id', ...]       # кабинеты
}
```

### 6.2 Формат замены

```python
{
    's': 'subject_id',   # новый предмет
    't': 'teacher_id',   # новый учитель
    'r': 'room_id',      # новый кабинет
    's': 'F'             # урок отменён
}
```

---

## 7. Как строится расписание класса

### 7.1 Поток вызовов

```
/start или callback "class_today_5А"
  → handlers/callbacks/class_callbacks.py
    → services/schedule_service.py
      → BaseScheduleService._format_schedule_response()
```

### 7.2 Алгоритм

В [services/schedule_service.py](services/schedule_service.py):

1. По имени класса находится `class_id` (`_find_class_id`).
2. По дате находится `period_id` (`_get_period_for_date`).
3. Определяется день недели (`isoweekday()`, 1=Пн ... 7=Вс).
4. Если суббота/воскресенье — выводится "Выходной день".
5. Из `CLASS_SCHEDULE[period_id][class_id]` собираются уроки.
6. Ключ урока формируется как `f"{day_num}{lesson_num:02d}"` (например, `"401"` = день 4, урок 1, `"410"` = день 4, урок 10).
7. Данные урока копируются, чтобы замены не мутировали исходный `school_data`.
8. К полученному расписанию применяются замены через `exchange_service.apply_exchanges_to_schedule()`.
9. Результат форматируется в Markdown и отправляется пользователю.

### 7.3 Расписание на неделю

`_get_week_schedule()` строит расписание для Пн–Пт и объединяет в одно сообщение. С Фазы 4 принимает `week_offset` (0 — текущая неделя), т.е. умеет строить соседние недели; пользовательской команды/кнопки под это нет. В `BaseScheduleService` есть helper `get_next_lesson` — возвращает ближайший (или текущий, если он последний) урок по `LESSON_TIMES`; сейчас используется только тестами.

---

## 8. Как работают замены

### 8.1 Применение замен

[services/exchange_service.py](services/exchange_service.py):

1. По имени класса находится `class_id`.
2. По дате `date_str = "dd.mm.YYYY"` берутся замены: `CLASS_EXCHANGE[class_id][date_str]`.
3. Для каждого урока проверяется наличие замены по номеру урока.
4. Если `s == 'F'` — урок помечается `is_cancelled=True`.
5. Иначе перезаписываются поля `s`, `t`, `r` и ставится флаг `has_exchange=True`.

> ✅ Исправлено: `ExchangeService._apply_exchange` делает глубокую копию `data`, поэтому `school_data['CLASS_SCHEDULE']` не мутируется. Аналогично в `ScheduleService._format_schedule_response`, `TeacherService` и `RoomService` данные урока копируются (`copy.deepcopy` либо ручная копия списков) перед применением замен, чтобы замены не мутировали общий `school_data`.

### 8.2 Детекция новых замен

[services/exchange_detector.py](services/exchange_detector.py):

1. Хранит `previous_schedules` — предыдущее состояние замен с разбивкой по школе И дате: `{school_id: {date_str: {class: {...}}}}`. Разделение по датам обязательно: фоновое обновление проверяет и «сегодня», и «завтра», и без него baseline одной даты затирал бы другую.
2. Периодически (из фонового обновления) вызывается `detect_exchanges(school_id, school_data, date, persist=True)`. Фоновый цикл вызывает его с `persist=False` через `asyncio.to_thread` и один раз за цикл делает общий `save_cache()`.
3. Строит текущие замены для всех классов (`_get_current_exchanges`).
4. Сравнивает с предыдущими за ту же дату (`_compare_class_exchanges`).
5. Найденные **новые** замены возвращаются для отправки уведомлений.
6. Текущее состояние сохраняется в `data/exchange_cache.json` атомарно (temp + `os.replace`); даты старше 3 суток удаляются. Старый (плоский) формат кэша при загрузке сбрасывается.

> ✅ Исправлено: ключи замен хранятся только как строки (`str(int(lesson_num_str))`). Это устраняет рассогласование `int`/`str` после JSON-сериализации кэша и предотвращает дублирование уведомлений. В финальном payload уведомления `lesson_num` преобразуется обратно в `int`.

### 8.3 Отправка уведомлений

[services/notification_service.py](services/notification_service.py):

1. Берёт получателей класса из индекса `(school_id, класс) → [user_id]`, построенного одним проходом по пользователям; настройки уведомлений читаются тем же проходом в `_settings_for_school`, поэтому `get_users_for_exchange` сразу отдаёт только тех, у кого уведомления для школы включены (без `find_one` на каждого получателя).
2. Формирует текст уведомления (динамические значения экранируются общим `services/text_utils.escape_markdown`).
3. Создаёт уникальный ключ (`school_id + class + date + hash замен`) и проверяет, не отправлялось ли уже.
4. Отправляет сообщения через `_send_message`, который пережидает Telegram `RetryAfter` (429) и не дропает сообщения при анти-флуд-паузе; между отправками пауза `asyncio.sleep(0.05)` против flood-лимитов. Помечает ключ отправленным и сохраняет в `data/notifications_cache.json`.
5. Формат строки замены — «до → после» с временем урока: `🔄 6. 13:00-13:45 • Математика (Ищенко К.А., каб. 301) → Биология (Усольцева А.Д., каб. 4022)`; отмена — `❌ N. время • Предмет (Фамилия И.О., каб.) — *ОТМЕНЕНО*`; снятие замены — `↩️ N. … — *замена снята*`. Исходный урок детектор берёт из базового расписания (`_get_original_lesson`: `CLASS_SCHEDULE[period][class][день+урок]`), время — из `LESSON_TIMES`; ФИО сокращаются до «Фамилия И.О.» хелпером `services/text_utils.short_name` (скрывает обрезанные источником ФИО). Если базового урока нет — деградация к заглушке «Урок N» без деталей.
6. Тихие часы: при включённом окне у пользователя уведомления не отправляются (`_is_quiet_hours`). При заменах у преподавателя/кабинета дополнительно вызывается `notify_subscribers`, который рассылает текст всем подписчикам сущности.

> ✅ Исправлено: уведомление помечается отправленным и кэш сохраняется только при `sent_count > 0`. Если все отправки не удались, ключ остаётся неотмеченным и повторная попытка будет предпринята позже.

---

## 9. Пользовательские данные

### 9.1 Структура записи пользователя

Хранится в `data/database.json`, коллекция `users`:

```json
{
  "user_id": 123456789,
  "current_school": "school_133",
  "school_classes": {
    "school_133": "5А",
    "school_181": "7Б"
  },
  "notification_settings": {
    "school_133": true,
    "school_181": false
  },
  "created_at": "2026-09-10T10:00:00",
  "updated_at": "2026-09-10T12:00:00"
}
```

### 9.2 Ключевые операции

- `get_user_school(user_id)` — текущая школа.
- `set_user_school(user_id, school_id)` — сменить школу.
- `get_user_class(user_id, school_id)` — класс для школы.
- `set_user_class(user_id, class_name, school_id)` — установить класс.
- `clear_user_class(user_id, school_id=None)` — очистить класс для указанной школы.
- `get_current_class(user_id)` — класс для текущей школы пользователя (сокращение для `get_user_class` + `get_user_school`).
- `get_user_data(user_id)` — все данные пользователя из БД.
- `get_users_with_classes()` — список всех пользователей, у которых задан хотя бы один класс (используется в админ-статистике).
- `get_user_notification_settings(user_id, school_id)` — включены ли уведомления.
- `set_user_notification_settings(user_id, enabled, school_id)` — настройка уведомлений.

---

## 10. Состояния пользователей

[services/state_service.py](services/state_service.py) — временное хранилище в памяти, похожее на FSM.

Используется для:
- ожидания ввода класса текстом,
- ожидания поиска учителя/кабинета,
- сохранения промежуточных списков при пагинации.

> ⚠️ Состояния живут только в памяти. После рестарта бота они теряются.

---

## 11. Callback-роутинг

Все inline-кнопки проходят через [handlers/callbacks/__init__.py](handlers/callbacks/__init__.py) — `CallbackRouter`.

Префикс callback_data → обработчик (на основе `handlers/callbacks/__init__.py:50-79`):

| Префикс | Обработчик | Назначение |
|---------|-----------|------------|
| `class_digit_` | `NavigationCallbackHandler` | Выбор цифры класса при наборе |
| `class_` | `ClassCallbackHandler` | Расписание класса (`class_today_`, `class_tomorrow_`, `class_week_` и т. п.) |
| `teacher_` | `TeacherCallbackHandler` | Учителя (поиск, расписание, навигация по дням) |
| `room_` | `RoomCallbackHandler` | Кабинеты (поиск, расписание, навигация по дням) |
| `admin_` | `AdminCallbackHandler` | Админ-панель и её подменю |
| `menu_` | `NavigationCallbackHandler` | Меню и настройки |
| `school_` | `NavigationCallbackHandler` | Выбор школы |
| `show_all_` | `NavigationCallbackHandler` | Показать полный список (учителя/кабинеты без поиска) |
| `clear_digit_` | `NavigationCallbackHandler` | Сброс выбора цифры класса |
| `toggle_notifications_` | `NavigationCallbackHandler` | Вкл/выкл уведомления о заменах для текущей школы |
| `toggle_lesson_reminders_` | `NavigationCallbackHandler` | Вкл/выкл напоминания об уроках |
| `toggle_quiet_hours_` | `NavigationCallbackHandler` | Вкл/выкл тихие часы |
| `toggle_update_notifications_` | `NavigationCallbackHandler` | Вкл/выкл админ-уведомления об обновлениях школ |
| `unsubscribe_` | `NavigationCallbackHandler` | Отписка от преподавателя/кабинета из `/settings` |
| `main_menu` | `NavigationCallbackHandler` | Возврат в главное меню |
| `change_class` | `NavigationCallbackHandler` | Сменить класс |

> **Fallback**: если ни один префикс не совпал, callback уходит в `menu` (`NavigationCallbackHandler`) — это поведение реализовано в `CallbackRouter.handle` (`handlers/callbacks/__init__.py:47-48`).

---

## 12. Администрирование

### 12.1 Кто админ

Список `ADMIN_IDS` задаётся в `.env`:
```env
ADMIN_IDS=123456789,987654321
```

### 12.2 Команды и кнопки

- `/status` — статус загрузки данных по школам.
- `/settings` — настройки: уведомления о заменах для текущей школы; `⏰` напоминания об уроках (`lesson_reminders`); `🌙` тихие часы (`quiet_hours`, по умолчанию 22:00–7:00); список подписок с кнопкой отписки; для админов — переключатель `update_notifications`. Реализовано в `handlers/common/settings.py`.
- `/cancel` — сброс текущего ввода/поиска (`reset_user_flow`) и возврат в главное меню.
- `/check_exchanges` — принудительная проверка замен.
- `/admin` — админ-панель (та же клавиатура, что и у callback'ов, включая «Принудительное обновление»).
- `/stats` — статистика пользователей: всего с классами + разбивка по школам.

> **Единая реализация**: с 11.09.2026 `handlers/admin/admin_panel.py` не дублирует построители панели — `/admin` и `/stats` делегируют в `AdminCallbackHandler` (`handlers/callbacks/admin_callbacks.py`). `/admin` и `/stats` регистрируются в `setup_admin_handlers()` (`handlers/admin/admin_panel.py`), вызов из `bot.py`. Команда `/check_exchanges` регистрируется в `bot.py`.

### 12.3 Админ-уведомления

[notification_service.py](services/notification_service.py) умеет слать сообщения всем админам.

- Флаг `update_notifications` хранится в `user_preferences.notifications` (коллекция `user_preferences` в `data/database.json`).
- Дефолт — `False` (см. `services/user_preferences.py:26-29`).
- Считывается через `BackgroundUpdater._get_admin_notification_settings` **по всем `ADMIN_IDS`** — флаг `True`, если он включён хотя бы у одного админа (`any(...)`), с 11.09.2026. Раздельная адресация (слать только подписанным админам) не реализована — осознанный компромисс, см. §16.
- Если хотя бы у одного админа флаг `True`, фоновое обновление шлёт summary-сообщение «обновлены школы: …» и сообщение об ошибке, если данные не загрузились.

---

## 13. Конфигурация (.env)

```env
TELEGRAM_TOKEN=your_bot_token_here
ADMIN_IDS=123456789
UPDATE_INTERVAL=3600
MAX_RETRIES=3
DB_PATH=./data/database.json
CACHE_PATH=./data/cache.json
LOG_LEVEL=INFO
LOG_FILE=./logs/bot.log
ADMIN_LOG_FILE=./logs/admin.log
```

> ✅ **`UPDATE_INTERVAL` используется** — `BackgroundUpdater` берёт интервал из `Config.UPDATE_INTERVAL` (по умолчанию 3600 c = 1 ч).
> ⚠️ **`CACHE_PATH` не используется** — папка `cache/` пуста, переменная оставлена для обратной совместимости.

---

## 14. Частые проблемы и где искать

| Симптом | Вероятная причина | Где смотреть |
|---------|-------------------|--------------|
| Бот не запускается | Нет `.env` или невалидный токен | [config/config.py](config/config.py), логи |
| Данные не загружаются | Изменился формат check-страницы или JS-файла | [core/data_loader.py](core/data_loader.py) |
| Замены не применяются | `CLASS_EXCHANGE` не найден или неправильный `class_id` | [services/exchange_service.py](services/exchange_service.py) |
| Замены портят базовое расписание | Неглубокая копия в `_apply_exchange` мутировала `school_data` | [services/exchange_service.py](services/exchange_service.py) (исправлено) |
| "Класс не найден" для правильного имени | Поиск по подстроке ловил другой класс | [services/schedule_service.py](services/schedule_service.py) (исправлено) |
| Не показываются уроки 10+ | Ключ формировался как `day0lesson` вместо `day{lesson:02d}` | [services/schedule_service.py](services/schedule_service.py) (исправлено) |
| Уведомления дублируются | JSON-ключи уроков стали строками | [services/exchange_detector.py](services/exchange_detector.py) |
| Уведомления не приходят | 0 доставок помечали ключ отправленным | [services/notification_service.py](services/notification_service.py) (исправлено) |
| Поиск учителя даёт не того | Индексы применяются к неправильному списку | [handlers/teachers/teacher_menu.py](handlers/teachers/teacher_menu.py), [handlers/callbacks/teacher_callbacks.py](handlers/callbacks/teacher_callbacks.py) |
| Бот зависает на обновлении из админки | Синхронный `requests` в async-обработчике — **исправлено 11.09**: `asyncio.to_thread` в `admin_callbacks.py` и `admin_panel.py` | [handlers/callbacks/admin_callbacks.py](handlers/callbacks/admin_callbacks.py) |
| Сообщение не уходит | Markdown экранирование сломано или >4096 символов — **исправлено 11.09**: единый `_escape_markdown` + нарезка в `messaging` | [services/base_schedule_service.py](services/base_schedule_service.py), [handlers/common/messaging.py](handlers/common/messaging.py) |
| Ввод несуществующего класса текстом падал с «непредвиденной ошибкой» | `show_class_selection` не умел работать без `callback_query` — **исправлено 11.09** | [handlers/common/callback_handler.py](handlers/common/callback_handler.py) |
| Повторное нажатие кнопки даёт «непредвиденную ошибку» | `Message is not modified` — **исправлено 11.09** во всех рендер-путях через `safe_edit_message`/`edit_long_message` | [handlers/common/messaging.py](handlers/common/messaging.py), [handlers/common/entity_menu.py](handlers/common/entity_menu.py) |
| `FileDB.delete_one` удалял все совпадающие документы, а не один | — **исправлено 11.09** | [database/file_db.py](database/file_db.py) |
| Битый `database.json` перезатирался пустым при первой записи | — **исправлено 11.09**: сохраняется копия `.corrupt` (с ротацией `.corrupt.N`) | [database/file_db.py](database/file_db.py) |
| Поиск учителя/кабинета выдавал чужого | Индексы поиска применялись к полному списку; кириллица в `callback_data` >64 байт — **исправлено 11.09** | [handlers/callbacks/teacher_callbacks.py](handlers/callbacks/teacher_callbacks.py), [handlers/callbacks/room_callbacks.py](handlers/callbacks/room_callbacks.py) |

---

## 15. Чек-лист при доработке

- [ ] Если меняешь структуру `schools_data`, проверь все сервисы расписания.
- [ ] Если правишь замены, проверь и `exchange_detector`, и `exchange_service`, и `notification_service`.
- [ ] Любая работа с `FileDB` должна учитывать потокобезопасность.
- [ ] Новые callback_data не должны превышать 64 байта (ограничение Telegram).
- [ ] Длинные сообщения (>4096) нужно нарезать.
- [x] Не оставляй `print()` в production-коде — используй `logger` (✅ все заменены на `logger`).
- [ ] Проверяй, что callback_data ≤ 64 байта.
- [ ] Длинные сообщения (>4096) нарезай через `messaging.split_long_message`.
- [ ] Обновляй этот Wiki и CHANGELOG при значимых изменениях.

---

## 16. Планируемые улучшения (roadmap)

См. [roadmap.md](roadmap.md) — там «что осталось сделать» с приоритетами P0/P1/P2; [CHANGELOG.md](CHANGELOG.md) — что уже сделано.

> ✅ **Основной аудит фактически закрыт 11.09.** Краткий список сделанного (подробности — в CHANGELOG):
>
> - **Критическое (P0)**: битый `database.json` → бэкап `.corrupt`; нарезка сообщений ≤4096; поиск учителей/кабинетов (чужие индексы + 64-байт callback); матчинг цифры класса («1» не матчит «11а»); `Message is not modified` во всех путях.
> - **P1**: двойной `query.answer()`; залипающие флаги поиска; утечка `class_digit`; TTL-кнопки; удалён мёртвый `UserSchool`; экранирование до бизнес-логики (замены учителей/кабинетов); `ExchangeService` в цикле.
> - **Рефакторинг/качество (P2)**: `EntityMenuHandler` (учителя/кабинеты — из дублей 913→500), `menu_builder`+`HELP_TEXT`, `is_admin`, `get_school_by_id`, `TIMEZONE`, `str(e)`→лог, мёртвый код, `ADMIN_LOG_FILE`, O(N) индекс получателей, TTL кэша уведомлений, `CacheService` (потокобезопасность + лимит), `@requires_school`, индикатор «печатает...», счётчик свежих школ. В Фазе 3: единая админ-панель (`/admin`/`/stats`), `/cancel` + `reset_user_flow`, общие `format_time_ago`/`find_class_id`, разделение хранилищ настроек уведомлений.
> - **Фаза 4 (новый функционал)**: уведомления о снятии замен (`↩️ … — замена снята`); подписки на преподавателей/кабинеты (`SubscriptionService`, кнопка в расписании, рассылка подписчикам, список в `/settings`); напоминания об уроках (`ReminderService` + `BackgroundUpdater._reminder_loop` на существующем asyncio-loop); тихие часы + анти-флуд; смещение недели и `get_next_lesson` (внутренние хелперы).
> - **Инструменты/тесты**: pytest (227 тестов: юнит + интеграционные моки), ruff (чистый), mypy (конфиг), CI-воркфлоу, `requirements-dev.txt`.

### 16.1 Открытый техдолг (P2)

> Полный актуальный список «что осталось» — см. [roadmap.md](roadmap.md); всё сделанное — в [CHANGELOG.md](CHANGELOG.md). Здесь — кратко, что ещё открыто:

1. **`FileDB` перезаписывает весь JSON на каждую операцию** — грязная запись (deferred) или переход на `sqlite3`. Сознательно не трогается на живой системе.
2. **`data_loader` ETag/If-Modified-Since** — не перекачивать данные при отсутствии изменений (метод `close()` уже добавлен).
3. **Архитектурные** (крупные, по желанию): `JobQueue` вместо ручного цикла; `ConversationHandler` вместо FSM-флагов; `UserRepository`; `render.py` (HTML) вместо разрозненного экранирования; `@dataclass` конфиг + `SCHOOLS_CONFIG` в JSON; строгая типизация (mypy); единый `Services`-объект вместо `context.bot_data.get(...)`.

> Открытых P0 нет; P0/P1/P2-минимум и все четыре фазы (1–4) закрыты. Явно отложены только крупные сквозные рефакторинги (слой данных `UserRepository`/`TypedDict`, clock-инъекция), параллельная загрузка школ, многозначный матчинг подписок и минутная гранулярность тихих часов.

---

## 17. Как дополнять Wiki

1. Открыть [WIKI.md](WIKI.md).
2. Добавить раздел или исправить существующий.
3. Сохранить.
4. При значимых изменениях кода обновить соответствующий раздел Wiki.
