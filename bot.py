# File: c:\Users\set\Downloads\telegram-schedule-bot1001\telegram-schedule-bot\bot.py
import logging
import logging.handlers

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config.config import Config
from config.schools import SCHOOLS_CONFIG, get_display_name
from core.background_updater import BackgroundUpdater
from core.data_loader import DataLoader
from database.file_db import FileDB
from handlers.admin.admin_panel import setup_admin_handlers
from handlers.common.callback_handler import callback_handler
from handlers.common.class_schedule import class_schedule_handler
from handlers.common.messaging import GENERIC_ERROR_MSG
from handlers.common.school_info import school_info_handler
from handlers.common.settings import settings_handler
from handlers.common.status import status_handler
from handlers.common.week_command import week_command_handler

# Импорт обработчиков
from handlers.start import cancel_handler, help_handler, start_handler
from services.cache_service import CacheService
from services.notification_service import NotificationService
from services.state_service import UserStateService
from services.user_service import UserService


class ScheduleBot:
    def __init__(self):
        self.config = Config()
        self.setup_logging()

        if not self.config.TELEGRAM_TOKEN:
            raise RuntimeError(
                "TELEGRAM_TOKEN не задан. Укажите его в .env (см. .env.example)"
            )

        # Создаем фоновый обновлятор временно без приложения
        self.background_updater = BackgroundUpdater(None)

        # Создаем приложение бота с post_init и увеличенным таймаутом
        self.application = Application.builder().token(
            self.config.TELEGRAM_TOKEN
        ).post_init(self._post_init).connect_timeout(30).read_timeout(30).write_timeout(30).build()

        # Подключаем приложение к обновлятору
        self.background_updater.application = self.application
        self.application.bot_data['background_updater'] = self.background_updater

        # Инициализируем базу данных и сервисы
        self.setup_services()

        # Загружаем данные при старте
        self.load_schools_data()

    def setup_logging(self):
        """Настройка логирования: ротация файла + вывод в консоль.

        Раньше `basicConfig(filename=...)` писал ВЕСЬ вывод только в файл
        (под systemd в консоли ничего не видно) и файл рос бесконечно. Теперь:
          - RotatingFileHandler (1 файл x 5 МБ, ротация до 3 бэкапов) — файл не растёт без предела;
          - StreamHandler — лог и в консоль/журнал systemd.
        httpx гонит в debug URL'ы с токеном бота — приглушаем его до WARNING.
        """
        level = getattr(logging, self.config.LOG_LEVEL, logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        file_handler = logging.handlers.RotatingFileHandler(
            self.config.LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        root = logging.getLogger()
        root.handlers = [file_handler, console_handler]
        root.setLevel(level)

        # Отдельный файл для действий администраторов (admin_logger, имя 'admin_panel').
        # Раньше ADMIN_LOG_FILE был объявлен в конфиге, но нигде не использовался.
        admin_handler = logging.handlers.RotatingFileHandler(
            self.config.ADMIN_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8'
        )
        admin_handler.setFormatter(formatter)
        admin_handler.setLevel(level)
        admin_logger = logging.getLogger('admin_panel')
        admin_logger.handlers = [admin_handler]
        admin_logger.propagate = False

        # Не писать URL-ы запросов (содержат TELEGRAM_TOKEN) в debug-лог httpx
        logging.getLogger('httpx').setLevel(logging.WARNING)

        self.logger = logging.getLogger(__name__)

    def setup_services(self):
        """Инициализирует сервисы и базу данных"""
        # Инициализируем базу данных
        db = FileDB(self.config.DB_PATH)

        # Инициализируем сервис кэширования расписания (короткий TTL, инвалидируется при обновлении)
        cache_service = CacheService(ttl=600)  # 10 минут TTL

        # Отдельный кэш состояния пользователей: списки (учителя/кабинеты/классы)
        # должны жить долго, иначе индексные кнопки «протухают» и становятся мёртвыми.
        # Он НЕ инвалидируется вместе с расписанием.
        state_cache_service = CacheService(ttl=24 * 60 * 60)  # 24 часа

        # Инициализируем сервис состояния пользователей (на своём долгом кэше)
        state_service = UserStateService(state_cache_service)

        # Инициализируем сервис пользователей
        user_service = UserService(db)

        # Инициализируем сервис уведомлений
        notification_service = NotificationService()

        # Инициализируем детектор замен - ДОБАВЛЕНО
        from services.exchange_detector import ExchangeDetector
        exchange_detector = ExchangeDetector()

        # Сохраняем в bot_data для доступа из обработчиков
        self.application.bot_data['user_service'] = user_service
        self.application.bot_data['db'] = db
        self.application.bot_data['config'] = self.config
        self.application.bot_data['cache_service'] = cache_service
        self.application.bot_data['notification_service'] = notification_service
        self.application.bot_data['schools_config'] = SCHOOLS_CONFIG
        self.application.bot_data['state_service'] = state_service  # ДОБАВЛЕНО
        self.application.bot_data['exchange_detector'] = exchange_detector

    def load_schools_data(self):
        """Загружает данные для всех активных школ"""
        self.logger.info("Загрузка данных расписания для всех школ...")
        loader = DataLoader()

        # Загружаем данные для всех активных школ
        schools_data = loader.load_all_schools_data()

        if schools_data:
            self.application.bot_data['schools_data'] = schools_data
            self.logger.info("✅ Данные расписания успешно загружены!")

            for school_id, school_data in schools_data.items():
                school_name = get_display_name(school_id, school_data)
                self.logger.info(f"• {school_name} - Загружено")
        else:
            self.logger.error("❌ Не удалось загрузить данные расписания")
            self.application.bot_data['schools_data'] = {}

    def setup_handlers(self):
        # Команды
        self.application.add_handler(CommandHandler("start", start_handler))
        self.application.add_handler(CommandHandler("cancel", cancel_handler))
        self.application.add_handler(CommandHandler("help", help_handler))
        self.application.add_handler(CommandHandler("status", status_handler))
        self.application.add_handler(CommandHandler("settings", settings_handler))
        self.application.add_handler(CommandHandler("week", week_command_handler))
        self.application.add_handler(CommandHandler("school", school_info_handler))

        # Админ-команды
        # Регистрация происходит в setup_admin_handlers
        # self.application.add_handler(CommandHandler("admin", admin_panel_handler))
        # self.application.add_handler(CommandHandler("stats", admin_panel_handler))
        # Команда для принудительной проверки уведомлений
        self.application.add_handler(CommandHandler("check_exchanges", self.force_check_exchanges))

        # Установка админ-обработчиков
        setup_admin_handlers(self.application)

        # Обработчик callback-ов от инлайн-кнопок (включая админ-панель)
        self.application.add_handler(CallbackQueryHandler(callback_handler))

        # Обработчик текстовых сообщений
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            class_schedule_handler
        ))

        # Глобальная обработка ошибок
        self.application.add_error_handler(self.error_handler)

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Базовая обработка ошибок"""
        try:
            # Логируем ошибку с полным traceback
            self.logger.error(
                f"Exception while handling an update: {context.error}",
                exc_info=context.error
            )

            # Уведомление пользователю
            if update and update.effective_message:
                await update.effective_message.reply_text(GENERIC_ERROR_MSG)

        except Exception as e:
            self.logger.error(f"Error in error handler: {e}")

    async def force_check_exchanges(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Принудительная проверка замен и отправка уведомлений"""
        # Проверяем, является ли пользователь администратором
        user_id = update.effective_user.id
        if not self.config.is_admin(self.config, user_id):
            await update.message.reply_text("❌ Эта команда доступна только администраторам")
            return

        try:
            await update.message.reply_text("🔄 Начинаю принудительную проверку замен...")

            # Вызываем метод из background_updater для проверки замен
            await self.background_updater.force_check_exchanges(context)

            await update.message.reply_text("✅ Проверка замен завершена")
        except Exception as e:
            self.logger.error(f"Error in force_check_exchanges: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка при проверке замен: {e}")

    async def _post_init(self, application):
        """Вызывается после старта event loop, но до начала polling"""
        # Уведомляем админов о запуске
        try:
            notification_service = self.application.bot_data.get('notification_service')
            if notification_service:
                await notification_service.notify_bot_started(self.application)
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления о запуске: {e}")

        self.background_updater.start_periodic_updates()

    def run(self):
        """Запуск бота"""
        self.setup_handlers()
        self.logger.info("Бот запущен")

        # Запускаем polling
        self.logger.info("✅ Бот запущен! Остановите сочетанием Ctrl+C")
        self.logger.info("📝 Доступные команды:")
        self.logger.info("   /start - Главное меню (основная команда)")
        self.logger.info("   /help - Помощь")
        self.logger.info("   /week <класс> - Расписание на неделю")
        self.logger.info("   /school - Информация о школе")
        self.logger.info("🏫 Доступные школы:")
        for school in SCHOOLS_CONFIG.values():
            if school.get('active', True):
                status = "✅" if school['id'] in self.application.bot_data.get('schools_data', {}) else "❌"
                self.logger.info(f"   {status} {school['name']} ({school['city']})")

        # ЗАПУСКАЕМ POLLING
        try:
            self.application.run_polling(
                stop_signals=None  # обрабатываем KeyboardInterrupt ниже
            )
        except KeyboardInterrupt:
            self.logger.info("🛑 Остановка бота...")
        finally:
            # Останавливаем фоновое обновление при выходе
            self.background_updater.stop()

if __name__ == "__main__":
    # Создаем необходимые директории
    Config.setup_directories()

    # Запускаем бота
    bot = ScheduleBot()
    bot.run()
