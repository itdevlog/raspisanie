from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.room_service import RoomService
from config.schools import SCHOOLS_CONFIG
from services.state_service import UserStateService
from handlers.common.messaging import edit_long_message, clear_search_flags

async def room_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора кабинета"""
    clear_search_flags(context)
    query = update.callback_query
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})
    
    if not user_service or not schools_data:
        if query:
            await query.edit_message_text("❌ Сервис не доступен")
        else:
            await update.message.reply_text("❌ Сервис не доступен")
        return
    
    # Получаем выбранную школу пользователя
    current_school_id = user_service.get_user_school(user_id)
    school_data = schools_data.get(current_school_id)
    
    if not school_data:
        if query:
            await query.edit_message_text("❌ Данные для вашей школы не загружены")
        else:
            await update.message.reply_text("❌ Данные для вашей школы не загружены")
        return
    
    try:
        room_service = RoomService(school_data)
        available_rooms = room_service.get_available_rooms()
        
        if not available_rooms:
            text = "❌ Нет данных о кабинетах в расписании"
            if query:
                await query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        # Получаем название текущей школы для отображения
        school_config = None
        for school in SCHOOLS_CONFIG.values():
            if school['id'] == current_school_id:
                school_config = school
                break
        
        school_name = school_config['name'] if school_config else "Неизвестно"
        
        # Показываем меню поиска кабинета
        await show_room_search_menu(update, context, school_name, available_rooms)
        
    except Exception as e:
        error_text = f"❌ Ошибка при загрузке списка кабинетов: {str(e)}"
        if query:
            await query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

async def show_room_search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, school_name: str, available_rooms: list):
    """Показывает меню поиска кабинета"""
    query = update.callback_query
    
    text = (
        f"🏫 *{school_name}*\n"
        f"*Расписание кабинетов*\n\n"
        f"Всего кабинетов: {len(available_rooms)}\n\n"
        f"Выберите действие:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск по номеру", callback_data="room_search_input")],
        [InlineKeyboardButton("📋 Показать все", callback_data="room_show_all_0")],  # Начинаем с страницы 0
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_room_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, room_name: str, schedule_type: str = "today"):
    """Обрабатывает выбор кабинета и показывает расписание"""
    query = update.callback_query
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})
    state_service = context.bot_data.get('state_service')  # УБЕДИТЕСЬ ЧТО ЭТА СТРОКА ЕСТЬ
    
    if not user_service or not schools_data:
        await query.edit_message_text("❌ Сервис не доступен")
        return
    
    # Получаем выбранную школу пользователя
    current_school_id = user_service.get_user_school(user_id)
    school_data = schools_data.get(current_school_id)
    
    if not school_data:
        await query.edit_message_text("❌ Данные для вашей школы не загружены")
        return
    
    # Показываем сообщение о загрузке
    await query.edit_message_text(f"🔄 Загружаем расписание для кабинета {room_name}...")
    
    try:
        room_service = RoomService(school_data)
        
        # Получаем расписание в зависимости от типа
        if schedule_type == "today":
            schedule = room_service.get_room_schedule_today(room_name)
        elif schedule_type == "tomorrow":
            schedule = room_service.get_room_schedule_tomorrow(room_name)
        elif schedule_type == "week":
            schedule = room_service.get_room_schedule_week(room_name)
        else:
            # Если неизвестный тип, показываем сегодняшнее расписание
            print(f"WARNING: Unknown schedule_type '{schedule_type}', defaulting to 'today'")
            schedule = room_service.get_room_schedule_today(room_name)
        
        # Создаем клавиатуру для навигации
        keyboard = []
        
        # Кнопки других дней для этого же кабинета.
        # Выясняем, из какого списка выбран кабинет (поиск vs полный),
        # чтобы дневные кнопки резолвили правильный индекс.
        other_days = []
        source, room_index = _resolve_room_source(user_id, room_name, state_service)
        idx_suffix = 'sidx' if source == 'search' else 'idx'
        if schedule_type != "today" and room_index is not None:
            other_days.append(InlineKeyboardButton("📅 Сегодня",
                callback_data=f"room_today_{idx_suffix}_{room_index}"))
        if schedule_type != "tomorrow" and room_index is not None:
            other_days.append(InlineKeyboardButton("📆 Завтра",
                callback_data=f"room_tomorrow_{idx_suffix}_{room_index}"))
        if schedule_type != "week" and room_index is not None:
            other_days.append(InlineKeyboardButton("🗓️ Неделя",
                callback_data=f"room_week_{idx_suffix}_{room_index}"))
        
        if other_days:
            keyboard.append(other_days)
        
        # Навигация
        keyboard.append([
            InlineKeyboardButton("🔍 Найти другой", callback_data="menu_room"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await edit_long_message(update, context, query, schedule, reply_markup=reply_markup)
        
    except Exception as e:
        # В случае ошибки покажем сообщение и кнопку назад
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_room")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"❌ Произошла ошибка при загрузке расписания:\n{str(e)}",
            reply_markup=reply_markup
        )

async def show_all_rooms(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Показывает полный список кабинетов с пагинацией"""
    clear_search_flags(context)
    query = update.callback_query
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})
    state_service = context.bot_data.get('state_service')  # ДОБАВЛЕНО
    
    if not user_service or not schools_data:
        await query.edit_message_text("❌ Сервис не доступен")
        return
    
    # Получаем выбранную школу пользователя
    current_school_id = user_service.get_user_school(user_id)
    school_data = schools_data.get(current_school_id)
    
    if not school_data:
        await query.edit_message_text("❌ Данные для вашей школы не загружены")
        return
    
    try:
        room_service = RoomService(school_data)
        available_rooms = room_service.get_available_rooms()
        
        if not available_rooms:
            await query.edit_message_text("❌ Нет данных о кабинетах")
            return
        
        # Сортируем кабинеты до сохранения, чтобы индексы совпадали
        available_rooms.sort()

        # Пагинация
        rooms_per_page = 30
        total_rooms = len(available_rooms)
        total_pages = (total_rooms + rooms_per_page - 1) // rooms_per_page

        # Проверяем корректность страницы
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1

        # СОХРАНЯЕМ список кабинетов через state_service
        state_service.set_user_list(user_id, 'rooms', available_rooms)
        state_service.set_user_page(user_id, 'rooms', page)

        start_index = page * rooms_per_page
        end_index = min(start_index + rooms_per_page, total_rooms)
        rooms_on_page = available_rooms[start_index:end_index]
        
        # Создаем клавиатуру с кабинетами
        keyboard = []
        current_row = []
        
        for index, room in enumerate(rooms_on_page):
            global_index = start_index + index
            
            button_text = room[:15] + "..." if len(room) > 15 else room
            callback_data = f"room_today_idx_{global_index}"
            
            current_row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
            
            if len(current_row) == 2:
                keyboard.append(current_row)
                current_row = []
        
        if current_row:
            keyboard.append(current_row)
        
        # Кнопки пагинации
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"room_show_all_{page-1}"))
        
        pagination_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="room_pages_info"))
        
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"room_show_all_{page+1}"))
        
        if pagination_buttons:
            keyboard.append(pagination_buttons)
        
        # Кнопки навигации
        keyboard.append([InlineKeyboardButton("🔍 Поиск", callback_data="room_search_input")])
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="menu_room"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        showing_start = start_index + 1
        showing_end = end_index
        
        text = (
            f"🏫 *Все кабинеты*\n\n"
            f"*Всего:* {total_rooms} кабинетов\n"
            f"*Показано:* {showing_start}-{showing_end}\n\n"
            f"Выберите кабинет:"
        )
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка при загрузке списка кабинетов: {str(e)}")


