# Roadmap — что осталось сделать

> Всё исправленное убрано отсюда и перенесено в [CHANGELOG.md](CHANGELOG.md).

> 🌐 **Публичный сайт расписания (основная оставшаяся работа).** Спека — [docs/superpowers/specs/2026-09-24-public-schedule-site-design.md](docs/superpowers/specs/2026-09-24-public-schedule-site-design.md); план реализации (W1–W41: базовый MVP W1–W31 + паритет с оригиналом Nikasoft W32–W41) — [docs/superpowers/plans/2026-10-02-public-schedule-site.md](docs/superpowers/plans/2026-10-02-public-schedule-site.md). Ни одна задача ещё не начата.

> ✅ **17.09 (полное выполнение [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md), 31 коммит `e8bf2a9..44ffc37`):** закрыты все существенные пункты T1–T45. CI впервые зелёный (ранее 23/23 красных); 514 тестов, покрытие 67%, ruff/mypy чистые. Ключевое: CI (`conftest`), widget API + HMAC/IDOR + XSS, PWA-иконки, напоминания/дайджесты с заменами и переносами, надёжность рассылок (baseline после доставки, тихие часы, атомарные кэши), вынос I/O из event loop, rate limiting, SW-гигиена, валидация конфига, `manage.sh`, FSM/callback UX, дедуп замен per-замена, `JobQueue`, `UserRepository`, `AppConfig`, алертинг админам, офлайн-WebApp. **Единственный parked — T42** (`FileDB` deferred-write/SQLite). Действия при деплое: `pip install -r requirements.txt` (apscheduler) и правка живого `.env`. Подробности — в [CHANGELOG.md](CHANGELOG.md).

> ✅ 16.09 (по [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md)): `FileDB` — долговечная запись (`fsync` файла + директории, `.bak`); `data_loader` — условные запросы `ETag`/`If-Modified-Since` (304 из кэша) и закрытие сессии; параллельная загрузка школ (`ThreadPoolExecutor` + `MAX_PARALLEL_SCHOOLS`); устранены 10 ошибок mypy в тестах; починен дато-зависимый тест кэша замен (`ExchangeDetector._now`). Подробности — в [CHANGELOG.md](CHANGELOG.md).

> ✅ 11.09 (Фаза 1 — критические исправления, P0): кэш расписания привязан к `school_id` (Task 4); кэш замен привязан к дате + атомарная запись (Task 5); блокирующий детект замен вынесен в `asyncio.to_thread` с единым flush (Task 6); `KeyError` при длинном запросе поиска (Task 2); `update.message` → `_edit_or_reply` (Task 3); пагинация сохраняет тип расписания (Task 7); валидация несуществующей школы + сброс флагов поиска (Task 8); общий `GENERIC_ERROR_MSG` в глобальном обработчике (Task 9). Подробности — в [CHANGELOG.md](CHANGELOG.md). Открытых P0 нет.
> ✅ 11.09 (Фаза 2 — надёжность и консистентность, P1): `FileDB` сообщает об ошибках записи; общий `escape_markdown`; пакетные настройки уведомлений + индекс получателей с учётом настроек; merge частичной загрузки + `asyncio.Lock` + единый `_on_data_replaced()`; инвалидация и guard в админ-refresh; `RetryAfter` + троттлинг рассылки; один слой ретраев и сессия на вызов в `DataLoader`; mypy-аннотация. Осталось опционально: параллельная загрузка школ через `Semaphore` — сознательно отложена (см. §2; реализована 16.09 через `ThreadPoolExecutor`). Подробности — в [CHANGELOG.md](CHANGELOG.md).
> ✅ 11.09 (завершающий блок Фазы 1): декоратор `@requires_school` (применён к school_info/week_command); индикатор «печатает...» в админ-операциях; счётчик свежих школ; интеграционные mock-тесты (3); инструменты ruff (чистый) + mypy (конфиг) + CI; `requirements-dev.txt`.
> ✅ 11.09 (Фаза 3 — рефакторинг и качество, P2): единая админ-панель (`/admin`/`/stats` делегируют в `AdminCallbackHandler`, `/stats` показывает статистику); `/cancel` + единый `reset_user_flow`; удалён мёртвый код и утечки `str(e)`; общие хелперы `format_time_ago`/`find_class_id`; разделение хранилищ настроек уведомлений (exchange → `UserService`, update → `UserPreferencesService`; `_get_admin_notification_settings` учитывает всех админов). Подробности — в [CHANGELOG.md](CHANGELOG.md).
> ✅ 12.09 (после Фазы 4): информативный формат уведомлений о заменах «до → после» с временем урока; утренний дайджест (`DigestService`, за час до первого урока — учитывает смены); навигация по неделям в недельном расписании (±2 недели). Подробности — в [CHANGELOG.md](CHANGELOG.md).
>
> ✅ 11.09 (Фаза 4 — новый функционал): уведомления о снятии замен (`↩️ … — замена снята`); подписки на преподавателей/кабинеты (`SubscriptionService`, кнопка в расписании, рассылка подписчикам, список в `/settings`); напоминания об уроках (`ReminderService` + цикл `BackgroundUpdater._reminder_loop` на существующем asyncio-loop, без новых зависимостей); тихие часы + анти-флуд; смещение недели и helper `get_next_lesson` (только внутренние, без пользовательской команды). Подробности — в [CHANGELOG.md](CHANGELOG.md).
>
> ✅ **Оригинальный аудит (03.09) и [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) (17.09) закрыты.** Остались только явно отложенные пункты:
> - многозначный матчинг подписок (одно имя на сущность, без алиасов);
> - архитектурные: `ConversationHandler` (§2), единый `render.py`/`HTML` (§4), `keyboards.py` + `Services`-объект (§7), инъекция часов (clock);
> - **parked T42:** `FileDB` deferred-write/SQLite — данные оставлены durable (мотивация снята T13).
> - `data_loader` ETag — ✅ реализовано 16.09.
>
> Аудит от 03.09.2026 (исторический стек: python-telegram-bot 20.7, requests, pytz, JSON-БД). Стек модернизирован 13.09.2026: PTB 22.8 (`Defaults`, `AIORateLimiter`), httpx, stdlib `zoneinfo`, FastAPI + uvicorn (Mini App).
> Приоритеты: 🔴 P0 — падения/потеря данных, 🟠 P1 — некорректное поведение, 🟡 P2 — качество и поддержка.

