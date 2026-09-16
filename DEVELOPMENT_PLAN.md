# План развития и улучшения проекта raspisanie

**Дата анализа:** 16 сентября 2026  
**Статус проекта:** Зрелый production-проект с отличной базой

---

## 📊 Резюме анализа

### Сильные стороны проекта

1. **Отличная архитектура** — чистое разделение на handlers → services → core
2. **Современный стек** — PTB 22.8, FastAPI, httpx, zoneinfo
3. **Quality assurance** — 268 тестов, ruff clean, mypy почти clean
4. **Production-ready** — manage.sh, systemd, multi-instance, backup/restore
5. **Документация** — README (334 строки), WIKI (508 строк), CHANGELOG, ROADMAP
6. **Активная разработка** — последнее обновление 13.09.2026

### Критические проблемы

1. ~~**mypy ошибки** — 10 ошибок в тестах~~ ✅ **исправлено 16.09.2026**
2. ~~**JSON БД** — риск потери данных~~ ✅ **закрыто 16.09.2026** (`fsync` + `.bak`); остаётся отложенная запись
3. ~~**ETag/If-Modified-Since** — нет HTTP-кэширования~~ ✅ **исправлено 16.09.2026**
4. ~~**Параллельная загрузка школ**~~ ✅ **исправлено 16.09.2026** (`ThreadPoolExecutor`)

### Выполнено 16.09.2026

- ✅ Исправлены 10 mypy ошибок (`tests/test_teacher_exchanges.py`, `tests/test_integration.py`) — `mypy .` чистый (111 файлов)
- ✅ `FileDB`: `flush` + `fsync` файла и директории, `.bak` предыдущей версии, корректная очистка temp
- ✅ `DataLoader`: условные запросы `ETag`/`If-Modified-Since`, `304` → deepcopy из кэша; кэш имени файла
- ✅ Параллельная загрузка школ: `ThreadPoolExecutor`, `MAX_PARALLEL_SCHOOLS` (default 4)
- ✅ Починен дато-зависимый `test_persist_flag_controls_disk_write` (`ExchangeDetector._now()`)
- ✅ 285 тестов проходят, ruff чистый, mypy 0 ошибок

### Архитектурные рекомендации (из roadmap.md)

1. Замена ручных asyncio.create_task на JobQueue
2. ConversationHandler вместо FSM-флагов
3. Слой UserRepository для доступа к данным
4. Конфигурация через dataclass + JSON/YAML для школ
5. TypedDict для типизации school_data

---

## 🎯 Приоритеты улучшений

### 🔴 P0 — Критические (исправить в первую очередь)

#### 1. Исправить mypy ошибки
**Файлы:** `tests/test_teacher_exchanges.py`, `tests/test_integration.py`  
**Проблема:** 10 ошибок типизации  
**Решение:** Добавить проверки на None, исправить типы

```bash
# Текущий статус
.venv/bin/mypy .  # 10 errors
```

**Задачи:**
- [ ] Исправить `test_teacher_exchanges.py:49` — аргументы _get_teacher_schedule_data
- [ ] Исправить `test_teacher_exchanges.py:147, 160` — аналогично
- [ ] Исправить `test_integration.py:136, 141` — тип datetime

---

#### 2. FileDB — атомарность и отложенная запись
**Файл:** `database/file_db.py`  
**Проблема:** Перезапись всего JSON на каждую операцию, риск потери данных

**Решение A (минимальное):** Dirty-флаг + отложенная запись
```python
# Добавить буферизацию записи
- Запись в временный файл → atomic rename
- Dirty-флаг для пакетной записи
- Backup при corruption
```

**Решение B (рекомендуемое):** Переход на SQLite
```python
# Преимущества:
- Транзакции и ACID
- Частичные обновления
- Индексы для производительности
- Встроен в stdlib
```

**Задачи:**
- [ ] Реализовать atomic write (temp file + os.replace)
- [ ] Добавить dirty-флаг для отложенной записи
- [ ] Опционально: миграция на SQLite (breaking change)

