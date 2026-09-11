from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню настроек"""
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    config = context.bot_data.get('config')
    
    if not user_service:
        if update.message:
            await update.message.reply_text("❌ Сервис не доступен")
        elif update.callback_query:
            query = update.callback_query
            await query.edit_message_text("❌ Сервис не доступен")
        return
    
    # Получаем текущие настройки уведомлений
    notifications_enabled = user_service.get_user_notification_settings(user_id)
    
    # Проверяем, является ли пользователь администратором
    is_admin = config and hasattr(config, 'ADMIN_IDS') and user_id in config.ADMIN_IDS
    
    # Создаем клавиатуру с настройками
    keyboard = [
        [
            InlineKeyboardButton(
                f"🔔 Уведомления: {'✅ Вкл' if notifications_enabled else '❌ Выкл'}",
                callback_data=f"toggle_notifications_{'off' if notifications_enabled else 'on'}"
            )
        ]
    ]
    
    # Если пользователь администратор, добавляем настройки уведомлений об обновлениях
    if is_admin:
        # Получаем настройки уведомлений об обновлениях
        from services.user_preferences import UserPreferencesService
        preferences_service = UserPreferencesService(user_service.db)
        admin_notifications = preferences_service.get_notification_settings(user_id)
        update_notifications_enabled = admin_notifications.get('update_notifications', False)
        
        keyboard.append([
            InlineKeyboardButton(
                f"🔄 Уведомления об обновлениях: {'✅ Вкл' if update_notifications_enabled else '❌ Выкл'}",
                callback_data=f"toggle_update_notifications_{'off' if update_notifications_enabled else 'on'}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "⚙️ *Настройки*\n\nВыберите параметр для изменения:"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
    """Переключает настройки уведомлений"""
    query = update.callback_query
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    
    if not user_service:
        await query.answer("❌ Сервис не доступен")
        return
    
    # Устанавливаем новые настройки
    notifications_enabled = state == 'on'
    user_service.set_user_notification_settings(user_id, notifications_enabled)
    
    # Подтверждение пользователю
    status_text = "включены" if notifications_enabled else "отключены"
    await query.answer(f"🔔 Уведомления {status_text}")
    
    # Обновляем меню настроек
    await settings_handler(update, context)


async def toggle_update_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
    """Переключает настройки уведомлений об обновлениях для администратора"""
    query = update.callback_query
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    
    if not user_service:
        await query.answer("❌ Сервис не доступен")
        return
    
    # Проверяем, является ли пользователь администратором
    config = context.bot_data.get('config')
    is_admin = config and hasattr(config, 'ADMIN_IDS') and user_id in config.ADMIN_IDS
    
    if not is_admin:
        await query.answer("❌ Только администраторы могут изменять эти настройки")
        return
    
    # Используем UserPreferencesService для изменения настроек
    from services.user_preferences import UserPreferencesService
    preferences_service = UserPreferencesService(user_service.db)
    
    # Устанавливаем новые настройки
    if state == 'on':
        preferences_service.enable_update_notifications(user_id)
        status_text = "включены"
    else:
        preferences_service.disable_update_notifications(user_id)
        status_text = "отключены"
    
    # Подтверждение пользователю
    await query.answer(f"🔄 Уведомления об обновлениях {status_text}")
    
    # Обновляем меню настроек
    await settings_handler(update, context)