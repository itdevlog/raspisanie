from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.config import Config
from services.text_utils import escape_markdown


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
    is_admin = Config.is_admin(config, user_id)

    # Создаем клавиатуру с настройками
    keyboard = [
        [
            InlineKeyboardButton(
                f"🔔 Уведомления: {'✅ Вкл' if notifications_enabled else '❌ Выкл'}",
                callback_data=f"toggle_notifications_{'off' if notifications_enabled else 'on'}"
            )
        ]
    ]

    # Подписки на преподавателей/кабинеты текущей школы
    subscription_service = context.bot_data.get('subscription_service')
    subscriptions = []
    if subscription_service:
        school_id = user_service.get_user_school(user_id)
        subscriptions = subscription_service.get_subscriptions(user_id, school_id)
        for index, (kind, name) in enumerate(subscriptions):
            label_kind = "👨‍🏫" if kind == 'teacher' else "🏫"
            keyboard.append([
                InlineKeyboardButton(
                    f"{label_kind} {name} — 🔕 Отписаться",
                    callback_data=f"unsubscribe_{kind}_{index}"
                )
            ])

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

    text = "⚙️ *Настройки*\n\n"
    if subscriptions:
        text += "🔔 *Ваши подписки:*\n"
        for kind, name in subscriptions:
            label_kind = "👨‍🏫" if kind == 'teacher' else "🏫"
            text += f"• {label_kind} {escape_markdown(name)}\n"
        text += "\n"
    text += "Выберите параметр для изменения:"

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query:
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')


async def unsubscribe_by_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """Отписывает по callback `unsubscribe_{kind}_{index}` и обновляет меню."""
    query = update.callback_query
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    subscription_service = context.bot_data.get('subscription_service')

    if not user_service or not subscription_service:
        await query.answer("❌ Сервис подписок не доступен")
        return

    parts = payload.split('_', 1)
    if len(parts) != 2 or not parts[1].isdigit():
        await query.answer("❌ Ошибка в данных подписки")
        return

    kind = parts[0]
    index = int(parts[1])
    school_id = user_service.get_user_school(user_id)
    subscriptions = subscription_service.get_subscriptions(user_id, school_id)

    if not (0 <= index < len(subscriptions)):
        await query.answer("❌ Подписка не найдена")
        return

    sub_kind, name = subscriptions[index]
    if sub_kind != kind:
        await query.answer("❌ Подписка не найдена")
        return

    subscription_service.unsubscribe(user_id, school_id, kind, name)
    await query.answer(f"🔕 Отписка от {name} оформлена")
    await settings_handler(update, context)


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
    is_admin = Config.is_admin(config, user_id)

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
