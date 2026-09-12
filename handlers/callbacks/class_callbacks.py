# handlers/callbacks/class_callbacks.py
import re

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from handlers.common.messaging import edit_long_message, log_user_error
from handlers.common.typing import require_query, require_user
from services.schedule_service import ScheduleService

WEEK_OFFSET_LIMIT = 2
_WEEK_OFFSET_RE = re.compile(r'_o(-?\d+)$')


def parse_week_offset(callback_data: str) -> int:
    """Извлекает смещение недели из `class_week_{класс}_o{N}` (иначе 0)."""
    match = _WEEK_OFFSET_RE.search(callback_data)
    if not match:
        return 0
    try:
        return int(match.group(1))
    except ValueError:
        return 0


class ClassCallbackHandler:
    """Обработчик callback'ов для работы с классами"""

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает class_* callback'ы"""
        query = require_query(update)

        week_offset = parse_week_offset(callback_data)
        if _WEEK_OFFSET_RE.search(callback_data):
            callback_data = _WEEK_OFFSET_RE.sub('', callback_data)

        # Разбираем callback_data: "class_today_5и" или "class_week_10а"
        parts = callback_data.split('_')
        if len(parts) < 3:
            await query.answer("❌ Ошибка в данных класса")
            return

        # ВАЖНО: callback выбора цифры (`class_digit_*`) перехватывается роутером
        # и сюда не попадает; в этой ветке обрабатывается только выбор класса.
        schedule_type = parts[1]  # today, tomorrow, week
        class_name = '_'.join(parts[2:])  # на случай, если в названии класса есть _

        await self.handle_class_selection(update, context, class_name, schedule_type, week_offset)

    async def handle_class_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                    class_name: str, schedule_type: str, week_offset: int = 0):
        """Обрабатывает выбор класса"""
        query = require_query(update)
        user_id = require_user(update).id
        user_service = context.bot_data.get('user_service')
        schools_data = context.bot_data.get('schools_data', {})

        if not user_service or not schools_data:
            await query.edit_message_text("❌ Сервис не доступен")
            return

        # Получаем выбранную школу пользователя
        current_school_id = user_service.get_user_school(user_id)
        school_data = schools_data.get(current_school_id)

        if not school_data:
            await query.edit_message_text("❌ Данные для вашей школы не загружены")
            return

        # Сохраняем класс для текущей школы пользователя
        user_service.set_user_class(user_id, class_name, current_school_id)

        # Показываем сообщение о загрузке
        await query.edit_message_text("🔄 Загружаем расписание...")

        try:
            cache_service = context.bot_data.get('cache_service')
            schedule_service = ScheduleService(school_data, cache_service, current_school_id)

            # Получаем расписание
            if schedule_type == "today":
                schedule = schedule_service.get_class_schedule_today(class_name)
            elif schedule_type == "tomorrow":
                schedule = schedule_service.get_class_schedule_tomorrow(class_name)
            elif schedule_type == "week":
                week_offset = max(-WEEK_OFFSET_LIMIT, min(WEEK_OFFSET_LIMIT, week_offset))
                schedule = schedule_service.get_class_schedule_week(class_name, week_offset)
                if week_offset > 0 and "Нет занятий" in schedule:
                    schedule = (
                        f"📅 *Неделя {class_name}*\n\n"
                        "❌ Данных на эту неделю ещё нет. Расписание обычно "
                        "публикуется ближе к концу текущей недели."
                    )
            else:
                schedule = "❌ Неизвестный тип расписания"

            # Импортируем здесь чтобы избежать циклического импорта
            from handlers.common.callback_handler import create_class_navigation_keyboard
            reply_markup = create_class_navigation_keyboard(class_name, schedule_type, week_offset)

            try:
                await edit_long_message(update, context, query, schedule, reply_markup=reply_markup)
            except BadRequest as e:
                if "not modified" not in str(e).lower():
                    raise

        except Exception as e:
            from handlers.common.callback_handler import create_error_keyboard
            reply_markup = create_error_keyboard()

            await query.edit_message_text(
                log_user_error("Error loading schedule", e),
                reply_markup=reply_markup
            )
