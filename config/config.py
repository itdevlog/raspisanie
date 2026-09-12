import os

import pytz
from dotenv import load_dotenv

load_dotenv()

# Часовой пояс по умолчанию (Екатеринбург = UTC+5). Читается из TIMEZONE (.env),
# чтобы не дублировать 'Asia/Yekaterinburg' в десятке сервисов.
_TZ_NAME = os.getenv('TIMEZONE', 'Asia/Yekaterinburg')
_TIMEZONE = pytz.timezone(_TZ_NAME)


def get_timezone():
    """Возвращает pytz-часовой пояс приложения (единая точка)."""
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


def _parse_admin_ids() -> list:
    """Разбирает ADMIN_IDS как список id через запятую."""
    raw = os.getenv('ADMIN_IDS', '')
    result = []
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


class Config:
    # Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

    # Настройки обновления
    UPDATE_INTERVAL = _parse_int('UPDATE_INTERVAL', 3600)
    MAX_RETRIES = _parse_int('MAX_RETRIES', 3)

    # Администраторы
    ADMIN_IDS = _parse_admin_ids()

    # База данных
    DB_PATH = os.getenv('DB_PATH', './data/database.json')
    CACHE_PATH = os.getenv('CACHE_PATH', './data/cache.json')

    # Логирование
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', './logs/bot.log')

    # Часовой пояс (Екатеринбург = UTC+5). Раньше хардкодился как
    # 'Asia/Yekaterinburg' в 5 местах и ошибочно назывался moscow_tz.
    TIMEZONE = os.getenv('TIMEZONE', 'Asia/Yekaterinburg')

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
    ADMIN_LOG_FILE = os.getenv('ADMIN_LOG_FILE', './logs/admin.log')

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
