from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from handlers.callbacks.admin_callbacks import AdminCallbackHandler

# Единая реализация админ-панели живёт в AdminCallbackHandler.
# Здесь — только команды /admin и /stats, делегирующие в неё.
_admin_handler = AdminCallbackHandler()


async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /admin: делегирует в единую реализацию AdminCallbackHandler."""
    user_id = update.effective_user.id

    if not _is_admin(user_id, context):
        await update.message.reply_text("❌ У вас нет прав доступа к админ-панели")
        return

    await _admin_handler.show_panel(update, context)


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats: статистика пользователей."""
    user_id = update.effective_user.id
    if not _is_admin(user_id, context):
        await update.message.reply_text("❌ У вас нет прав доступа к админ-панели")
        return
    await _admin_handler._show_statistics(update, context)


def _is_admin(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Проверяет, является ли пользователь администратором"""
    from config.config import Config
    config = context.bot_data.get('config')
    return Config.is_admin(config, user_id)


# Регистрация обработчиков
def setup_admin_handlers(application):
    """Регистрирует обработчики админ-панели"""
    application.add_handler(CommandHandler("admin", admin_panel_handler))
    application.add_handler(CommandHandler("stats", stats_handler))
