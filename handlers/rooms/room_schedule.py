# handlers/rooms/room_schedule.py
"""Меню кабинетов — тонкая обёртка над EntityMenuHandler.

Вся логика (меню, поиск, пагинация, выбор, дневные кнопки) вынесена в
handlers/common/entity_menu.py; здесь только конфиг сущности и прежние
публичные функции (для обратной совместимости с callbacks-обработчиками).
"""
from telegram import Update
from telegram.ext import ContextTypes

from handlers.common.entity_menu import EntityConfig, EntityMenuHandler
from services.room_service import RoomService

_room_handler = EntityMenuHandler(EntityConfig(
    entity='room',
    label_singular='кабинет',
    label_plural='кабинетов',
    icon='🏫',
    menu_title='Расписание кабинетов',
    search_input_hint='Введите номер или название кабинета для поиска',
    search_example='Например: *101* или *актовый*',
    empty_data_msg='❌ Нет данных о кабинетах в расписании',
    button_truncate=15,
    state_full_key='rooms',
    state_search_key='search_rooms',
    search_query_key='room_search_query',
    service_factory=RoomService,
    get_all_method='get_available_rooms',
    search_method='search_rooms',
    schedule_today_method='get_room_schedule_today',
    schedule_tomorrow_method='get_room_schedule_tomorrow',
    schedule_week_method='get_room_schedule_week',
))


async def room_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _room_handler.menu(update, context)


async def show_room_search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                school_name: str, available_rooms: list):
    await _room_handler.show_search_menu(update, context, school_name, available_rooms)


async def handle_room_selection(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                room_name: str, schedule_type: str = "today"):
    await _room_handler.select(update, context, room_name, schedule_type)


async def show_all_rooms(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    await _room_handler.show_all(update, context, page)


async def handle_room_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _room_handler.search_input(update, context)


async def handle_room_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                     search_query: str, page: int = 0):
    await _room_handler.search_results(update, context, search_query, page)
