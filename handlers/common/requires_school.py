# handlers/common/requires_school.py
"""Декоратор @requires_school: убирает дублирующиеся проверки сервисов/школы.

Раньше каждый обработчик повторял:
  user_service = context.bot_data.get('user_service')
  schools_data = context.bot_data.get('schools_data', {})
  if not user_service or not schools_data: ... return
  current_school_id = user_service.get_user_school(user_id)
  school_data = schools_data.get(current_school_id)
  if not school_data: ... return

Декоратор вычисляет это один раз, подкладывает в `context` ключи
`user_service`, `current_school_id`, `school_data` и вызывает обработчик только
когда всё готово; иначе отправляет понятную ошибку (reply или edit) и return.
"""
import functools
from typing import Any, Callable, cast

from telegram import Update
from telegram.ext import ContextTypes

from handlers.common.messaging import safe_edit_message
from handlers.common.typing import require_user


async def _send(context, update, text: str):
    if update.callback_query:
        return await safe_edit_message(update.callback_query, text)
    msg = update.effective_message
    if msg:
        return await msg.reply_text(text)
    return None


def requires_school(func: Callable):
    """Выполняет func(update, context, ...) только при наличии user_service и school_data."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_service = context.bot_data.get('user_service')
        schools_data = context.bot_data.get('schools_data', {})

        if not user_service or not schools_data:
            return await _send(context, update, "❌ Сервис не доступен")

        user_id = require_user(update).id
        current_school_id = user_service.get_user_school(user_id)
        school_data = schools_data.get(current_school_id)

        if not school_data:
            return await _send(context, update, "❌ Данные для вашей школы не загружены")

        # Подкладываем готовые значения в контекст для обработчика
        ctx = cast(Any, context)
        ctx.user_service = user_service
        ctx.current_school_id = current_school_id
        ctx.school_data = school_data

        return await func(update, context, *args, **kwargs)

    return wrapper