---

#### 3. Data Loader — HTTP кэширование
**Файл:** `core/data_loader.py`  
**Проблема:** Нет ETag/If-Modified-Since, перекачивание данных при отсутствии изменений

**Решение:**
```python
# Добавить заголовки кэширования
headers = {
    "If-None-Match": etag,  # из прошлого запроса
    "If-Modified-Since": last_modified
}
# 304 Not Modified → не парсить JSON
```

**Задачи:**
- [ ] Сохранять ETag и Last-Modified в кэше
- [ ] Отправлять заголовки при запросе
- [ ] Обрабатывать ответ 304
- [ ] Закрывать httpx.Session явно (context manager)

---

### 🟠 P1 — Серьёзные (улучшение надёжности)

#### 4. Параллельная загрузка школ
**Файл:** `core/background_updater.py`  
**Проблема:** Школы загружаются последовательно

**Решение:**
```python
async with asyncio.Semaphore(3):  # макс. 3 параллельных
    tasks = [load_school(school_id) for school_id in schools]
    await asyncio.gather(*tasks)
```

**Задачи:**
- [ ] Добавить Semaphore (напр. 3-5 параллельных)
- [ ] Обработать ошибки каждой школы независимо
- [ ] Логировать время загрузки каждой школы

---

#### 5. JobQueue вместо ручных asyncio.create_task
**Файлы:** `bot.py`, `core/background_updater.py`  
**Проблема:** Ручное управление задачами, проблемы с stop()

**Решение:**
```python
# Вместо:
asyncio.create_task(background_updater.start())

# Использовать:
application.job_queue.run_repeating(
    callback=check_exchanges,
    interval=UPDATE_INTERVAL,
    first=0
)
```

**Задачи:**
- [ ] Перенести background_updater на JobQueue
- [ ] Перенести reminder_loop на JobQueue
- [ ] Перенести digest_loop на JobQueue
- [ ] Удалить ручное управление задачами

---

#### 6. ConversationHandler вместо FSM-флагов
**Файлы:** `handlers/**/*.py`  
**Проблема:** Флаги `waiting_for_*` в user_data — источник «залипаний»

**Решение:**
```python
# Использовать ConversationHandler
from telegram.ext import ConversationHandler

WAITING_FOR_CLASS = 1
WAITING_FOR_TEACHER = 2

conv_handler = ConversationHandler(
    entry_points=[...],
    states={
        WAITING_FOR_CLASS: [...],
        WAITING_FOR_TEACHER: [...]
    },
    fallbacks=[...]
)
```

**Задачи:**
- [ ] Аудит всех FSM-флагов в коде
- [ ] Выделить диалоги (выбор школы, класса, поиска)
- [ ] Реализовать через ConversationHandler
- [ ] Добавить fallbacks для /cancel

---

### 🟡 P2 — Улучшения (качество жизни)

#### 7. Слой UserRepository
**Файлы:** `services/user_service.py`, `services/subscription_service.py`  
**Проблема:** NotificationService лезет в user_service.db напрямую

**Решение:**
```python
class UserRepository:
    def get_users_by_class(self, school_id: str, class_name: str) -> List[int]:
        ...
    
    def get_subscribers(self, subscription_type: str, entity_name: str) -> List[int]:
        ...
```

**Задачи:**
- [ ] Создать `database/user_repository.py`
- [ ] Перенести запросы выбора пользователей
- [ ] Обновить NotificationService, SubscriptionService
- [ ] Добавить аннотации типов (TypedDict)

---

#### 8. Конфигурация через dataclass
**Файлы:** `config/config.py`, `config/schools.py`  
**Проблема:** Добавление школы требует правки кода

**Решение:**
```python
@dataclass(frozen=True)
class SchoolConfig:
    id: str
    name: str
    check_url: str
    display_name: str
    
@dataclass
class AppConfig:
    telegram_token: str
    admin_ids: List[int]
    schools: Dict[str, SchoolConfig]
    
    @classmethod
    def from_env(cls) -> "AppConfig":
        # Валидация и парсинг .env
```

