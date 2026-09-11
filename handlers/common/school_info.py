from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler
from config.schools import get_display_name
from handlers.common.messaging import safe_edit_message
from handlers.common.requires_school import requires_school

@requires_school
async def school_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о школе и данных"""
    school_data = context.school_data
    current_school_id = context.current_school_id
    school_name = get_display_name(current_school_id, school_data)
    city = school_data.get('CITY_NAME', 'Неизвестно')
    export_date = school_data.get('EXPORT_DATE', 'Неизвестно')
    export_time = school_data.get('EXPORT_TIME', 'Неизвестно')
    
    # Статистика
    classes_count = len(school_data.get('CLASSES', {}))
    teachers_count = len(school_data.get('TEACHERS', {}))
    subjects_count = len(school_data.get('SUBJECTS', {}))
    rooms_count = len(school_data.get('ROOMS', {}))
    
    info_text = (
        f"🏫 *{school_name}*\n"
        f"📍 {city}\n\n"
        f"📊 *Статистика:*\n"
        f"• Классов: {classes_count}\n"
        f"• Преподавателей: {teachers_count}\n"
        f"• Предметов: {subjects_count}\n"
        f"• Кабинетов: {rooms_count}\n\n"
        f"🕒 *Данные обновлены:*\n"
        f"{export_date} {export_time}\n\n"
        f"🔗 *Сайт школы:*\n"
        f"{school_data.get('HOMEPAGE_URL', 'Не указан')}"
    )
    
    # Создаем клавиатуру только для callback (в команде /school не нужна)
    if update.callback_query:
        keyboard = [
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await safe_edit_message(update.callback_query, info_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(info_text, parse_mode='Markdown')