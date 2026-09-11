from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from config.schools import SCHOOLS_CONFIG
from services.status_service import StatusService
from handlers.common.messaging import clear_search_flags

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню с инлайн-клавиатурой"""
    clear_search_flags(context)
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')

    schools_data = context.bot_data.get('schools_data', {})
    
    # Получаем текущую школу и класс пользователя
    current_school_id = user_service.get_user_school(user_id) if user_service else None
    current_school_name = "Не выбрана"
    current_class = user_service.get_current_class(user_id) if user_service else None
    
    # Получаем статус данных
    status_service = StatusService(schools_data)
    school_status = status_service.get_school_status(current_school_id) if current_school_id else None
    
    if user_service and current_school_id:
        school_config = None
        for school in SCHOOLS_CONFIG.values():
            if school['id'] == current_school_id:
                school_config = school
                break
        if school_config:
            current_school_name = school_config['name']
    
    # Создаем клавиатуру в зависимости от того, выбран ли класс
    keyboard = []
    
    if current_class:
        # Меню когда класс выбран
        keyboard.extend([
            [
                InlineKeyboardButton(f"📅 {current_class} - Сегодня", callback_data=f"class_today_{current_class}"),
                InlineKeyboardButton(f"📆 {current_class} - Завтра", callback_data=f"class_tomorrow_{current_class}"),
                InlineKeyboardButton(f"🗓️ {current_class} - Неделя", callback_data=f"class_week_{current_class}")
            ],
            [
                InlineKeyboardButton("👨‍🏫 Преподаватель", callback_data="menu_teacher"),
                InlineKeyboardButton("🏫 Кабинеты", callback_data="menu_room")
            ],
            [
                InlineKeyboardButton("🔄 Сменить класс", callback_data="change_class"),
                InlineKeyboardButton("🏫 Сменить школу", callback_data="menu_change_school")
            ],
            [
                InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help"),
                InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings"),
                InlineKeyboardButton("🏫 О школе", callback_data="menu_school_info")
            ]
        ])
    else:
        # Меню когда класс не выбран
        keyboard.extend([
            [
                InlineKeyboardButton("📅 Сегодня", callback_data="menu_today"),
                InlineKeyboardButton("📆 Завтра", callback_data="menu_tomorrow"),
                InlineKeyboardButton("🗓️ Неделя", callback_data="menu_week")           
            ],
            [

                InlineKeyboardButton("👨‍🏫 Преподаватель", callback_data="menu_teacher"),
                InlineKeyboardButton("🏫 Кабинеты", callback_data="menu_room"),
                InlineKeyboardButton("🏫 Сменить школу", callback_data="menu_change_school")
            ],
            [
                InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help"),
                InlineKeyboardButton("🏫 О школе", callback_data="menu_school_info")
            ]
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Формируем текст с учетом статуса данных
    text = f"🏠 *Главное меню*\n\n"
    text += f"🏫 Текущая школа: *{current_school_name}*\n"
    
    # Добавляем статус данных, если школа выбрана
    if current_school_id and school_status:
        if school_status['loaded']:
            status_icon = "✅" if "Актуально" in school_status['status'] else "⚠️"
            text += f"📊 Статус: {status_icon} {school_status['details']}\n"
        else:
            text += f"📊 Статус: ❌ Данные не загружены\n"
    
    if current_class:
        text += f"📚 Текущий класс: *{current_class}*\n\n"
    else:
        text += f"\n"
    
    text += f"Выберите нужный пункт:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        query = update.callback_query
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except BadRequest as e:
            if "not modified" not in str(e).lower():
                raise