---

## 1. 🔴 Критические баги (P0)

Нет открытых P0.

---

## 2. 🟠 Серьёзные баги (P1)

Закрытых в Фазе 2 пунктов здесь нет — всё перенесено в [CHANGELOG.md](CHANGELOG.md).

Осталось **опционально** (сознательно отложено, не входит в P1-минимум):

- ~~**Параллельная загрузка школ**~~ — ✅ реализована 16.09 (`ThreadPoolExecutor`, `MAX_PARALLEL_SCHOOLS`).

---

## 3. 🟡 Улучшения (P2)

Пункты Фазы 3, сделанные 11.09 (единая админ-панель, `/cancel` + `reset_user_flow`, удаление мёртвого кода, `str(e)`→лог, общие хелперы, разделение хранилищ настроек), перенесены в [CHANGELOG.md](CHANGELOG.md). Ниже — что осталось.

> Сознательно отложены крупные сквозные рефакторинги (низкая пользовательская ценность относительно объёма): слой данных `UserRepository` и инъекция часов (clock).

### Данные и производительность

- ~~**`data_loader` — ETag/If-Modified-Since**~~ — ✅ реализовано 16.09 (304 → кэш; `close()` уже был).
- ~~**`FileDB` перезаписывает весь JSON на каждую операцию**~~ — долговечность закрыта 16.09 (`fsync` + `.bak`); отложенная запись (dirty-флаг) и миграция на `sqlite3` **осознанно parked (T42)**: deferred-write снизил бы долговечность, а мотивация «event loop» снята выносом I/O в `to_thread` (T13). Данные остаются durable.

### Отложено в Фазе 4 (явно вне рамок)

- **Многозначный матчинг подписок** — сейчас подписка и рассылка работают по точному имени сущности (`{kind, name}`); алиасы/нормализация нескольких написаний не реализованы.
- ~~**Тихие часы с почасовой точностью**~~ — ✅ реализовано 17.09 (T38): окно задаётся с минутной точностью (`datetime.time`), с миграцией данных и UI.

---

## 4. Архитектурные рекомендации

1. ~~**`JobQueue` вместо ручного потока**~~ — ✅ реализовано 17.09 (T40): периодические задачи переведены на `application.job_queue.run_repeating(...)` (требует `apscheduler`).
2. **`ConversationHandler` вместо FSM-флагов** — флаги `waiting_for_*` в `user_data` — источник «залипаний»; регистрировать до общего `MessageHandler(TEXT & ~COMMAND)` в `bot.py`. (17.09 добавлены TTL и сброс sibling-флагов — T30; полный переход на ConversationHandler остаётся.)
3. ~~**Слой данных**~~ — ✅ реализовано 17.09 (T41): `UserRepository` закрывает прямой доступ `NotificationService` к `user_service.db`; добавлен `TypedDict` для `school_data`.
4. **Форматирование/экранирование** — размыто по файлам. Вынести в `render.py`, перейти на `HTML` parse_mode. (17.09 закрыты XSS/PWA и экранирование — T4/T7, но единый слой не вводился.)
5. ~~**Конфигурация**~~ — ✅ реализовано 17.09 (T43): `@dataclass(frozen=True)` c `AppConfig.from_env()`, валидация и внешний JSON школ.
6. ~~**Типизация**~~ — ✅ реализовано 17.09 (T41): `TypedDict` для `school_data`; `mypy` покрывает весь репозиторий (0 ошибок).
7. **Структура handlers** — builders клавиатур вынести в `handlers/keyboards.py`; зависимости прокидывать одним `Services`-объектом вместо повторов `context.bot_data.get(...)`.

> Осталось из архитектурных: переход на `ConversationHandler` (§2), единый `render.py`/`HTML` (§4), `keyboards.py` + `Services`-объект (§7), инъекция часов (clock).

---

## 5. Тесты

Есть pytest (514 тестов: юнит + mock-интеграционные через pytest-asyncio, `tests/test_integration.py`). 

- Инструменты: ruff/mypy/CI подключены (конфиги `ruff.toml`, `mypy.ini`, `.github/workflows/ci.yml`); `ruff check .` — чисто; `mypy .` — 0 ошибок на всём репозитории (141 файл); CI зелёный, матрица Python 3.11/3.12/3.13, покрытие 67% при пороге 60%.
- Для сужения Optional-полей PTB используются хелперы `handlers/common/typing.py` (`require_user`/`require_message`/`require_query`/`require_user_data`).

