# handlers/callbacks/class_callbacks.py
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from handlers.common.messaging import edit_long_message, log_user_error
from services.schedule_service import ScheduleService


class ClassCallbackHandler:
    """Обработчик callback'ов для работы с классами"""

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает class_* callback'ы"""
        query = update.callback_query

        # Разбираем callback_data: "class_today_5и" или "class_week_10а"
        parts = callback_data.split('_')
        if len(parts) < 3:
            await query.answer("❌ Ошибка в данных класса")
            return

        # ВАЖНО: Проверяем, что это НЕ callback выбора цифры
        if parts[1] == "digit":
            # Это выбор цифры, а не класса - не обрабатываем здесь
            await query.answer()  # Просто закрываем уведомление
            return

        schedule_type = parts[1]  # today, tomorrow, week
        class_name = '_'.join(parts[2:])  # на случай, если в названии класса есть _

        # Дополнительная проверка: если class_name содержит "digit", это ошибка
        if "digit" in class_name:
            await query.answer("❌ Ошибка выбора класса")
            return

        await self.handle_class_selection(update, context, class_name, schedule_type)

    async def handle_class_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE,  # ← УБРАТЬ нижнее подчеркивание
                                    class_name: str, schedule_type: str):
        """Обрабатывает выбор класса"""
        query = update.callback_query
        user_id = update.effective_user.id
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

        # Сохраняем тип расписания для будущего использования
        context.user_data['last_schedule_type'] = schedule_type

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
                schedule = schedule_service.get_class_schedule_week(class_name)
            else:
                schedule = "❌ Неизвестный тип расписания"

            # Импортируем здесь чтобы избежать циклического импорта
            from handlers.common.callback_handler import create_class_navigation_keyboard
            reply_markup = create_class_navigation_keyboard(class_name, schedule_type)

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
