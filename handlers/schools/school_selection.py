from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config.schools import SCHOOLS_CONFIG
import logging

logger = logging.getLogger(__name__)

async def school_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора школы"""
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})
    
    if not user_service:
        if update.message:
            await update.message.reply_text("❌ Сервис пользователей не доступен")
        elif update.callback_query:
            await update.callback_query.edit_message_text("❌ Сервис пользователей не доступен")
        return
    
    current_school_id = user_service.get_user_school(user_id)
    
    keyboard = []
    for school_id, school in SCHOOLS_CONFIG.items():
        if school.get('active', True):
            # Проверяем загружены ли данные школы
            is_loaded = school_id in schools_data
            
            # Иконка для текущей школы и статуса загрузки
            if school_id == current_school_id:
                icon = "⭐" if is_loaded else "⚠️"
            else:
                icon = "✅" if is_loaded else "🔴"
            
            button_text = f"{icon} {school['name']} ({school['city']})"
            
            # Для школ без данных делаем кнопку неактивной
            if is_loaded:
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data=f"select_school_{school_id}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data="school_not_loaded")
                ])
    
    # Кнопка отмены (возврат в главное меню)
    keyboard.append([
        InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = (
        "🏫 *Выбор школы*\n\n"
        "Выберите вашу школу из списка:\n"
        "⭐ - ваша текущая школа\n"
        "✅ - доступная школа с данными\n"
        "⚠️ - ваша школа (данные загружаются)\n"
        "🔴 - школа временно не доступна\n\n"
        f"*Загружено школ:* {len(schools_data)}/{len([s for s in SCHOOLS_CONFIG.values() if s.get('active', True)])}"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def handle_school_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, school_id: str):
    """Обрабатывает выбор школы пользователем"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    
    if not user_service:
        await query.edit_message_text("❌ Сервис пользователей не доступен")
        return
    
    # Сохраняем выбранную школу для пользователя
    user_service.set_user_school(user_id, school_id)
    
    # Получаем информацию о школе для подтверждения
    from config.schools import SCHOOLS_CONFIG
    school_info = SCHOOLS_CONFIG.get(school_id, {})
    school_name = school_info.get('name', 'неизвестная школа')
    
    # Логируем изменение
    logger.info(f"Пользователь {user_id} выбрал школу {school_id}")
    
    # Показываем главное меню вместо сообщения с подтверждением
    from handlers.common.main_menu import main_menu_handler
    await main_menu_handler(update, context)