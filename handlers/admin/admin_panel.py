from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
import logging
from config.schools import SCHOOLS_CONFIG
from services.status_service import StatusService

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

# Callback-обработчики админ-панели (admin_*) обслуживаются НЕ здесь, а классом
# AdminCallbackHandler в handlers/callbacks/admin_callbacks.py: роутер
# CallbackRouter маршрутизирует 'admin' префикс в него. Здесь остаётся только
# живой код для команд /admin и /stats.

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
