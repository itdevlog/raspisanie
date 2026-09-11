# handlers/callbacks/admin_callbacks.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import asyncio
import logging
from config.schools import SCHOOLS_CONFIG
from services.status_service import StatusService
from core.data_loader import DataLoader

# Настройка логгера
admin_logger = logging.getLogger('admin_panel')

class AdminCallbackHandler:
    """Обработчик callback'ов для админ-панели"""
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает admin_* callback'ы"""
        query = update.callback_query
        user_id = update.effective_user.id
        
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
        config = context.bot_data.get('config')
        if config and hasattr(config, 'ADMIN_IDS'):
            return user_id in config.ADMIN_IDS
        return False

    async def _show_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = None):
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
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            await self._handle_message_error(update, e)

    def _build_admin_panel_text(self, schools_status: dict, message_text: str = None) -> str:
        """Формирует текст админ-панели"""
        text = "⚙️ *Админ-панель*\n\n"
        
        # Статус школ
        text += f"🏫 *Статус школ:*\n"
        for school_id, status in schools_status.items():
            school_config = SCHOOLS_CONFIG.get(school_id, {})
            school_name = school_config.get('name', school_id)
            
            if status['loaded']:
                icon = "✅" if "Актуально" in status['status'] else "⚠️"
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

    async def _refresh_all_schools(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет данные всех школ"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text("🔄 *Обновление данных всех школ...*\n\nЭто может занять несколько секунд.", parse_mode='Markdown')

        loader = DataLoader()
        # Оффлоадим синхронные HTTP-запросы в отдельный поток, чтобы не блокировать event loop
        schools_data = await asyncio.to_thread(loader.load_all_schools_data)
        
        if schools_data:
            context.bot_data['schools_data'] = schools_data
            admin_logger.info(f"Admin {user_id} manually refreshed all schools data")
            
            success_count = len(schools_data)
            total_count = len([s for s in SCHOOLS_CONFIG.values() if s.get('active', True)])
            
            await self._show_admin_panel(update, context, f"✅ Обновлено {success_count}/{total_count} школ")
        else:
            admin_logger.error(f"Admin {user_id} failed to refresh schools data")
            await self._show_admin_panel(update, context, "❌ Не удалось обновить данные школ")

    async def _refresh_school(self, update: Update, context: ContextTypes.DEFAULT_TYPE, school_id: str):
        """Обновляет данные конкретной школы"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        school_config = SCHOOLS_CONFIG.get(school_id)
        if not school_config:
            await query.answer("❌ Школа не найдена")
            return
        
        school_name = school_config.get('name', school_id)
        await query.edit_message_text(f"🔄 *Обновление данных {school_name}...*", parse_mode='Markdown')

        loader = DataLoader()
        # Оффлоадим синхронный HTTP-запрос в отдельный поток, чтобы не блокировать event loop
        school_data = await asyncio.to_thread(loader.load_school_data, school_config)
        
        if school_data:
            if 'schools_data' not in context.bot_data:
                context.bot_data['schools_data'] = {}
            context.bot_data['schools_data'][school_id] = school_data
            
            admin_logger.info(f"Admin {user_id} manually refreshed school {school_id}")
            await self._show_admin_panel(update, context, f"✅ {school_name} обновлена")
        else:
            admin_logger.error(f"Admin {user_id} failed to refresh school {school_id}")
            await self._show_admin_panel(update, context, f"❌ Не удалось обновить {school_name}")

    async def _force_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Принудительное обновление данных всех школ"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        await query.edit_message_text("🔄 *Принудительное обновление всех школ...*\n\nЭто может занять несколько минут.", parse_mode='Markdown')
        
        try:
            # Получаем background_updater из bot_data
            background_updater = context.bot_data.get('background_updater')
            
            if not background_updater:
                await query.edit_message_text("❌ Сервис фонового обновления не доступен")
                return
            
            # Выполняем обновление
            await background_updater._perform_update()
            
            # Получаем обновленный статус школ
            schools_status = await self._get_schools_status(context)
            
            # Формируем сообщение об успехе
            loaded_schools = sum(1 for status in schools_status.values() if status['loaded'])
            total_schools = len(schools_status)
            
            message_text = f"✅ Принудительное обновление завершено!\nЗагружено школ: {loaded_schools}/{total_schools}"
            
            await self._show_admin_panel(update, context, message_text)
            admin_logger.info(f"Admin {user_id} executed force update")
            
        except Exception as e:
            error_msg = f"❌ Ошибка при принудительном обновлении: {str(e)}"
            await query.edit_message_text(error_msg)
            admin_logger.error(f"Admin {user_id} failed force update: {e}")
            
            # Показываем панель с ошибкой
            await self._show_admin_panel(update, context, f"Ошибка: {str(e)}")

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
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            if "Message is not modified" in str(e):
                await update.callback_query.answer("✅ Панель уже актуальна")
            else:
                admin_logger.error(f"Error updating admin panel: {e}")
                await update.callback_query.answer("❌ Ошибка при обновлении")

    async def _handle_message_error(self, update: Update, error: Exception):
        """Обрабатывает ошибки сообщений"""
        if "Message is not modified" in str(error):
            if update.callback_query:
                await update.callback_query.answer("✅ Панель уже актуальна")
        else:
            admin_logger.error(f"Error in admin panel: {error}")
            if update.callback_query:
                await update.callback_query.answer("❌ Ошибка при обновлении")
    
    async def _show_users_with_classes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список пользователей с выбранными классами"""
        query = update.callback_query
        user_id = update.effective_user.id
        
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
                    text += f"   *Классы:* нет\n"
                
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
            error_msg = f"❌ Ошибка при получении списка пользователей: {str(e)}"
            # Добавляем клавиатуру и для ошибки
            keyboard = [
                [InlineKeyboardButton("🔙 Назад в админ-панель", callback_data="admin_refresh_panel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(error_msg, reply_markup=reply_markup)
            admin_logger.error(f"Admin {user_id} failed to get users with classes: {e}", exc_info=True)
    