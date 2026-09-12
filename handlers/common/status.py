from telegram import Update
from telegram.ext import ContextTypes

from config.schools import SCHOOLS_CONFIG, get_display_name
from handlers.common.typing import require_message
from services.status_service import StatusService


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статус бота и школ"""
    schools_data = context.bot_data.get('schools_data', {})

    text = "📊 *Статус бота*\n\n"

    # Статус школ
    loaded_schools = len(schools_data)
    total_active_schools = len([s for s in SCHOOLS_CONFIG.values() if s.get('active', True)])

    text += f"🏫 *Школы:* {loaded_schools}/{total_active_schools} загружены\n\n"

    if schools_data:
        status_service = StatusService(schools_data)

        for school_id, school_data in schools_data.items():
            school_name = get_display_name(school_id, school_data)
            status_info = status_service.get_school_status(school_id)

            if status_info['loaded']:
                text += f"• ✅ {school_name}\n"
                text += f"  📅 {status_info['details']}\n"
            else:
                text += f"• ❌ {school_name} - данные не загружены\n"
    else:
        text += "❌ Нет загруженных данных школ\n"

    await require_message(update).reply_text(text, parse_mode='Markdown')