async def handle_room_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает запрос на ввод номера кабинета для поиска"""
    query = update.callback_query
    
    # Устанавливаем флаг, что ждем ввод номера кабинета
    context.user_data['waiting_for_room_search'] = True
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="menu_room")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔍 *Поиск кабинета*\n\n"
        "Введите номер или название кабинета для поиска:\n"
        "Например: *101* или *актовый*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_room_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, search_query: str, page: int = 0):
    """Показывает результаты поиска кабинетов с пагинацией"""
    query = update.callback_query
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})
    state_service = context.bot_data.get('state_service')  # УБЕДИТЕСЬ ЧТО ЭТА СТРОКА ЕСТЬ
    
    if not user_service or not schools_data:
        if query:
            await query.edit_message_text("❌ Сервис не доступен")
        else:
            await update.message.reply_text("❌ Сервис не доступен")
        return
    
    # Получаем выбранную школу пользователя
    current_school_id = user_service.get_user_school(user_id)
    school_data = schools_data.get(current_school_id)
    
    if not school_data:
        if query:
            await query.edit_message_text("❌ Данные для вашей школы не загружены")
        else:
            await update.message.reply_text("❌ Данные для вашей школы не загружены")
        return
    
    try:
        room_service = RoomService(school_data)
        found_rooms = room_service.search_rooms(search_query)
        
        if not found_rooms:
            # Сбрасываем сохранённый запрос, т.к. результатов нет
            context.user_data.pop('room_search_query', None)
            text = f"❌ Кабинеты с номером '*{search_query}*' не найдены"
            keyboard = [
                [InlineKeyboardButton("🔍 Попробовать снова", callback_data="room_search_input")],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu_room")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if query:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            return
        
        # Сортируем результаты поиска до сохранения, чтобы индексы совпадали
        found_rooms.sort()

        # Пагинация для результатов поиска
        rooms_per_page = 30
        total_rooms = len(found_rooms)
        total_pages = (total_rooms + rooms_per_page - 1) // rooms_per_page

        # Проверяем корректность страницы
        if page < 0:
            page = 0
        elif total_pages > 0 and page >= total_pages:
            page = total_pages - 1

        start_index = page * rooms_per_page
        end_index = min(start_index + rooms_per_page, total_rooms)
        rooms_on_page = found_rooms[start_index:end_index]

        # СОХРАНЯЕМ запрос и найденные кабинеты под ОТДЕЛЬНЫМ ключом
        # 'search_rooms' (не 'rooms'), чтобы индексы из поиска не конфликтовали
        # с полным списком кабинетов.
        if not state_service:
            await update.message.reply_text("❌ Сервис временно не доступен")
            return

        context.user_data['room_search_query'] = search_query
        state_service.set_user_list(user_id, 'search_rooms', found_rooms)
        state_service.set_user_page(user_id, 'search_rooms', page)
        
        # Создаем клавиатуру с найденными кабинетами
        keyboard = []
        current_row = []
        
        for index, room in enumerate(rooms_on_page):
            global_index = start_index + index
            
            button_text = room[:15] + "..." if len(room) > 15 else room
            
            # Используем индекс + признак поиска ('sidx_') в callback_data,
            # чтобы отличать индекс из результатов поиска от полного списка
            callback_data = f"room_today_sidx_{global_index}"
            
            current_row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
            
            if len(current_row) == 2:  # 2 кнопки в ряду
                keyboard.append(current_row)
                current_row = []
        
        if current_row:
            keyboard.append(current_row)
        
        # Кнопки пагинации для поиска.
        # Запрос не кладём в callback_data (кириллица превышает лимит 64 байта),
        # храним его в user_data и передаём только номер страницы.
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"room_search_page_{page-1}"))
        
        pagination_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="room_search_pages_info"))
        
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"room_search_page_{page+1}"))
        
        if pagination_buttons:
            keyboard.append(pagination_buttons)
        
        # Кнопки навигации
        keyboard.append([InlineKeyboardButton("🔍 Новый поиск", callback_data="room_search_input")])
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="menu_room"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        showing_start = start_index + 1
        showing_end = end_index
        
        text = (
            f"🔍 *Результаты поиска:* '{search_query}'\n\n"
            f"*Найдено:* {total_rooms} кабинетов\n"
            f"*Показано:* {showing_start}-{showing_end}\n\n"
            f"Выберите кабинет:"
        )
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        error_text = f"❌ Ошибка при поиске кабинетов: {str(e)}"
        if query:
            await query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

def _resolve_room_source(user_id: int, room_name: str, state_service: UserStateService) -> tuple:
    """Определяет список, из которого выбран кабинет, и его индекс.

    Возвращает (source, index): source — 'search' или 'full'.
    Поиск хранится под отдельным ключом 'search_rooms', поэтому кнопки
    «Сегодня/Завтра/Неделя» после выбора из результатов поиска должны
    резолвить индекс по этому же списку (иначе клик уйдёт в чужой кабинет).
    """
    search_list = state_service.get_user_list(user_id, 'search_rooms')
    if search_list and room_name in search_list:
        return ('search', search_list.index(room_name))
    full_list = state_service.get_user_list(user_id, 'rooms')
    if full_list and room_name in full_list:
        return ('full', full_list.index(room_name))
    return ('full', None)