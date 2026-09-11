from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
import asyncio
import logging
from config.schools import SCHOOLS_CONFIG
from services.status_service import StatusService
from core.data_loader import DataLoader

# Настройка логгера
admin_logger = logging.getLogger('admin_panel')

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Главная админ-панель"""
    user_id = update.effective_user.id
    
    if not _is_admin(user_id, context):
        await update.message.reply_text("❌ У вас нет прав доступа к админ-панели")
        return
    
    await _show_admin_panel(update, context)

async def _show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = None):
    """Показывает админ-панель"""
    schools_status = await _get_schools_status(context)
    
    # Формируем текст
    text = _build_admin_panel_text(schools_status, message_text)
    
    # Создаем клавиатуру
    reply_markup = _build_admin_keyboard(schools_status)
    
    try:
        if update.callback_query:
            await _update_callback_message(update, text, reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        await _handle_message_error(update, e)

def _build_admin_panel_text(schools_status: dict, message_text: str = None) -> str:
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

def _build_admin_keyboard(schools_status: dict) -> InlineKeyboardMarkup:
    """Создает клавиатуру админ-панели"""
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить все школы", callback_data="admin_refresh_all")],
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

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает callback-и админ-панели"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not _is_admin(user_id, context):
        await query.answer("❌ Нет прав доступа")
        return
    
    callback_data = query.data
    
    # Добавьте этот обработчик
    if callback_data == "admin_force_update":
        await query.answer("🔄 Принудительное обновление...")
        await _force_update(update, context)
    
    # Обработка основных действий
    if callback_data == "admin_refresh_panel":
        await query.answer("🔄 Обновляем панель...")
        await _show_admin_panel(update, context)
    
    elif callback_data == "admin_refresh_all":
        await query.answer("🔄 Начинаем обновление всех школ...")
        await _refresh_all_schools(update, context)
    
    elif callback_data.startswith("admin_refresh_school_"):
        school_id = callback_data.replace("admin_refresh_school_", "")
        await query.answer(f"🔄 Обновляем {school_id}...")
        await _refresh_school(update, context, school_id)
    
    elif callback_data == "admin_show_users_with_classes":
        await query.answer("📋 Загружаем список пользователей с классами...")
        await _show_users_with_classes(update, context)
    
    

async def _force_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        schools_status = await _get_schools_status(context)
        
        # Формируем сообщение об успехе
        loaded_schools = sum(1 for status in schools_status.values() if status['loaded'])
        total_schools = len(schools_status)
        
        message_text = f"✅ Принудительное обновление завершено!\nЗагружено школ: {loaded_schools}/{total_schools}"
        
        await _show_admin_panel(update, context, message_text)
        admin_logger.info(f"Admin {user_id} executed force update")
        
    except Exception as e:
        error_msg = f"❌ Ошибка при принудительном обновлении: {str(e)}"
        await query.edit_message_text(error_msg)
        admin_logger.error(f"Admin {user_id} failed force update: {e}")
        
        # Показываем панель с ошибкой
        await _show_admin_panel(update, context, f"Ошибка: {str(e)}")

async def _refresh_all_schools(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        
        await _show_admin_panel(update, context, f"✅ Обновлено {success_count}/{total_count} школ")
    else:
        admin_logger.error(f"Admin {user_id} failed to refresh schools data")
        await _show_admin_panel(update, context, "❌ Не удалось обновить данные школ")

async def _refresh_school(update: Update, context: ContextTypes.DEFAULT_TYPE, school_id: str):
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
        await _show_admin_panel(update, context, f"✅ {school_name} обновлена")
    else:
        admin_logger.error(f"Admin {user_id} failed to refresh school {school_id}")
        await _show_admin_panel(update, context, f"❌ Не удалось обновить {school_name}")

async def _get_schools_status(context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Получает статус всех школ"""
    schools_data = context.bot_data.get('schools_data', {})
    status_service = StatusService(schools_data)
    
    schools_status = {}
    for school_id in SCHOOLS_CONFIG.keys():
        schools_status[school_id] = status_service.get_school_status(school_id)
    
    return schools_status

async def _update_callback_message(update: Update, text: str, reply_markup: InlineKeyboardMarkup):
    """Обновляет сообщение callback"""
    try:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        if "Message is not modified" in str(e):
            await update.callback_query.answer("✅ Панель уже актуальна")
        else:
            admin_logger.error(f"Error updating admin panel: {e}")
            await update.callback_query.answer("❌ Ошибка при обновлении")
    
async def _handle_message_error(update: Update, error: Exception):
    """Обрабатывает ошибки сообщений"""
    if "Message is not modified" in str(error):
        if update.callback_query:
            await update.callback_query.answer("✅ Панель уже актуальна")
    else:
        admin_logger.error(f"Error in admin panel: {error}")
        if update.callback_query:
            await update.callback_query.answer("❌ Ошибка при обновлении")

async def _show_users_with_classes(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                    text += f"   *Школа {school_id}:* `{class_name}`\n"
            else:
                text += f"   *Классы:* нет\n"
            
            text += "\n"
        
        # Ограничиваем длину сообщения, если оно слишком большое
        if len(text) > 4000:
            text = text[:4000] + "\n... (список обрезан из-за длины)"
        
        await query.edit_message_text(text, parse_mode='Markdown')
        admin_logger.info(f"Admin {user_id} viewed users with classes list")
        
    except Exception as e:
        error_msg = f"❌ Ошибка при получении списка пользователей: {str(e)}"
        await query.edit_message_text(error_msg)
        admin_logger.error(f"Admin {user_id} failed to get users with classes: {e}", exc_info=True)



def _is_admin(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, является ли пользователь администратором"""
    config = context.bot_data.get('config')
    if config and hasattr(config, 'ADMIN_IDS'):
        return user_id in config.ADMIN_IDS
    return False


# Регистрация обработчиков
def setup_admin_handlers(application):
    """Регистрирует обработчики админ-панели"""
    application.add_handler(CommandHandler("admin", admin_panel_handler))
    application.add_handler(CommandHandler("stats", admin_panel_handler))
