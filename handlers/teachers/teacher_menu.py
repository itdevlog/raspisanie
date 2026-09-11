from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.state_service import UserStateService
from services.teacher_service import TeacherService
from config.schools import SCHOOLS_CONFIG

async def teacher_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает меню выбора преподавателя"""
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
        teacher_service = TeacherService(school_data)
        available_teachers = teacher_service.get_available_teachers()
        
        if not available_teachers:
            text = "❌ Нет данных о преподавателях в расписании"
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
        
        # Показываем меню поиска преподавателя
        await show_teacher_search_menu(update, context, school_name, available_teachers)
        
    except Exception as e:
        error_text = f"❌ Ошибка при загрузке списка преподавателей: {str(e)}"
        if query:
            await query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

async def show_teacher_search_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, school_name: str, available_teachers: list):
    """Показывает меню поиска преподавателя"""
    query = update.callback_query
    
    text = (
        f"👨‍🏫 *{school_name}*\n"
        f"*Поиск преподавателя*\n\n"
        f"Всего преподавателей: {len(available_teachers)}\n\n"
        f"Выберите действие:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔍 Поиск по фамилии", callback_data="teacher_search_input")],
        [InlineKeyboardButton("📋 Показать всех", callback_data="teacher_show_all_0")],  # Начинаем с страницы 0
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_teacher_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, teacher_name: str, schedule_type: str = "today"):
    """Обрабатывает выбор преподавателя и показывает расписание"""
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
    await query.edit_message_text(f"🔄 Загружаем расписание для {teacher_name}...")
    
    try:
        teacher_service = TeacherService(school_data)
        
        # Получаем расписание в зависимости от типа
        if schedule_type == "today":
            schedule = teacher_service.get_teacher_schedule_today(teacher_name)
        elif schedule_type == "tomorrow":
            schedule = teacher_service.get_teacher_schedule_tomorrow(teacher_name)
        elif schedule_type == "week":
            schedule = teacher_service.get_teacher_schedule_week(teacher_name)
        else:
            schedule = teacher_service.get_teacher_schedule_today(teacher_name)
        
        # Создаем клавиатуру для навигации
        keyboard = []
        
        # Кнопки других дней для этого же преподавателя
        other_days = []
        if schedule_type != "today":
            # Используем индекс через state_service - ПЕРЕДАЕМ state_service
            teacher_index = _get_teacher_index(user_id, teacher_name, state_service)  # ИЗМЕНЕНО
            if teacher_index is not None:
                other_days.append(InlineKeyboardButton("📅 Сегодня", 
                    callback_data=f"teacher_today_idx_{teacher_index}"))
        if schedule_type != "tomorrow":
            teacher_index = _get_teacher_index(user_id, teacher_name, state_service)  # ИЗМЕНЕНО
            if teacher_index is not None:
                other_days.append(InlineKeyboardButton("📆 Завтра", 
                    callback_data=f"teacher_tomorrow_idx_{teacher_index}"))
        if schedule_type != "week":
            teacher_index = _get_teacher_index(user_id, teacher_name, state_service)  # ИЗМЕНЕНО
            if teacher_index is not None:
                other_days.append(InlineKeyboardButton("🗓️ Неделя", 
                    callback_data=f"teacher_week_idx_{teacher_index}"))
        
        if other_days:
            keyboard.append(other_days)
        
        # Навигация
        keyboard.append([
            InlineKeyboardButton("🔍 Найти другого", callback_data="menu_teacher"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(schedule, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        keyboard = [
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_teacher")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"❌ Произошла ошибка при загрузке расписания:\n{str(e)}",
            reply_markup=reply_markup
        )

async def show_all_teachers(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Показывает полный список преподавателей с пагинацией"""
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
        teacher_service = TeacherService(school_data)
        available_teachers = teacher_service.get_available_teachers()
        
        if not available_teachers:
            await query.edit_message_text("❌ Нет данных о преподавателях")
            return
        
        # Сортируем преподавателей до сохранения, чтобы индексы совпадали
        available_teachers.sort()

        # Пагинация
        teachers_per_page = 30
        total_teachers = len(available_teachers)
        total_pages = (total_teachers + teachers_per_page - 1) // teachers_per_page

        # Проверяем корректность страницы
        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1

        # СОХРАНЯЕМ список преподавателей через state_service вместо глобальной переменной
        state_service.set_user_list(user_id, 'teachers', available_teachers)
        state_service.set_user_page(user_id, 'teachers', page)

        start_index = page * teachers_per_page
        end_index = min(start_index + teachers_per_page, total_teachers)
        teachers_on_page = available_teachers[start_index:end_index]
        
        # Создаем клавиатуру с преподавателями
        keyboard = []
        current_row = []
        
        for index, teacher in enumerate(teachers_on_page):
            global_index = start_index + index
            
            button_text = teacher[:20] + "..." if len(teacher) > 20 else teacher
            
            # Используем индекс вместо имени для callback_data
            callback_data = f"teacher_today_idx_{global_index}"
            
            current_row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
            
            if len(current_row) == 2:  # 2 кнопки в ряду для преподавателей
                keyboard.append(current_row)
                current_row = []
        
        if current_row:  # Добавим оставшиеся кнопки
            keyboard.append(current_row)
        
        # Кнопки пагинации
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"teacher_show_all_{page-1}"))
        
        pagination_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="teacher_pages_info"))
        
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"teacher_show_all_{page+1}"))
        
        if pagination_buttons:
            keyboard.append(pagination_buttons)
        
        # Кнопки навигации
        keyboard.append([InlineKeyboardButton("🔍 Поиск", callback_data="teacher_search_input")])
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="menu_teacher"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        showing_start = start_index + 1
        showing_end = end_index
        
        text = (
            f"👨‍🏫 *Все преподаватели*\n\n"
            f"*Всего:* {total_teachers} преподавателей\n"
            f"*Показано:* {showing_start}-{showing_end}\n\n"
            f"Выберите преподавателя:"
        )
        
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка при загрузке списка преподавателей: {str(e)}")

