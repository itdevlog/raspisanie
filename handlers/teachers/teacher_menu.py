# handlers/teachers/teacher_menu.py
"""Меню преподавателей — тонкая обёртка над EntityMenuHandler.

Вся логика (меню, поиск, пагинация, выбор, дневные кнопки) вынесена в
handlers/common/entity_menu.py; здесь только конфиг сущности и прежние
публичные функции (для обратной совместимости с callbacks-обработчиками).
"""
from telegram import Update
from telegram.ext import ContextTypes

from services.teacher_service import TeacherService
from handlers.common.entity_menu import EntityConfig, EntityMenuHandler

_teacher_handler = EntityMenuHandler(EntityConfig(
    entity='teacher',
    label_singular='преподаватель',
    label_plural='преподавателей',
    icon='👨‍🏫',
    menu_title='Поиск преподавателя',
    search_input_hint='Введите фамилию преподавателя для поиска',
    search_example='Например: *Иванов* или *Петрова*',
    empty_data_msg='❌ Нет данных о преподавателях в расписании',
    button_truncate=20,
    state_full_key='teachers',
    state_search_key='search_teachers',
    search_query_key='teacher_search_query',
    service_factory=TeacherService,
    get_all_method='get_available_teachers',
    search_method='search_teachers',
    schedule_today_method='get_teacher_schedule_today',
    schedule_tomorrow_method='get_teacher_schedule_tomorrow',
    schedule_week_method='get_teacher_schedule_week',
))


async def teacher_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _teacher_handler.menu(update, context)


async def show_teacher_search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   school_name: str, available_teachers: list):
    await _teacher_handler.show_search_menu(update, context, school_name, available_teachers)


async def handle_teacher_selection(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                   teacher_name: str, schedule_type: str = "today"):
    await _teacher_handler.select(update, context, teacher_name, schedule_type)


async def show_all_teachers(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    await _teacher_handler.show_all(update, context, page)


async def handle_teacher_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _teacher_handler.search_input(update, context)


async def handle_teacher_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                        search_query: str, page: int = 0):
    await _teacher_handler.search_results(update, context, search_query, page)
