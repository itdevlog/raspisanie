# handlers/callbacks/admin_callbacks.py
import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from config.schools import SCHOOLS_CONFIG
from core.data_loader import DataLoader
from handlers.common.messaging import log_user_error
from handlers.common.typing import require_message, require_query, require_user
from services.status_service import StatusService, status_icon
from services.text_utils import escape_markdown

# Настройка логгера
admin_logger = logging.getLogger('admin_panel')

class AdminCallbackHandler:
    """Обработчик callback'ов для админ-панели"""

    def __init__(self):
        self._refresh_lock = asyncio.Lock()

    def _updater_lock(self, context: ContextTypes.DEFAULT_TYPE):
        """Общая блокировка обновлений: не даём ручному и фоновому обновлению пересекаться."""
        updater = context.bot_data.get('background_updater')
        lock = getattr(updater, '_update_lock', None) if updater else None
        return lock or self._refresh_lock

    def _invalidate_data(self, context: ContextTypes.DEFAULT_TYPE):
        """Единая инвалидация после ручной замены schools_data."""
        updater = context.bot_data.get('background_updater')
        if updater and hasattr(updater, '_on_data_replaced'):
            updater._on_data_replaced()
        else:
            cache_service = context.bot_data.get('cache_service')
            if cache_service:
                cache_service.clear()
            notification_service = context.bot_data.get('notification_service')
            if notification_service and hasattr(notification_service, 'reset_user_class_index'):
                notification_service.reset_user_class_index()

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает admin_* callback'ы"""
        query = require_query(update)
        user_id = require_user(update).id

        if not self._is_admin(user_id, context):
            await query.answer("❌ Нет прав доступа")
            return

        # Обработка основных действий
        if callback_data == "admin_refresh_panel":
            await query.answer("🔄 Обновляем панель...")
            await self._show_admin_panel(update, context)

        elif callback_data == "admin_refresh_all":
            await query.answer("🔄 Начинаем обновление всех школ...")
            await self._refresh_all_schools(update, context)

        elif callback_data == "admin_force_update":
            await query.answer("⚡ Запускаем принудительное обновление...")
            await self._force_update(update, context)


        elif callback_data.startswith("admin_refresh_school_"):
            school_id = callback_data.replace("admin_refresh_school_", "")
            await query.answer(f"🔄 Обновляем {school_id}...")
            await self._refresh_school(update, context, school_id)

        elif callback_data == "admin_show_users_with_classes":
            await query.answer("📋 Загружаем список пользователей с классами...")
            await self._show_users_with_classes(update, context)

    def _is_admin(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Проверяет, является ли пользователь администратором"""
        from config.config import Config
        config = context.bot_data.get('config')
        return Config.is_admin(config, user_id)

    async def show_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str | None = None):
        """Показывает админ-панель (публичный вход для /admin и callback'ов)"""
        await self._show_admin_panel(update, context, message_text)

    async def _show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статистику пользователей (для /stats)."""
        try:
            user_service = context.bot_data.get('user_service')
            users = user_service.get_users_with_classes() if user_service else []
            total = len(users)
            by_school: dict = {}
            for u in users:
                sid = u.get('current_school', '—')
                by_school[sid] = by_school.get(sid, 0) + 1
            lines = ["📊 *Статистика*\n", f"👥 Пользователей с классами: *{total}*", ""]
            for sid, cnt in sorted(by_school.items()):
                lines.append(f"• {escape_markdown(str(sid))}: {cnt}")
            text = "\n".join(lines)
            if getattr(update, 'callback_query', None):
                await require_query(update).edit_message_text(text, parse_mode='Markdown')
            else:
                msg = update.message
                if msg is not None:
                    await msg.reply_text(text, parse_mode='Markdown')
        except Exception as e:
            error_msg = log_user_error("Failed to show statistics", e)
            if getattr(update, 'callback_query', None):
                await require_query(update).edit_message_text(error_msg)
            else:
                msg = update.message
                if msg is not None:
                    await msg.reply_text(error_msg)

    async def _show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str | None = None):
        """Показывает админ-панель"""
        schools_status = await self._get_schools_status(context)

        # Формируем текст
        text = self._build_admin_panel_text(schools_status, message_text)

        # Создаем клавиатуру
        reply_markup = self._build_admin_keyboard(schools_status)

        try:
            if update.callback_query:
                await self._update_callback_message(update, text, reply_markup)
            else:
                await require_message(update).reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            await self._handle_message_error(update, e)

    def _build_admin_panel_text(self, schools_status: dict, message_text: str | None = None) -> str:
        """Формирует текст админ-панели"""
        text = "⚙️ *Админ-панель*\n\n"

        # Статус школ
        text += "🏫 *Статус школ:*\n"
        for school_id, status in schools_status.items():
            school_config = SCHOOLS_CONFIG.get(school_id, {})
            school_name = school_config.get('name', school_id)

            if status['loaded']:
                icon = status_icon(status)
                text += f"• {icon} {school_name}: {status['details']}\n"
            else:
                text += f"• ❌ {school_name}: Данные не загружены\n"

        if message_text:
            text += f"\n💡 {message_text}"

        return text

    def _build_admin_keyboard(self, schools_status: dict) -> InlineKeyboardMarkup:
        """Создает клавиатуру админ-панели"""
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить все школы", callback_data="admin_refresh_all")],
            [InlineKeyboardButton("⚡ Принудительное обновление", callback_data="admin_force_update")],
            [InlineKeyboardButton("📋 Пользователи с классами", callback_data="admin_show_users_with_classes")],
        ]

        # Кнопки для каждой школы
        for school_id, status in schools_status.items():
            school_config = SCHOOLS_CONFIG.get(school_id, {})
            if school_config.get('active', True):
                school_name = school_config.get('name', school_id)
                button_text = school_name[:15] + "..." if len(school_name) > 15 else school_name
                keyboard.append([
                    InlineKeyboardButton(f"🔄 {button_text}", callback_data=f"admin_refresh_school_{school_id}")
                ])

        keyboard.append([InlineKeyboardButton("🔄 Обновить панель", callback_data="admin_refresh_panel")])

        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    async def _typing_until(chat_id: int, context, coro):
        """Показывает «печатает...» и выполняет coro, периодически подогревая индикатор."""
        import asyncio

        async def _show():
            while not done:
                try:
                    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                except Exception:
                    pass
                await asyncio.sleep(3)

        done = False
        task = asyncio.ensure_future(_show())
        try:
            result = await coro
            return result
        finally:
            done = True
            try:
                task.cancel()
            except Exception:
                pass

    async def _refresh_all_schools(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет данные всех школ"""
        query = require_query(update)
        user_id = require_user(update).id

        if self._updater_lock(context).locked():
            await query.edit_message_text("⏳ Обновление уже выполняется в фоне. Дождитесь завершения.")
            return

        async with self._updater_lock(context):
            await query.edit_message_text("🔄 *Обновление данных всех школ...*\n\nЭто может занять несколько секунд.", parse_mode='Markdown')

            chat_id = update.effective_chat.id if update.effective_chat else None
            loader = DataLoader()
            # Оффлоадим синхронные HTTP-запросы в отдельный поток, чтобы не блокировать event loop
            if chat_id:
                schools_data = await self._typing_until(chat_id, context, asyncio.to_thread(loader.load_all_schools_data))
            else:  # pragma: no cover
                schools_data = await asyncio.to_thread(loader.load_all_schools_data)

            if schools_data:
                merged = context.bot_data.get('schools_data', {})
                updater = context.bot_data.get('background_updater')
                if updater and hasattr(updater, '_merge_schools_data'):
                    merged = updater._merge_schools_data(merged, schools_data)
                else:
                    merged = dict(merged or {})
                    merged.update(schools_data)
                context.bot_data['schools_data'] = merged
                self._invalidate_data(context)
                admin_logger.info(f"Admin {user_id} manually refreshed all schools data")

                total_count = len([s for s in SCHOOLS_CONFIG.values() if s.get('active', True)])
                # Считаем «успешно обновлёнными» только загруженные школы со свежими данными
                status_service = StatusService(schools_data)
                fresh_count = sum(
                    1 for sid in schools_data
                    if "Актуально" in status_service.get_school_status(sid)['status']
                )
                await self._show_admin_panel(
                    update, context,
                    f"✅ Обновлено {fresh_count}/{total_count} школ (свежих данных)"
                )
            else:
                admin_logger.error(f"Admin {user_id} failed to refresh schools data")
                await self._show_admin_panel(update, context, "❌ Не удалось обновить данные школ")

    async def _refresh_school(self, update: Update, context: ContextTypes.DEFAULT_TYPE, school_id: str):
        """Обновляет данные конкретной школы"""
        query = require_query(update)
        user_id = require_user(update).id

        school_config = SCHOOLS_CONFIG.get(school_id)
        if not school_config:
            await query.answer("❌ Школа не найдена")
            return

        if self._updater_lock(context).locked():
            await query.edit_message_text("⏳ Обновление уже выполняется в фоне. Дождитесь завершения.")
            return

        async with self._updater_lock(context):
            school_name = school_config.get('name', school_id)
            await query.edit_message_text(f"🔄 *Обновление данных {school_name}...*", parse_mode='Markdown')

            loader = DataLoader()
            # Оффлоадим синхронный HTTP-запрос в отдельный поток, чтобы не блокировать event loop
            school_data = await asyncio.to_thread(loader.load_school_data, school_config)

            if school_data:
                if 'schools_data' not in context.bot_data:
                    context.bot_data['schools_data'] = {}
                context.bot_data['schools_data'][school_id] = school_data
                self._invalidate_data(context)

                admin_logger.info(f"Admin {user_id} manually refreshed school {school_id}")
                await self._show_admin_panel(update, context, f"✅ {school_name} обновлена")
            else:
                admin_logger.error(f"Admin {user_id} failed to refresh school {school_id}")
                await self._show_admin_panel(update, context, f"❌ Не удалось обновить {school_name}")

    async def _force_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Принудительное обновление данных всех школ"""
        query = require_query(update)
        user_id = require_user(update).id

        await query.edit_message_text("🔄 *Принудительное обновление всех школ...*\n\nЭто может занять несколько минут.", parse_mode='Markdown')

        try:
            # Получаем background_updater из bot_data
            background_updater = context.bot_data.get('background_updater')

            if not background_updater:
                await query.edit_message_text("❌ Сервис фонового обновления не доступен")
                return

            # Выполняем обновление
            chat_id = update.effective_chat.id if update.effective_chat else None
            if chat_id:
                ran = await self._typing_until(
                    chat_id, context, background_updater._perform_update())
            else:  # pragma: no cover
                ran = await background_updater._perform_update()

            if not ran:
                await self._show_admin_panel(
                    update, context,
                    "⏳ Обновление уже выполняется в фоне. Дождитесь завершения."
                )
                return

            # Получаем обновленный статус школ
            schools_status = await self._get_schools_status(context)

            # Формируем сообщение об успехе
            loaded_schools = sum(1 for status in schools_status.values() if status['loaded'])
            total_schools = len(schools_status)

            message_text = f"✅ Принудительное обновление завершено!\nЗагружено школ: {loaded_schools}/{total_schools}"

            await self._show_admin_panel(update, context, message_text)
            admin_logger.info(f"Admin {user_id} executed force update")

        except Exception as e:
            admin_logger.error(f"Admin {user_id} failed force update: {e}")
            error_msg = log_user_error("Admin force update failed", e)

            # Показываем панель с ошибкой
            await self._show_admin_panel(update, context, error_msg)

    async def _get_schools_status(self, context: ContextTypes.DEFAULT_TYPE) -> dict:
        """Получает статус всех школ"""
        schools_data = context.bot_data.get('schools_data', {})
        status_service = StatusService(schools_data)

        schools_status = {}
        for school_id in SCHOOLS_CONFIG.keys():
            schools_status[school_id] = status_service.get_school_status(school_id)

        return schools_status

    async def _update_callback_message(self, update: Update, text: str, reply_markup: InlineKeyboardMarkup):
        """Обновляет сообщение callback"""
        try:
            await require_query(update).edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            if "Message is not modified" in str(e):
                await require_query(update).answer("✅ Панель уже актуальна")
            else:
                admin_logger.error(f"Error updating admin panel: {e}")
                await require_query(update).answer("❌ Ошибка при обновлении")

    async def _handle_message_error(self, update: Update, error: Exception):
        """Обрабатывает ошибки сообщений"""
        if "Message is not modified" in str(error):
            if update.callback_query:
                await require_query(update).answer("✅ Панель уже актуальна")
        else:
            admin_logger.error(f"Error in admin panel: {error}")
            if update.callback_query:
                await require_query(update).answer("❌ Ошибка при обновлении")

    async def _show_users_with_classes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список пользователей с выбранными классами"""
        query = require_query(update)
        user_id = require_user(update).id

        try:
            # Получаем UserService из bot_data
            user_service = context.bot_data.get('user_service')
            if not user_service:
                await query.edit_message_text("❌ Не удалось получить сервис пользователей")
                admin_logger.error(f"Admin {user_id} failed to get user_service")
                return

            # Получаем всех пользователей с классами
            users_with_classes = user_service.get_users_with_classes()
            admin_logger.info(f"Found {len(users_with_classes)} users with classes")

            if not users_with_classes:
                await query.edit_message_text("📋 *Список пользователей с классами пуст*")
                return

            # Формируем сообщение со списком пользователей
            text = f"📋 *Список пользователей с классами* ({len(users_with_classes)}):\n\n"

            for i, user in enumerate(users_with_classes, 1):
                user_id_display = user.get('user_id')
                current_school = user.get('current_school', 'Не указана')
                school_classes = user.get('school_classes', {})

                text += f"{i}. *ID:* `{user_id_display}`\n"
                text += f"   *Текущая школа:* `{current_school}`\n"

                # Показываем каждую школу и соответствующий класс
                if school_classes:
                    for school_id, class_name in school_classes.items():
                        # Извлекаем номер школы из ID (убираем префикс "school_")
                        school_number = school_id.replace("school_", "") if school_id.startswith("school_") else school_id
                        text += f"   *Школа {school_number}:* `{class_name}`\n"
                else:
                    text += "   *Классы:* нет\n"

                text += "\n"

            # Ограничиваем длину сообщения, если оно слишком большое.
            # Режем по границе строки, чтобы не разрывать разметку Markdown
            # (`*...*`/`` `...` ``) — иначе упадёт Can't parse entities.
            if len(text) > 4000:
                cut = text.rfind('\n', 0, 4000)
                if cut == -1:
                    cut = 4000
                text = text[:cut] + "\n... (список обрезан из-за длины)"

            # Создаем клавиатуру с кнопкой возврата в админ-панель
            keyboard = [
                [InlineKeyboardButton("🔙 Назад в админ-панель", callback_data="admin_refresh_panel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
            admin_logger.info(f"Admin {user_id} viewed users with classes list")

        except Exception as e:
            error_msg = log_user_error("Failed to get users with classes", e)
            # Добавляем клавиатуру и для ошибки
            keyboard = [
                [InlineKeyboardButton("🔙 Назад в админ-панель", callback_data="admin_refresh_panel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(error_msg, reply_markup=reply_markup)
            admin_logger.error(f"Admin {user_id} failed to get users with classes: {e}", exc_info=True)