async def handle_teacher_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает запрос на ввод фамилии для поиска"""
    query = update.callback_query
    
    # Устанавливаем флаг, что ждем ввод фамилии преподавателя
    context.user_data['waiting_for_teacher_search'] = True
    
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="menu_teacher")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔍 *Поиск преподавателя*\n\n"
        "Введите фамилию преподавателя для поиска:\n"
        "Например: *Иванов* или *Петрова*",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def handle_teacher_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, search_query: str, page: int = 0):
    """Показывает результаты поиска преподавателей с пагинацией"""
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
        teacher_service = TeacherService(school_data)
        found_teachers = teacher_service.search_teachers(search_query)
        
        if not found_teachers:
            text = f"❌ Преподаватели с фамилией '*{search_query}*' не найдены"
            keyboard = [
                [InlineKeyboardButton("🔍 Попробовать снова", callback_data="teacher_search_input")],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu_teacher")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if query:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            return
        
        # Сортируем результаты поиска до сохранения, чтобы индексы совпадали
        found_teachers.sort()

        # Пагинация для результатов поиска
        teachers_per_page = 30
        total_teachers = len(found_teachers)
        total_pages = (total_teachers + teachers_per_page - 1) // teachers_per_page

        # Проверяем корректность страницы
        if page < 0:
            page = 0
        elif total_pages > 0 and page >= total_pages:
            page = total_pages - 1

        start_index = page * teachers_per_page
        end_index = min(start_index + teachers_per_page, total_teachers)
        teachers_on_page = found_teachers[start_index:end_index]

        # СОХРАНЯЕМ найденных преподавателей под тем же ключом,
        # чтобы callback-и разрешали индексы корректно
        if not state_service:
            await update.message.reply_text("❌ Сервис временно не доступен")
            return

        state_service.set_user_list(user_id, 'teachers', found_teachers)
        state_service.set_user_page(user_id, 'teachers', page)
        
        # Создаем клавиатуру с найденными преподавателями
        keyboard = []
        current_row = []
        
        for index, teacher in enumerate(teachers_on_page):
            global_index = start_index + index
            
            button_text = teacher[:20] + "..." if len(teacher) > 20 else teacher
            
            # Используем индекс вместо имени для callback_data
            callback_data = f"teacher_today_idx_{global_index}"
            
            current_row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
            
            if len(current_row) == 2:  # 2 кнопки в ряду
                keyboard.append(current_row)
                current_row = []
        
        if current_row:
            keyboard.append(current_row)
        
        # Кнопки пагинации для поиска
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=f"teacher_search_{search_query}_{page-1}"))
        
        pagination_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="teacher_search_pages_info"))
        
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"teacher_search_{search_query}_{page+1}"))
        
        if pagination_buttons:
            keyboard.append(pagination_buttons)
        
        # Кнопки навигации
        keyboard.append([InlineKeyboardButton("🔍 Новый поиск", callback_data="teacher_search_input")])
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data="menu_teacher"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        showing_start = start_index + 1
        showing_end = end_index
        
        text = (
            f"🔍 *Результаты поиска:* '{search_query}'\n\n"
            f"*Найдено:* {total_teachers} преподавателей\n"
            f"*Показано:* {showing_start}-{showing_end}\n\n"
            f"Выберите преподавателя:"
        )
        
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        error_text = f"❌ Ошибка при поиске преподавателей: {str(e)}"
        if query:
            await query.edit_message_text(error_text)
        else:
            await update.message.reply_text(error_text)

def _get_teacher_index(user_id: int, teacher_name: str, state_service: UserStateService) -> int | None:
    """Получает индекс преподавателя по имени из state_service"""
    for key in ('teachers',):
        teachers_list = state_service.get_user_list(user_id, key)
        if teachers_list and teacher_name in teachers_list:
            return teachers_list.index(teacher_name)
    return None