**Задачи:**
- [ ] Создать `config/app_config.py`
- [ ] Перенести SCHOOLS_CONFIG в JSON/YAML
- [ ] Добавить валидацию при загрузке
- [ ] Обновить bot.py для использования

---

#### 9. Форматирование/экранирование в render.py
**Файлы:** `services/text_utils.py`, `handlers/common/messaging.py`  
**Проблема:** Экранирование размазано по 4 файлам

**Решение:**
```python
# services/render.py
def escape_markdown_v2(text: str) -> str:
    ...

def format_schedule(lesson: Lesson, show_exchanges: bool = True) -> str:
    ...
    
def parse_mode() -> str:
    return "HTML"  # или MarkdownV2
```

**Задачи:**
- [ ] Создать `services/render.py`
- [ ] Перенести все функции форматирования
- [ ] Перейти на HTML parse_mode (богаче возможности)
- [ ] Обновить все вызовы

---

#### 10. Многозначный матчинг подписок
**Файл:** `services/subscription_service.py`  
**Проблема:** Подписка по точному имени, нет алиасов

**Решение:**
```python
# Добавить нормализацию имён
TEACHER_ALIASES = {
    "Иванов И.И.": ["Иванов", "Иванов И.", "Иванов Игорь"],
    "каб. 301": ["301", "кабинет 301", "ауд. 301"]
}
```

**Задачи:**
- [ ] Добавить маппинг алиасов
- [ ] Нормализация при подписке
- [ ] Поиск по алиасам при детекте замен

---

#### 11. Тихие часы с минутной точностью
**Файл:** `services/user_preferences.py`  
**Проблема:** Только целые часы (22:00-7:00)

**Решение:**
```python
# Хранить как минуты от начала суток
quiet_start: int = 22 * 60  # 22:00
quiet_end: int = 7 * 60    # 07:00

# Или datetime.time
quiet_start: datetime.time = datetime.time(22, 30)
```

**Задачи:**
- [ ] Изменить формат хранения
- [ ] Обновить UI настроек
- [ ] Миграция существующих данных

---

### 🟢 P3 — Долгосрочные (архитектурные)

#### 12. Переход на полноценную БД
**Текущее:** JSON файлы (`data/database.json`)  
**Целевое:** SQLite или PostgreSQL

**Преимущества:**
- Транзакции и ACID
- Индексы для производительности
- Частичные обновления
- Конкурентный доступ

**Задачи:**
- [ ] Выбрать БД (SQLite для простоты, PostgreSQL для масштаба)
- [ ] Спроектировать схему данных
- [ ] Написать миграции
- [ ] Реализовать ORM/слой доступа
- [ ] Миграция данных из JSON

---

#### 13. Мониторинг и алертинг
**Отсутствует:** Система мониторинга ошибок

**Решение:**
- Sentry для отслеживания ошибок
- Prometheus + Grafana для метрик
- Health checks с алертами

**Задачи:**
- [ ] Интегрировать Sentry
- [ ] Добавить метрики (запросы, ошибки, время ответа)
- [ ] Настроить дашборды
- [ ] Алерты в Telegram при критических ошибках

---

#### 14. Rate limiting для API
**Файл:** `web/api.py`  
**Проблема:** Нет ограничения запросов к API

**Решение:**
```python
from slowapi import SlowAPILimiter

limiter = SlowAPILimiter()
app.state.limiter = limiter

@app.get("/api/schedule")
@limiter.limit("100/minute")
async def get_schedule(...):
    ...
```

**Задачи:**
- [ ] Добавить slowapi
- [ ] Настроить лимиты на эндпоинты
- [ ] Обработка 429 Too Many Requests

---

#### 15. Кэширование на уровне Redis
**Текущее:** In-memory cache с TTL  
**Проблема:** Нет кэша между рестартами, нет shared cache для multi-instance

