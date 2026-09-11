# Roadmap — что осталось сделать

> Всё исправленное убрано отсюда и перенесено в [CHANGELOG.md](CHANGELOG.md).

> ✅ 11.09 (завершающий блок): декоратор `@requires_school` (применён к school_info/week_command); индикатор «печатает...» в админ-операциях; счётчик свежих школ; интеграционные mock-тесты (3); инструменты ruff (чистый) + mypy (конфиг) + CI; `requirements-dev.txt`. Итого 64 теста.
> Решено НЕ трогать на живой системе (рискованно): `FileDB` deferred-write, `data_loader` ETag — оставлены внизу как отдельные задачи.
> Аудит от 03.09.2026, стек: python-telegram-bot 20.7, requests, pytz, JSON-БД.
> Приоритеты: 🔴 P0 — падения/потеря данных, 🟠 P1 — некорректное поведение, 🟡 P2 — качество и поддержка.

---

## 1. 🔴 Критические баги (P0)

Нет открытых P0.

---

## 2. 🟠 Серьёзные баги (P1)


---

## 3. 🟡 Улучшения (P2)



### Данные и производительность

- **`FileDB` перезаписывает весь JSON на каждую операцию** — dirty-флаг + отложенная запись, или перейти на `sqlite3` (stdlib). (Рискованно менять на живой системе — делать отдельно.)
- **`data_loader` — ETag/If-Modified-Since** — не перекачивать данные при отсутствии изменений; закрывать `Session` (метод `close()` добавлен).

---

## 4. Архитектурные рекомендации

1. **`JobQueue` вместо ручного потока** — заменить `asyncio.create_task` + цикл на `application.job_queue.run_repeating(...)`; устраняет проблемы `stop()` и гонок. (Рекомендация, текущая схема стабильна.)
2. **`ConversationHandler` вместо FSM-флагов** — флаги `waiting_for_*` в `user_data` — источник «залипаний»; регистрировать до общего `MessageHandler(TEXT & ~COMMAND)` в `bot.py`.
3. **Слой данных** — `NotificationService` лезет в `user_service.db` напрямую. Завести `UserRepository` (`get_users_by_class(school_id, class_name)` и пр.).
4. **Форматирование/экранирование** — размыто по 4 файлам. Вынести в `render.py`, перейти на `HTML` parse_mode.
5. **Конфигурация** — `@dataclass(frozen=True)` c `from_env()` и валидацией; `SCHOOLS_CONFIG` в JSON/YAML, чтобы добавление школы не требовало правки кода.
6. **Типизация** — `TypedDict`/dataclass для структуры school_data; `mypy` для `services/`; исправить аннотации.
7. **Структура handlers** — builders клавиатур вынести в `handlers/keyboards.py`; зависимости прокидывать одним `Services`-объектом вместо повторов `context.bot_data.get(...)`.

---

## 5. Тесты

Есть pytest (64 теста: юнит + mock-интеграционные через pytest-asyncio, `tests/test_integration.py`). Осталось:

- Инструменты: включить ruff/mypy/CI в пайплайн (конфиги `ruff.toml`, `mypy.ini` добавлены).

