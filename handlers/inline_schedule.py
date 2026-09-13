# handlers/inline_schedule.py
"""Inline-режим: @bot 9а — расписание класса на сегодня в любом чате."""
import logging

from telegram import InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import ContextTypes

from services.schedule_service import ScheduleService

logger = logging.getLogger(__name__)
MAX_RESULTS = 5


def build_inline_results(query: str, context, user_id: int) -> list:
    """Строит inline-результаты по префиксу класса (или классу профиля)."""
    bot_data = context.bot_data
    schools_data = bot_data.get('schools_data', {})
    user_service = bot_data.get('user_service')
    if not schools_data or not user_service:
        return []

    school_id = user_service.get_user_school(user_id)
    school_data = schools_data.get(school_id)
    if not school_data:
        return []

    service = ScheduleService(school_data, school_id=school_id)
    all_classes = service.get_available_classes()

    q = (query or '').strip().lower()
    if q:
        matched = [c for c in all_classes if c.lower().startswith(q)]
    else:
        profile_class = user_service.get_user_class(user_id, school_id)
        matched = [profile_class] if profile_class else []

    results = []
    for class_name in sorted(matched)[:MAX_RESULTS]:
        text = service.get_class_schedule_today(class_name)
        results.append(InlineQueryResultArticle(
            id=f"cls_{class_name}",
            title=f"📅 {class_name} — сегодня",
            input_message_content=InputTextMessageContent(
                message_text=text, parse_mode='Markdown'),
            description="Расписание с заменами",
        ))
    return results


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отвечает на inline-запросы расписания."""
    if not update.inline_query:
        return
    results = build_inline_results(
        update.inline_query.query, context, update.inline_query.from_user.id)
    await update.inline_query.answer(
        results, cache_time=300, is_personal=True,
    )
