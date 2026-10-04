import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

def _parse_timezone(name: str = 'TIMEZONE', default: str = 'Asia/Yekaterinburg') -> str:
    """Красиво разбирает название часового пояса.

    Раньше `ZoneInfo(os.getenv('TIMEZONE', ...))` падал прямо на импорте
    config с сырым `ZoneInfoNotFoundError`. Здесь — понятное сообщение.
    """
    raw = os.getenv(name)
    value = (raw if raw is not None else default).strip() or default
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(
            f"Переменная {name!r} = {raw!r} — неизвестный часовой пояс. "
            f"Пример: {name}=Europe/Moscow. Проверьте .env (см. .env.example)."
        )
    return value


# Часовой пояс по умолчанию (Екатеринбург = UTC+5). Читается из TIMEZONE (.env),
# чтобы не дублировать 'Asia/Yekaterinburg' в десятке сервисов.
_TZ_NAME = _parse_timezone()
_TIMEZONE = ZoneInfo(_TZ_NAME)


def get_timezone():
    """Возвращает часовой пояс приложения (zoneinfo, единая точка)."""
    return _TIMEZONE


def _parse_int(name: str, default: int) -> int:
    """Красиво разбирает целочисленную переменную окружения.

    Раньше `int(os.getenv(...))` падал прямо на импорте config с непонятным
    ValueError. Здесь — понятное сообщение и fallback на умолчание.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == '':
        return default
    try:
        return int(raw.strip())
    except ValueError:
        raise ValueError(
            f"Переменная {name!r} = {raw!r} не является числом. "
            f"Пример: {name}=3600. Проверьте .env (см. .env.example)."
        )


def _parse_int_positive(name: str, default: int) -> int:
    """Как `_parse_int`, но требует значение > 0."""
    value = _parse_int(name, default)
    if value <= 0:
        raise ValueError(
            f"Переменная {name!r} = {value!r} должна быть больше 0. "
            f"Пример: {name}={default}. Проверьте .env (см. .env.example)."
        )
    return value


def _parse_int_min(name: str, default: int, minimum: int) -> int:
    """Как `_parse_int`, но не даёт опуститься ниже `minimum`."""
    return max(minimum, _parse_int(name, default))


def _parse_port(name: str, default: int) -> int:
    """Разбирает номер порта и проверяет диапазон 0..65535 (0 = выключено)."""
    value = _parse_int(name, default)
    if not 0 <= value <= 65535:
        raise ValueError(
            f"Переменная {name!r} = {value!r} вне диапазона 0..65535 (0 — веб выключен). "
            f"Пример: {name}=8080. Проверьте .env (см. .env.example)."
        )
    return value


def normalize_webapp_url(raw: str) -> str:
    """Приводит WEBAPP_URL к виду, допустимому Telegram (http/https).

    Telegram отклоняет WebAppInfo с URL без схемы ('only https links are
    allowed'), что валит /start. Если схема не указана — подставляем https.
    """
    url = (raw or '').strip()
    if not url:
        return ''
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return f'https://{url}'


def _parse_admin_ids() -> list[int]:
    """Разбирает ADMIN_IDS как список id через запятую."""
    raw = os.getenv('ADMIN_IDS', '')
    result: list[int] = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except ValueError:
            raise ValueError(
                f"ADMIN_IDS содержит нечисловое значение {part!r}. "
                f"Ожидается список id через запятую. Проверьте .env (см. .env.example)."
            )
    return result


@dataclass(frozen=True)
class AppConfig:
    """Неизменяемый снимок настроек приложения из переменных окружения.

    Единый источник значений. `Config` ниже — обратно-совместимый фасад с
    прежними UPPER_CASE-именами, которые ожидает существующий код.
    """

    telegram_token: str | None
    update_interval: int
    max_retries: int
    max_parallel_schools: int
    admin_ids: list[int]
    db_path: str
    cache_path: str
    log_level: str
    log_file: str
    admin_log_file: str
    timezone: str
    webapp_host: str
    webapp_port: int
    webapp_url: str
    edge_host: str
    edge_port: int
    snapshot_path: str
    snapshot_max_age: int
    snapshot_max_bytes: int
    snapshot_max_retries: int
    edge_ingest_url: str
    edge_ingest_secret: str
    edge_auth_secret: str
    edge_origin_url: str
    vapid_public_key: str
    vapid_private_key: str
    vapid_subject: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Собирает конфиг из окружения через существующие хелперы валидации."""
        return cls(
            telegram_token=os.getenv('TELEGRAM_TOKEN'),
            update_interval=_parse_int_positive('UPDATE_INTERVAL', 3600),
            max_retries=_parse_int_min('MAX_RETRIES', 3, 1),
            # Параллельная загрузка школ (потоков). 1 — последовательно.
            max_parallel_schools=max(1, _parse_int('MAX_PARALLEL_SCHOOLS', 4)),
            admin_ids=_parse_admin_ids(),
            db_path=os.getenv('DB_PATH', './data/database.json'),
            cache_path=os.getenv('CACHE_PATH', './data/cache.json'),
            log_level=os.getenv('LOG_LEVEL', 'INFO'),
            log_file=os.getenv('LOG_FILE', './logs/bot.log'),
            admin_log_file=os.getenv('ADMIN_LOG_FILE', './logs/admin.log'),
            timezone=_parse_timezone(),
            webapp_host=os.getenv('WEBAPP_HOST', '127.0.0.1'),
            webapp_port=_parse_port('WEBAPP_PORT', 8080),
            webapp_url=normalize_webapp_url(os.getenv('WEBAPP_URL', '')),
            # Edge-хост/порт публичного сайта (отдельно от WEBAPP мини-аппа).
            edge_host=os.getenv('EDGE_HOST', '127.0.0.1'),
            edge_port=_parse_port('EDGE_PORT', 8090),
            # Снапшот расписания: путь и лимиты (возраст/размер/ретраи).
            snapshot_path=os.getenv('SNAPSHOT_PATH', './data/snapshot.json'),
            snapshot_max_age=_parse_int_positive('SNAPSHOT_MAX_AGE', 7200),
            snapshot_max_bytes=_parse_int_positive('SNAPSHOT_MAX_BYTES', 20 * 1024 * 1024),
            # Отдельно от MAX_RETRIES (ретраи DataLoader) — свои ретраи публикации.
            snapshot_max_retries=_parse_int_min('SNAPSHOT_MAX_RETRIES', 3, 1),
            # Публикация снапшота на edge (нужна только origin).
            edge_ingest_url=os.getenv('EDGE_INGEST_URL', ''),
            edge_ingest_secret=os.getenv('EDGE_INGEST_SECRET', ''),
            edge_auth_secret=os.getenv('EDGE_AUTH_SECRET', ''),
            # Прокси push на origin — нужен только edge; на origin может быть пустым.
            edge_origin_url=os.getenv('EDGE_ORIGIN_URL', ''),
            # Web Push (VAPID).
            vapid_public_key=os.getenv('VAPID_PUBLIC_KEY', ''),
            vapid_private_key=os.getenv('VAPID_PRIVATE_KEY', ''),
            vapid_subject=os.getenv('VAPID_SUBJECT', 'mailto:admin@example.ru'),
        )


# Единый снимок настроек на импорте. Config — тонкая обёртка над ним.
_APP_CONFIG = AppConfig.from_env()


class Config:
    # Telegram
    TELEGRAM_TOKEN = _APP_CONFIG.telegram_token

    # Настройки обновления
    UPDATE_INTERVAL = _APP_CONFIG.update_interval
    MAX_RETRIES = _APP_CONFIG.max_retries
    # Параллельная загрузка школ (потоков). 1 — последовательно.
    MAX_PARALLEL_SCHOOLS = _APP_CONFIG.max_parallel_schools

    # Администраторы
    ADMIN_IDS = _APP_CONFIG.admin_ids

    # База данных
    DB_PATH = _APP_CONFIG.db_path
    CACHE_PATH = _APP_CONFIG.cache_path

    # Логирование
    LOG_LEVEL = _APP_CONFIG.log_level
    LOG_FILE = _APP_CONFIG.log_file

    # Часовой пояс (Екатеринбург = UTC+5). Раньше хардкодился как
    # 'Asia/Yekaterinburg' в 5 местах и ошибочно назывался moscow_tz.
    TIMEZONE = _APP_CONFIG.timezone

    # Mini App / веб-сервер
    # 127.0.0.1 по умолчанию: доступ к боту только через reverse proxy (Caddy),
    # чтобы порт не был открыт в интернет. Для нескольких ботов — свой порт каждому.
    WEBAPP_HOST = _APP_CONFIG.webapp_host
    WEBAPP_PORT = _APP_CONFIG.webapp_port
    WEBAPP_URL = _APP_CONFIG.webapp_url

    # Публичный сайт: edge-сервер, снапшот, push (W1+).
    EDGE_HOST = _APP_CONFIG.edge_host
    EDGE_PORT = _APP_CONFIG.edge_port
    SNAPSHOT_PATH = _APP_CONFIG.snapshot_path
    SNAPSHOT_MAX_AGE = _APP_CONFIG.snapshot_max_age
    SNAPSHOT_MAX_BYTES = _APP_CONFIG.snapshot_max_bytes
    # Свои ретраи публикации снапшота, отдельно от MAX_RETRIES (DataLoader).
    SNAPSHOT_MAX_RETRIES = _APP_CONFIG.snapshot_max_retries
    # Origin публикует снапшот на edge по EDGE_INGEST_URL (HMAC-подпись).
    EDGE_INGEST_URL = _APP_CONFIG.edge_ingest_url
    EDGE_INGEST_SECRET = _APP_CONFIG.edge_ingest_secret
    # Общий секрет origin↔edge (edge проксирует push на origin).
    EDGE_AUTH_SECRET = _APP_CONFIG.edge_auth_secret
    # Нужен только edge; на origin может быть пустым.
    EDGE_ORIGIN_URL = _APP_CONFIG.edge_origin_url
    # Web Push (VAPID).
    VAPID_PUBLIC_KEY = _APP_CONFIG.vapid_public_key
    VAPID_PRIVATE_KEY = _APP_CONFIG.vapid_private_key
    VAPID_SUBJECT = _APP_CONFIG.vapid_subject

    @staticmethod
    def is_admin(config, user_id: int) -> bool:
        """Единая проверка, является ли user_id администратором.

        Раньше этот код дублировался в admin_panel.py, admin_callbacks.py,
        settings.py и bot.py.
        """
        ids: list | None = getattr(config, 'ADMIN_IDS', None) if config else None
        if not ids:
            return False
        return user_id in ids

    # Логирование админ-панели
    ADMIN_LOG_FILE = _APP_CONFIG.admin_log_file

    # Создаем необходимые директории
    @staticmethod
    def setup_directories():
        os.makedirs('./data', exist_ok=True)
        os.makedirs('./logs', exist_ok=True)
        os.makedirs('./cache', exist_ok=True)

    @staticmethod
    def get_updatelog_path() -> str:
        """Путь к файлу лога обновлений — рядом с базой данных (в data/).

        Раньше жёстко 'updatelog.txt' от cwd; запуск не из корня молча создавал
        пустой файл в другом месте. Выводим из CACHE_PATH, чтобы файл лежал
        в общей data-директории.
        """
        db_path = os.getenv('DB_PATH', './data/database.json')
        data_dir = os.path.dirname(db_path) or './data'
        return os.path.join(data_dir, 'updatelog.txt')
