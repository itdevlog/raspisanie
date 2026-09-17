from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.config import Config
from handlers.common.typing import require_query, require_user
from services.text_utils import escape_markdown
from services.user_preferences import UserPreferencesService
from web.auth import generate_widget_token


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню настроек"""
    user_id = require_user(update).id
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

    # Напоминания об уроках и тихие часы — доступны всем пользователям
    preferences_service = UserPreferencesService(user_service.db)
    user_notification_settings = preferences_service.get_notification_settings(user_id)
    lesson_reminders_enabled = user_notification_settings.get('lesson_reminders', False)
    daily_digest_enabled = user_notification_settings.get('daily_digest', False)
    quiet_hours = user_notification_settings.get('quiet_hours') or {}
    quiet_hours_enabled = bool(quiet_hours.get('enabled'))

    # Создаем клавиатуру с настройками
    keyboard = [
        [
            InlineKeyboardButton(
                f"🔔 Уведомления: {'✅ Вкл' if notifications_enabled else '❌ Выкл'}",
                callback_data=f"toggle_notifications_{'off' if notifications_enabled else 'on'}"
            )
        ],
        [
            InlineKeyboardButton(
                f"⏰ Напоминания об уроках: {'✅ Вкл' if lesson_reminders_enabled else '❌ Выкл'}",
                callback_data=f"toggle_lesson_reminders_{'off' if lesson_reminders_enabled else 'on'}"
            )
        ],
        [
            InlineKeyboardButton(
                f"📋 Дайджест дня (за час до 1-го урока): {'✅ Вкл' if daily_digest_enabled else '❌ Выкл'}",
                callback_data=f"toggle_daily_digest_{'off' if daily_digest_enabled else 'on'}"
            )
        ],
        [
            InlineKeyboardButton(
                f"🌙 Тихие часы ({quiet_hours.get('start', 22)}:00-{quiet_hours.get('end', 7)}:00): "
                f"{'✅ Вкл' if quiet_hours_enabled else '❌ Выкл'}",
                callback_data=f"toggle_quiet_hours_{'off' if quiet_hours_enabled else 'on'}"
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
        update_notifications_enabled = user_notification_settings.get('update_notifications', False)

        keyboard.append([
            InlineKeyboardButton(
                f"🔄 Уведомления об обновлениях: {'✅ Вкл' if update_notifications_enabled else '❌ Выкл'}",
                callback_data=f"toggle_update_notifications_{'off' if update_notifications_enabled else 'on'}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("📱 Ссылка на виджет", callback_data="widget_link")
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
    query = require_query(update)
    user_id = require_user(update).id
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
    query = require_query(update)
    user_id = require_user(update).id
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


async def toggle_lesson_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
    """Переключает напоминания об уроках (доступно всем пользователям)."""
    query = require_query(update)
    user_id = require_user(update).id
    user_service = context.bot_data.get('user_service')

    if not user_service:
        await query.answer("❌ Сервис не доступен")
        return

    preferences_service = UserPreferencesService(user_service.db)
    if state == 'on':
        preferences_service.enable_lesson_reminders(user_id)
        status_text = "включены"
    else:
        preferences_service.disable_lesson_reminders(user_id)
        status_text = "отключены"

    await query.answer(f"⏰ Напоминания об уроках {status_text}")
    await settings_handler(update, context)


async def toggle_quiet_hours(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
    """Переключает тихие часы (доступно всем пользователям)."""
    query = require_query(update)
    user_id = require_user(update).id
    user_service = context.bot_data.get('user_service')

    if not user_service:
        await query.answer("❌ Сервис не доступен")
        return

    preferences_service = UserPreferencesService(user_service.db)
    if state == 'on':
        preferences_service.enable_quiet_hours(user_id)
        status_text = "включены"
    else:
        preferences_service.disable_quiet_hours(user_id)
        status_text = "отключены"

    await query.answer(f"🌙 Тихие часы {status_text}")
    await settings_handler(update, context)


async def toggle_daily_digest(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
    """Переключает утренний дайджест (доступно всем пользователям)."""
    query = require_query(update)
    user_id = require_user(update).id
    user_service = context.bot_data.get('user_service')

    if not user_service:
        await query.answer("❌ Сервис не доступен")
        return

    preferences_service = UserPreferencesService(user_service.db)
    if state == 'on':
        preferences_service.enable_daily_digest(user_id)
        status_text = "включён"
    else:
        preferences_service.disable_daily_digest(user_id)
        status_text = "отключён"

    await query.answer(f"📋 Дайджест дня {status_text}")
    await settings_handler(update, context)


async def toggle_update_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
    """Переключает настройки уведомлений об обновлениях для администратора"""
    query = require_query(update)
    user_id = require_user(update).id
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


async def send_widget_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет подписанную ссылку на standalone-виджет PWA."""
    query = require_query(update)
    user_id = require_user(update).id

    webapp_url = context.bot_data.get('webapp_url')
    config = context.bot_data.get('config')
    token = getattr(config, 'TELEGRAM_TOKEN', None)

    if not webapp_url:
        await query.answer("❌ URL Mini App не настроен (WEBAPP_URL)")
        return
    if not token:
        await query.answer("❌ Токен бота не настроен")
        return

    widget_token = generate_widget_token(user_id, token)
    link = f"{webapp_url.rstrip('/')}/widget.html?user_id={user_id}&token={widget_token}"
    await query.answer()
    await query.edit_message_text(
        "📱 *Виджет расписания*\n\n"
        "Добавьте расписание на главный экран. Ссылка действует 30 дней, "
        "после чего получите новую здесь же.\n\n"
        f"`{link}`",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings"),
             InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ])
    )
