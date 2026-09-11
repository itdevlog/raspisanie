import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    
    # Настройки обновления
    UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', 3600))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))
    
    # Администраторы
    ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
    
    # База данных
    DB_PATH = os.getenv('DB_PATH', './data/database.json')
    CACHE_PATH = os.getenv('CACHE_PATH', './data/cache.json')
    
    # Логирование
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', './logs/bot.log')
    
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