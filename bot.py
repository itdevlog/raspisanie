# File: c:\Users\set\Downloads\telegram-schedule-bot1001\telegram-schedule-bot\bot.py
import asyncio
import logging
import logging.handlers
import os
import socket
import time

from telegram import LinkPreviewOptions, Update
from telegram.ext import (
    AIORateLimiter,
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    InlineQueryHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

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
from handlers.common.typing import require_message, require_user
from handlers.common.week_command import week_command_handler
from handlers.inline_schedule import inline_query_handler

# Импорт обработчиков
from handlers.start import cancel_handler, help_handler, start_handler
from services.alert_service import AlertService
from services.cache_service import CacheService
from services.metrics import MetricsService
from services.notification_service import NotificationService
from services.state_service import UserStateService
from services.user_service import UserService
from web.server import run_webapp, wait_forever


class ScheduleBot:
    def __init__(self):
        self.config = Config()
        self.setup_logging()
        self._init_sentry()

        if not self.config.TELEGRAM_TOKEN:
            raise RuntimeError(
                "TELEGRAM_TOKEN не задан. Укажите его в .env (см. .env.example)"
            )

        # Создаем фоновый обновлятор временно без приложения
        self.background_updater = BackgroundUpdater(None)

        # Создаем приложение бота с post_init и увеличенным таймаутом.
        # connection_pool_size > 1: при обрыве TLS через прокси (fake-IP) один
        # мёртвый сокет не должен блокировать все отправки. TCP keepalive
        # помогает отбрасывать оборванные соединения вместо «залипания» в CLOSE-WAIT.
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=30,
            read_timeout=30,
            write_timeout=30,
            pool_timeout=10,
            socket_options=[
                (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
                (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30),
                (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10),
                (socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3),
            ],
        )
        self.application = Application.builder().token(
            self.config.TELEGRAM_TOKEN
        ).post_init(self._post_init).defaults(
            Defaults(link_preview_options=LinkPreviewOptions(is_disabled=True))
        ).rate_limiter(
            AIORateLimiter(max_retries=3)
        ).request(request).get_updates_request(
            HTTPXRequest(
                connection_pool_size=2,
                connect_timeout=30,
                read_timeout=30,
                write_timeout=30,
                pool_timeout=10,
                socket_options=[
                    (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
                    (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30),
                    (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10),
                    (socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3),
                ],
            )
        ).build()

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

    def _init_sentry(self) -> None:
        """Опциональная инициализация Sentry (T44c).

        Sentry не является обязательной зависимостью: без `SENTRY_DSN` или без
        установленного `sentry_sdk` инициализация молча пропускается. Ошибки
        инициализации не должны мешать запуску бота.
        """
        dsn = os.getenv('SENTRY_DSN', '').strip()
        if not dsn:
            return
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0)
            self.logger.info("✅ Sentry инициализирован")
        except ImportError:
            self.logger.info(
                "SENTRY_DSN задан, но пакет sentry_sdk не установлен — Sentry отключён"
            )
        except Exception as e:
            # Не логируем текст исключения: неверный DSN может попасть в логи.
            self.logger.error("Не удалось инициализировать Sentry: %s", type(e).__name__)

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

        # Алертинг админам о повторяющихся ошибках и метрики рассылок (T44)
        alert_service = AlertService()
        metrics_service = MetricsService()

        # Инициализируем сервис подписок на преподавателей/кабинеты
        from services.subscription_service import SubscriptionService
        subscription_service = SubscriptionService(db)

        # Инициализируем детектор замен - ДОБАВЛЕНО
        from services.exchange_detector import ExchangeDetector
        exchange_detector = ExchangeDetector()

        # Сохраняем в bot_data для доступа из обработчиков
        self.application.bot_data['user_service'] = user_service
        self.application.bot_data['db'] = db
        self.application.bot_data['config'] = self.config
        self.application.bot_data['cache_service'] = cache_service
        self.application.bot_data['notification_service'] = notification_service
        self.application.bot_data['alert_service'] = alert_service
        self.application.bot_data['metrics'] = metrics_service
        self.application.bot_data['subscription_service'] = subscription_service
        self.application.bot_data['schools_config'] = SCHOOLS_CONFIG
        self.application.bot_data['state_service'] = state_service  # ДОБАВЛЕНО
        self.application.bot_data['exchange_detector'] = exchange_detector
        self.application.bot_data['webapp_url'] = self.config.WEBAPP_URL or None

    def load_schools_data(self):
        """Загружает данные для всех активных школ с ретраями начальной загрузки.

        Пустой результат не оставляем до планового цикла обновления (по умолчанию
        час): до 3 попыток с нарастающей паузой (1с, 2с). Частичный результат
        (хотя бы одна школа) считается успехом и не ретраится. Вызывается
        синхронно до старта event loop, поэтому паузы — `time.sleep`; на
        успешном первом проходе задержки нет.
        """
        self.logger.info("Загрузка данных расписания для всех школ...")
        loader = DataLoader()

        max_attempts = 3
        schools_data: dict = {}
        for attempt in range(max_attempts):
            schools_data = loader.load_all_schools_data()
            if schools_data:
                break
            if attempt < max_attempts - 1:
                pause = 2 ** attempt
                self.logger.warning(
                    f"⚠️ Данные расписания не загружены (попытка {attempt + 1}/"
                    f"{max_attempts}), повтор через {pause}с..."
                )
                time.sleep(pause)

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

        # Inline-режим: расписание в любом чате (@bot 9а)
        self.application.add_handler(InlineQueryHandler(inline_query_handler))

        # Глобальная обработка ошибок
        self.application.add_error_handler(self.error_handler)

    async def _alert_admins_on_error(self, context, error) -> None:
        """Best-effort алерт админам при повторяющейся ошибке (T44a).

        Никакие ошибки алертинга не должны утекать в глобальный обработчик.
        В текст попадают только тип ошибки и источник — без сообщения/секретов.
        """
        try:
            bot_data = getattr(context, 'bot_data', None)
            if not bot_data:
                return
            alert_service = bot_data.get('alert_service')
            if not alert_service:
                return
            source = 'update_handler'
            alert_service.record(error, source)
            key = alert_service.error_key(error, source)
            if not alert_service.should_alert(key):
                return
            notification_service = bot_data.get('notification_service')
            if not notification_service:
                return
            error_type = type(error).__name__ if error is not None else 'UnknownError'
            text = (
                "🚨 Повторяющаяся ошибка\n\n"
                f"Тип: {error_type}\n"
                f"Источник: {source}\n"
                f"Повторов за окно: ≥{alert_service.threshold}"
            )
            await notification_service.notify_admins(context, text, parse_mode=None)
        except Exception as e:
            self.logger.error(f"Ошибка алертинга админам: {e}")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Базовая обработка ошибок"""
        try:
            # Логируем ошибку с полным traceback
            self.logger.error(
                f"Exception while handling an update: {context.error}",
                exc_info=context.error
            )

            # Алертим админов при повторяющихся ошибках (best-effort)
            await self._alert_admins_on_error(context, context.error)

            # Уведомление пользователю
            effective_message = getattr(update, 'effective_message', None)
            if effective_message:
                await effective_message.reply_text(GENERIC_ERROR_MSG)

        except Exception as e:
            self.logger.error(f"Error in error handler: {e}")

    async def force_check_exchanges(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Принудительная проверка замен и отправка уведомлений"""
        # Проверяем, является ли пользователь администратором
        user_id = require_user(update).id
        message = require_message(update)
        if not self.config.is_admin(self.config, user_id):
            await message.reply_text("❌ Эта команда доступна только администраторам")
            return

        try:
            await message.reply_text("🔄 Начинаю принудительную проверку замен...")

            # Вызываем метод из background_updater для проверки замен
            await self.background_updater.force_check_exchanges(context)

            await message.reply_text("✅ Проверка замен завершена")
        except Exception as e:
            self.logger.error(f"Error in force_check_exchanges: {e}", exc_info=True)
            await message.reply_text(f"❌ Ошибка при проверке замен: {e}")

    async def _post_init(self, application):
        """Вызывается после старта event loop, но до начала polling"""
        # Уведомляем админов о запуске
        try:
            notification_service = self.application.bot_data.get('notification_service')
            if notification_service:
                await notification_service.notify_bot_started(self.application)
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления о запуске: {e}")

        webapp_url = self.config.WEBAPP_URL
        if webapp_url:
            try:
                from telegram import MenuButtonWebApp, WebAppInfo
                await application.bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(
                        text="🌐 Веб-расписание",
                        web_app=WebAppInfo(url=webapp_url),
                    )
                )
            except Exception as e:
                self.logger.error(f"Ошибка установки MenuButtonWebApp: {e}")

        self.background_updater.start_periodic_updates()

    async def _do_shutdown(self):
        """Выполняет шаги очистки по порядку."""
        if self.application.updater:
            await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        self.background_updater.stop()
        self.logger.info("🛑 Бот остановлен")

    async def _shutdown(self):
        """Гарантирует завершение очистки даже при отмене задачи сигналом.

        При Ctrl+C ``asyncio.run`` отменяет главную задачу, и первый же ``await``
        в ``finally`` прерывается ``CancelledError`` — очистка не доживает до
        конца. Запускаем её отдельной задачей и прикрываем ``shield``: отмена
        приходит в ожидающий ``await``, но сама задача очистки продолжает жить,
        и мы дожидаемся её перед повторным пробросом отмены.
        """
        shutdown = asyncio.create_task(self._do_shutdown())
        try:
            await asyncio.shield(shutdown)
        except asyncio.CancelledError:
            await shutdown
            raise

    async def run_async(self):
        """Запуск бота и веб-сервера в одном event loop (PTB custom startup)."""
        self.setup_handlers()
        self.logger.info("Бот запущен")
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

        await self.application.initialize()

        # PTB сам не вызывает post_init без run_polling/run_webhook —
        # вызываем вручную, иначе не запустятся фоновые обновления и уведомления.
        if self.application.post_init:
            await self.application.post_init(self.application)

        if self.application.updater:
            await self.application.updater.start_polling()
        await self.application.start()

        try:
            if getattr(self.config, 'WEBAPP_PORT', 0):
                await run_webapp(self.application, self.config)
            else:
                await wait_forever()
        finally:
            await self._shutdown()

    def run(self):
        """Запуск бота"""
        asyncio.run(self.run_async())

if __name__ == "__main__":
    # Создаем необходимые директории
    Config.setup_directories()

    # Запускаем бота
    bot = ScheduleBot()
    bot.run()
