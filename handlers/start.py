from telegram import Update
from telegram.ext import ContextTypes

from handlers.common.menu_builder import (
    HELP_TEXT,
    build_help_keyboard,
    build_main_menu_keyboard,
    build_main_menu_text,
)
from handlers.common.messaging import reset_user_flow
from services.status_service import StatusService


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start - показывает главное меню"""
    reset_user_flow(context)
    user = update.effective_user
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})

    # Приветственное сообщение
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для просмотра школьного расписания.\n\n"
        "🎯 *С чего начать:*\n"
        "1. Выберите школу\n"
        "2. Выберите класс через любое расписание\n"
        "3. Получайте расписание с заменами 🔄\n\n"
        "💡 *Быстрый доступ:*\n"
        "• Ваш класс сохраняется автоматически\n"
        "• Расписание обновляется каждый час\n\n"
        "👇 *Выберите нужный пункт ниже:*"
    )

    # Получаем текущую школу и класс пользователя
    current_school_id = user_service.get_user_school(user.id) if user_service else None
    current_class = user_service.get_current_class(user.id) if user_service else None

    # Получаем статус данных
    status_service = StatusService(schools_data)
    school_status = status_service.get_school_status(current_school_id) if current_school_id else None

    reply_markup = build_main_menu_keyboard(current_class)
    text = build_main_menu_text(school_status, current_school_id, current_class, welcome=welcome_text)

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает текущее действие и возвращает в главное меню."""
    reset_user_flow(context)
    await start_handler(update, context)

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help - показывает справку"""
    reply_markup = build_help_keyboard()
    await update.message.reply_text(HELP_TEXT, reply_markup=reply_markup, parse_mode='Markdown')
