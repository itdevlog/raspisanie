# handlers/callbacks/navigation_callbacks.py
from telegram import Update
from telegram.ext import ContextTypes


class NavigationCallbackHandler:
    """Обработчик callback'ов для навигации и меню"""

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает навигационные callback'ы"""
        query = update.callback_query

        if callback_data == "main_menu":
            await self._handle_main_menu(update, context)
        elif callback_data == "change_class":
            await self._handle_change_class(update, context)
        elif callback_data == "menu_teacher":  # ДОБАВЛЕНО
            await self._handle_teacher_menu(update, context)
        elif callback_data == "menu_room":     # ДОБАВЛЕНО
            await self._handle_room_menu(update, context)
        elif callback_data.startswith("menu_"):
            await self._handle_menu_navigation(update, context, callback_data)
        elif callback_data.startswith("toggle_lesson_reminders_"):
            await self._handle_toggle_lesson_reminders(update, context, callback_data)
        elif callback_data.startswith("toggle_quiet_hours_"):
            await self._handle_toggle_quiet_hours(update, context, callback_data)
        elif callback_data.startswith("toggle_notifications_"):
            await self._handle_toggle_notifications(update, context, callback_data)
        elif callback_data.startswith("toggle_update_notifications_"):
            await self._handle_toggle_update_notifications(update, context, callback_data)
        elif callback_data.startswith("unsubscribe_"):
            await self._handle_unsubscribe(update, context, callback_data)
        elif callback_data.startswith("select_school_"):
            await self._handle_school_selection(update, context, callback_data)
        elif callback_data.startswith("show_all_"):
            await self._handle_show_all_classes(update, context, callback_data)
        elif callback_data.startswith("all_classes_page_"):
            await self._handle_show_all_classes(update, context, callback_data)
        elif callback_data == "all_classes_pages_info":
            await query.answer("Используйте кнопки навигации по страницам")
        elif callback_data.startswith("clear_digit_"):
            await self._handle_clear_digit(update, context, callback_data)
        elif callback_data.startswith("class_digit_"):
            await self._handle_class_digit(update, context, callback_data)
        elif callback_data == "school_not_loaded":
            await query.answer("❌ Данные для этой школы еще загружаются. Попробуйте позже.")
        else:
            await query.answer("❌ Неизвестная команда навигации")

    async def _handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает переход в главное меню"""
        from handlers.common.main_menu import main_menu_handler
        await main_menu_handler(update, context)

    async def _handle_change_class(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает смену класса"""
        from handlers.common.callback_handler import handle_change_class
        await handle_change_class(update, context)

    async def _handle_menu_navigation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает навигацию по меню"""
        from handlers.common.callback_handler import handle_help, show_class_selection
        from handlers.common.school_info import school_info_handler
        from handlers.common.settings import settings_handler

        menu_item = callback_data.replace("menu_", "")

        if menu_item in ["today", "tomorrow", "week"]:
            await show_class_selection(update, context, menu_item)
        elif menu_item == "school_info":
            await school_info_handler(update, context)
        elif menu_item == "help":
            await handle_help(update, context)
        elif menu_item == "settings":
            await settings_handler(update, context)
        elif menu_item == "change_school":
            from handlers.schools.school_selection import school_selection_handler
            await school_selection_handler(update, context)
        elif menu_item == "teacher":
            # ДОБАВЛЕНО: Обработка перехода в меню преподавателей
            from handlers.teachers.teacher_menu import teacher_menu_handler
            await teacher_menu_handler(update, context)
        elif menu_item == "room":
            # ДОБАВЛЕНО: Обработка перехода в меню кабинетов
            from handlers.rooms.room_schedule import room_menu_handler
            await room_menu_handler(update, context)

    async def _handle_school_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает выбор школы"""
        from handlers.schools.school_selection import handle_school_selection

        school_id = callback_data.replace("select_school_", "")
        await handle_school_selection(update, context, school_id)

    async def _handle_show_all_classes(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает показ всех классов (с сохранением типа расписания)."""
        from handlers.common.callback_handler import (
            handle_show_all_classes,
            parse_all_classes_page,
        )
        if callback_data.startswith("all_classes_page_"):
            parsed = parse_all_classes_page(callback_data)
            if parsed is None:
                await update.callback_query.answer("❌ Ошибка страницы")
                return
            schedule_type, page = parsed
        else:
            schedule_type = callback_data.replace("show_all_", "")
            page = 0
        await handle_show_all_classes(update, context, schedule_type, page)

    async def _handle_clear_digit(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает очистку выбранной цифры класса"""
        from handlers.common.callback_handler import show_class_selection

        schedule_type = callback_data.replace("clear_digit_", "")
        if 'class_digit' in context.user_data:
            del context.user_data['class_digit']
        await show_class_selection(update, context, schedule_type)

    async def _handle_class_digit(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает выбор цифры класса"""
        from handlers.common.callback_handler import show_class_selection

        parts = callback_data.split('_')
        if len(parts) >= 4:
            digit = parts[2]  # цифра класса
            schedule_type = parts[3]  # today, tomorrow, week
            context.user_data['class_digit'] = digit
            await show_class_selection(update, context, schedule_type)
        else:
            await update.callback_query.answer("❌ Ошибка в данных цифры")

    async def _handle_teacher_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает переход в меню преподавателей"""
        from handlers.teachers.teacher_menu import teacher_menu_handler
        await teacher_menu_handler(update, context)

    async def _handle_room_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает переход в меню кабинетов"""
        from handlers.rooms.room_schedule import room_menu_handler
        await room_menu_handler(update, context)

    async def _handle_unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает отписку от преподавателя/кабинета из меню настроек."""
        from handlers.common.settings import unsubscribe_by_callback

        payload = callback_data.replace("unsubscribe_", "")
        await unsubscribe_by_callback(update, context, payload)

    async def _handle_toggle_notifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает переключение уведомлений"""
        from handlers.common.settings import toggle_notifications

        state = callback_data.replace("toggle_notifications_", "")
        await toggle_notifications(update, context, state)

    async def _handle_toggle_lesson_reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает переключение напоминаний об уроках"""
        from handlers.common.settings import toggle_lesson_reminders

        state = callback_data.replace("toggle_lesson_reminders_", "")
        await toggle_lesson_reminders(update, context, state)

    async def _handle_toggle_quiet_hours(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает переключение тихих часов"""
        from handlers.common.settings import toggle_quiet_hours

        state = callback_data.replace("toggle_quiet_hours_", "")
        await toggle_quiet_hours(update, context, state)

    async def _handle_toggle_update_notifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает переключение уведомлений обновлениях"""
        from handlers.common.settings import toggle_update_notifications

        state = callback_data.replace("toggle_update_notifications_", "")
        await toggle_update_notifications(update, context, state)