**Решение:**
```python
import redis.asyncio as redis

cache = redis.Redis(host='localhost', port=6379)
await cache.setex(f"schedule:{school_id}:{date}", ttl=3600, value=json_data)
```

**Задачи:**
- [ ] Добавить Redis
- [ ] Миграция cache_service
- [ ] Настроить TTL для разных типов данных
- [ ] Pub/Sub для инвалидации кэша

---

## 📈 Метрики качества

### Текущее состояние

| Метрика | Значение | Цель |
|---------|----------|------|
| Тесты | 268 | 300+ |
| ruff | ✅ 0 ошибок | 0 ошибок |
| mypy | ❌ 10 ошибок | 0 ошибок |
| Покрытие | Не измеряется | 80%+ |
| Documentation | Отличная | Актуальная |

### Цели на 3 месяца

1. **Исправить все mypy ошибки** — 0 ошибок
2. **Добавить 30+ тестов** — 300+ тестов
3. **Внедрить покрытие тестами** — 80%+
4. **Миграция на JobQueue** — все фоновые задачи
5. **SQLite миграция** — опционально

---

## 📅 План внедрения

### Неделя 1-2: Критические исправления

- [ ] Исправить mypy ошибки (P0-1)
- [ ] FileDB atomic write (P0-2A)
- [ ] Data Loader HTTP кэширование (P0-3)

### Неделя 3-4: Надёжность

- [ ] JobQueue вместо asyncio.create_task (P1-5)
- [ ] Параллельная загрузка школ (P1-4)
- [ ] ConversationHandler аудит (P1-6)

### Неделя 5-8: Рефакторинг

- [ ] UserRepository слой (P2-7)
- [ ] AppConfig dataclass (P2-8)
- [ ] Render модуль (P2-9)

### Месяц 3+: Долгосрочные улучшения

- [ ] SQLite миграция (P3-12)
- [ ] Sentry мониторинг (P3-13)
- [ ] Redis кэширование (P3-15)

---

## 🚀 Быстрые победы (можно сделать за 1-2 часа)

1. **Исправить mypy ошибки** — 10 ошибок в 2 файлах
2. **Добавить explicit session.close()** в data_loader
3. **Добавить backup .corrupt** в FileDB
4. **Логирование времени загрузки школ**
5. **Документировать API эндпоинты**

---

## ⚠️ Риски

### Высокий риск (требует тестирования)

1. **Миграция на SQLite** — breaking change, нужна обратная совместимость
2. **ConversationHandler** — изменение поведения FSM, риск «залипаний»
3. **JobQueue миграция** — изменение управления задачами

### Средний риск

1. **FileDB отложенная запись** — риск потери данных при крахе
2. **AppConfig dataclass** — изменение конфигурации

### Низкий риск

1. **myty исправления** — только тесты
2. **HTTP кэширование** — обратно совместимо
3. **Render модуль** — рефакторинг без изменения API

---

## 📝 Рекомендации

### Немедленно (эта неделя)

1. Исправить mypy ошибки — 10 ошибок мешают CI
2. Добавить atomic write в FileDB — критично для целостности данных
3. Добавить HTTP кэширование — снизит нагрузку на Nikasoft

### В ближайший месяц

1. JobQueue миграция — улучшит управление задачами
2. UserRepository — улучшит архитектуру
3. Параллельная загрузка — ускорит обновление для >5 школ

### Долгосрочно (3-6 месяцев)

1. SQLite миграция — если планируется >10 школ
2. Monitoring/Sentry — для production мониторинга
3. Redis кэш — для multi-instance деплоя

---

## 🔗 Связанные документы

- [roadmap.md](roadmap.md) — что осталось сделать после Фаз 1-4
- [CHANGELOG.md](CHANGELOG.md) — история изменений
- [WIKI.md](WIKI.md) — архитектура проекта
- [README.md](README.md) — документация пользователя

---

**Автор:** AI Assistant  
**Дата создания:** 16 сентября 2026  
**Статус:** Готов к обсуждению и приоритизации
