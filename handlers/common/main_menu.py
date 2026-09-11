from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from handlers.common.menu_builder import build_main_menu_keyboard, build_main_menu_text
from handlers.common.messaging import clear_search_flags
from services.status_service import StatusService


async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает главное меню с инлайн-клавиатурой"""
    clear_search_flags(context)
    context.user_data.pop('class_digit', None)
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')

    schools_data = context.bot_data.get('schools_data', {})

    # Получаем текущую школу и класс пользователя
    current_school_id = user_service.get_user_school(user_id) if user_service else None
    current_class = user_service.get_current_class(user_id) if user_service else None

    # Получаем статус данных
    status_service = StatusService(schools_data)
    school_status = status_service.get_school_status(current_school_id) if current_school_id else None

    reply_markup = build_main_menu_keyboard(current_class)
    text = build_main_menu_text(school_status, current_school_id, current_class)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        query = update.callback_query
        try:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except BadRequest as e:
            if "not modified" not in str(e).lower():
                raise
