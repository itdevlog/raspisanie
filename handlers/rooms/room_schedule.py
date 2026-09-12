# handlers/rooms/room_schedule.py
"""Меню кабинетов — тонкая обёртка над EntityMenuHandler.

Вся логика (меню, поиск, пагинация, выбор, дневные кнопки) вынесена в
handlers/common/entity_menu.py; здесь только конфиг сущности и прежние
публичные функции (для обратной совместимости с callbacks-обработчиками).
"""
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from handlers.common.entity_menu import EntityConfig, EntityMenuHandler
from handlers.common.messaging import log_user_error
from handlers.common.typing import require_query, require_user
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
    extra_button_label='🔍 Свободный кабинет',
    extra_button_callback='room_free_now',
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


async def handle_room_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    await _room_handler.handle_subscription_callback(update, context, callback_data)


async def free_rooms_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """«Свободный кабинет»: свободные кабинеты на текущий/следующий урок.

    Как «Найти свободный кабинет» на сайте Nikasoft: после уроков
    показываем следующий день не предлагаем — только текущий слот
    (идущий урок или следующий за ним).
    """
    query = require_query(update)
    user_id = require_user(update).id
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})

    if not user_service or not schools_data:
        await query.edit_message_text("❌ Сервис не доступен")
        return
    school_id = user_service.get_user_school(user_id)
    school_data = schools_data.get(school_id)
    if not school_data:
        await query.edit_message_text("❌ Данные для вашей школы не загружены")
        return

    try:
        service = RoomService(school_data)
        now = datetime.now(service.moscow_tz)
        if now.isoweekday() > 5 or not service._get_period_for_date(now):
            await query.edit_message_text("🏖️ Сегодня занятий нет — все кабинеты свободны")
            return

        lesson_num = _current_or_next_lesson(service, now)
        if lesson_num is None:
            await query.edit_message_text(
                "🏫 Сегодня уроков больше нет.\n"
                "Свободные кабинеты показываем на текущий/следующий урок.")
            return

        text = service.get_free_rooms_message(now, lesson_num)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data="room_free_now")],
            [InlineKeyboardButton("🔙 К кабинетам", callback_data="menu_room"),
             InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        ])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
    except Exception as e:
        await query.edit_message_text(
            log_user_error("Ошибка поиска свободных кабинетов", e))


def _current_or_next_lesson(service: RoomService, now: datetime) -> int | None:
    """Номер текущего (идёт сейчас) или следующего урока по LESSON_TIMES."""
    lesson_times = service.school_data.get('LESSON_TIMES', {})
    best: int | None = None
    for lesson_num_str, times in lesson_times.items():
        if not times or len(times) < 2 or times[0] == '?':
            continue
        try:
            start = now.replace(hour=int(times[0][:2]), minute=int(times[0][3:5]),
                                second=0, microsecond=0)
            end = now.replace(hour=int(times[1][:2]), minute=int(times[1][3:5]),
                              second=0, microsecond=0)
        except (ValueError, IndexError):
            continue
        if start <= now <= end:
            return int(lesson_num_str)  # идущий урок — приоритет
        if now < start and (best is None or int(lesson_num_str) < best):
            best = int(lesson_num_str)
    return best
