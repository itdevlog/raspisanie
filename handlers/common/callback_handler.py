# handlers/common/callback_handler.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from services.schedule_service import ScheduleService
from config.schools import SCHOOLS_CONFIG
from typing import List

# Импортируем новый роутер callback'ов
from handlers.callbacks import callback_handler as new_callback_handler

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все callback-и от инлайн-клавиатур (перенаправляет в новый роутер)"""
    await new_callback_handler(update, context)

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ СОЗДАНИЯ КЛАВИАТУР ==========

def create_class_navigation_keyboard(class_name: str, schedule_type: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру навигации для расписания класса"""
    keyboard = []
    
    # Кнопки других дней для этого же класса
    other_days = []
    if schedule_type != "today":
        other_days.append(InlineKeyboardButton("📅 Сегодня", callback_data=f"class_today_{class_name}"))
    if schedule_type != "tomorrow":
        other_days.append(InlineKeyboardButton("📆 Завтра", callback_data=f"class_tomorrow_{class_name}"))
    if schedule_type != "week":
        other_days.append(InlineKeyboardButton("🗓️ Неделя", callback_data=f"class_week_{class_name}"))

    if other_days:
        keyboard.append(other_days)
    
    # Кнопка обновления
    keyboard.append([InlineKeyboardButton("🔄 Обновить", callback_data=f"class_{schedule_type}_{class_name}")])

    # Навигация        
    keyboard.append([
        InlineKeyboardButton("📚 Выбрать класс", callback_data=f"menu_{schedule_type}"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"),
        InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_error_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для сообщений об ошибках"""
    keyboard = [
        [InlineKeyboardButton("🔙 Назад", callback_data="main_menu"),
         InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С КЛАССАМИ ==========

async def handle_change_class(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает смену класса"""
    query = update.callback_query
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    
    if not user_service:
        await query.edit_message_text("❌ Сервис не доступен")
        return
    
    # Очищаем выбранный класс
    user_service.clear_user_class(user_id)
    
    # Всегда используем "today" при смене класса
    await show_class_selection(update, context, "today")

async def show_class_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, schedule_type: str):
    """Показывает меню выбора класса с сначала цифрой, потом буквой"""
    query = update.callback_query
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})

    async def send_text(text: str, reply_markup: InlineKeyboardMarkup):
        if query:
            try:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            except BadRequest as e:
                if "not modified" in str(e).lower():
                    return
                raise
        else:
            await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

    if not user_service or not schools_data:
        await send_text("❌ Сервис не доступен", InlineKeyboardMarkup([]))
        return

    # Получаем выбранную школу пользователя
    current_school_id = user_service.get_user_school(user_id)
    school_data = schools_data.get(current_school_id)

    if not school_data:
        await send_text("❌ Данные для вашей школы не загружены", InlineKeyboardMarkup([]))
        return

    try:
        schedule_service = ScheduleService(school_data)
        available_classes = schedule_service.get_available_classes()

        if not available_classes:
            await send_text("❌ Нет доступных классов в расписании", InlineKeyboardMarkup([]))
            return
        
        # Получаем название текущей школы для отображения
        school_config = None
        for school in SCHOOLS_CONFIG.values():
            if school['id'] == current_school_id:
                school_config = school
                break
        
        school_name = school_config['name'] if school_config else "Неизвестно"
        type_text = {
            "today": "на сегодня",
            "tomorrow": "на завтра", 
            "week": "на неделю"
        }
        
        # Если нет callback_data с цифрой, показываем выбор цифры (1-11) - ИНЛАЙН-КНОПКАМИ
        if not context.user_data.get('class_digit'):
            # Создаем клавиатуру с цифрами 1-11
            keyboard = []
            row = []
            
            for digit in range(1, 12):  # 1-11
                # Проверяем, есть ли классы с этой цифрой
                has_classes = any(cls.startswith(str(digit)) for cls in available_classes)
                if has_classes:
                    row.append(InlineKeyboardButton(str(digit), callback_data=f"class_digit_{digit}_{schedule_type}"))
                    if len(row) == 4:  # 4 кнопки в ряду
                        keyboard.append(row)
                        row = []
            
            if row:  # Добавим оставшиеся кнопки
                keyboard.append(row)
            
            # Кнопка "Все классы сразу"
            keyboard.append([InlineKeyboardButton("📋 Все классы сразу", callback_data=f"show_all_{schedule_type}")])
            
            # Кнопка возврата в главное меню
            keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            text = (
                f"📚 *{school_name}*\n"
                f"Выберите класс *{type_text[schedule_type]}*\n\n"
                f"Сначала выберите цифру класса:"
            )
            
            await send_text(text, reply_markup)

        else:
            # Показываем буквы для выбранной цифры - ИНЛАЙН-КНОПКАМИ
            class_digit = context.user_data['class_digit']
            class_letters = _get_class_letters_for_digit(available_classes, int(class_digit))

            if not class_letters:
                if query:
                    await query.answer("❌ Нет классов с этой цифрой")
                return
            
            keyboard = []
            row = []
            
            for letter in class_letters:
                class_name = f"{class_digit}{letter}"
                row.append(InlineKeyboardButton(class_name, callback_data=f"class_{schedule_type}_{class_name}"))
                if len(row) == 4:  # 4 кнопки в ряду
                    keyboard.append(row)
                    row = []
            
            if row:  # Добавим оставшиеся кнопки
                keyboard.append(row)
            
            # Кнопки навигации
            keyboard.append([
                InlineKeyboardButton("🔙 К выбору цифры", callback_data=f"clear_digit_{schedule_type}"),
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            text = (
                f"📚 *{school_name}*\n"
                f"Выберите класс *{type_text[schedule_type]}*\n\n"
                f"Цифра: *{class_digit}*\n"
                f"Выберите букву:"
            )

            await send_text(text, reply_markup)

    except Exception as e:
        error_text = f"❌ Ошибка при загрузке списка классов: {str(e)}"
        try:
            await send_text(error_text, InlineKeyboardMarkup([]))
        except Exception:
            pass

def _get_class_letters_for_digit(available_classes: List[str], digit: int) -> List[str]:
    """Получает список букв для указанной цифры класса"""
    letters = set()
    for class_name in available_classes:
        if class_name.startswith(str(digit)) and len(class_name) > len(str(digit)):
            # Извлекаем букву (все что после цифры)
            letter = class_name[len(str(digit)):]
            if letter:  # Убедимся что буква не пустая
                letters.add(letter)
    
    return sorted(list(letters))

async def handle_show_all_classes(update: Update, context: ContextTypes.DEFAULT_TYPE, schedule_type: str):
    """Показывает полный список классов (альтернативный способ)"""
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
    
    try:
        schedule_service = ScheduleService(school_data)
        available_classes = schedule_service.get_available_classes()
        
        # Создаем клавиатуру со всеми классами (группируем по цифрам)
        keyboard = []
        
        # Группируем классы по цифрам
        classes_by_digit = {}
        for class_name in available_classes:
            # Извлекаем цифру из названия класса
            digit = ''.join(filter(str.isdigit, class_name))
            if digit:
                if digit not in classes_by_digit:
                    classes_by_digit[digit] = []
                classes_by_digit[digit].append(class_name)
        
        # Создаем строки с кнопками, сгруппированные по цифрам
        for digit in sorted(classes_by_digit.keys(), key=int):
            row = []
            for class_name in sorted(classes_by_digit[digit]):
                row.append(InlineKeyboardButton(class_name, callback_data=f"class_{schedule_type}_{class_name}"))
                if len(row) == 3:  # 3 кнопки в ряду
                    keyboard.append(row)
                    row = []
            if row:  # Добавим оставшиеся кнопки в ряду
                keyboard.append(row)
        
        # Кнопки навигации
        keyboard.append([
            InlineKeyboardButton("🔙 К выбору цифры", callback_data=f"menu_{schedule_type}"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        type_text = {
            "today": "на сегодня",
            "tomorrow": "на завтра",
            "week": "на неделю"
        }
        
        await query.edit_message_text(
            f"📚 Все классы *{type_text[schedule_type]}*:\n\n"
            f"*Всего классов:* {len(available_classes)}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка при загрузке списка классов: {str(e)}")

# ========== ФУНКЦИИ ДЛЯ ИНФОРМАЦИИ И ПОМОЩИ ==========

async def handle_school_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает показ информации о школе через меню"""
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
        await query.edit_message_text("❌ Данные не загружены")
        return
    
    school_name = school_data.get('SCHOOL_NAME', 'Неизвестно')
    city = school_data.get('CITY_NAME', 'Неизвестно')
    export_date = school_data.get('EXPORT_DATE', 'Неизвестно')
    export_time = school_data.get('EXPORT_TIME', 'Неизвестно')
    
    # Статистика
    classes_count = len(school_data.get('CLASSES', {}))
    teachers_count = len(school_data.get('TEACHERS', {}))
    subjects_count = len(school_data.get('SUBJECTS', {}))
    rooms_count = len(school_data.get('ROOMS', {}))
    
    info_text = (
        f"🏫 *{school_name}*\n"
        f"📍 {city}\n\n"
        f"📊 *Статистика:*\n"
        f"• Классов: {classes_count}\n"
        f"• Преподавателей: {teachers_count}\n"
        f"• Предметов: {subjects_count}\n"
        f"• Кабинетов: {rooms_count}\n\n"
        f"🕒 *Данные обновлены:*\n"
        f"{export_date} {export_time}\n\n"
        f"🔗 *Сайт школы:*\n"
        f"{school_data.get('HOMEPAGE_URL', 'Не указан')}"
    )
    
    # Добавляем кнопку возврата
    keyboard = [
        [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu"),
         InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(info_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает показ справки через меню"""
    query = update.callback_query
    
    help_text = (
        "📚 *Помощь по боту расписания*\n\n"
        
        "🏠 *Главное меню:*\n"
        "• *Класс - Сегодня/Завтра/Неделя* - быстрый доступ к расписанию вашего класса\n"
        "• *Сменить класс* - выбрать другой класс\n"
        "• *Сменить школу* - выбрать другую школу\n"
        "• *О школе* - информация о текущей школе\n\n"
        
        "📅 *Основные разделы:*\n"
        "• *Сегодня* - расписание на сегодня\n" 
        "• *Завтра* - расписание на завтра\n"
        "• *Неделя* - расписание на всю неделю\n"
        "• *Учитель* - поиск преподавателя\n\n"
        
        "🎯 *Как пользоваться:*\n"
        "1. Выберите школу в разделе 'Сменить школу'\n"
        "2. Выберите класс через любой раздел расписания\n"
        "3. Класс сохранится для быстрого доступа\n"
        "4. Используйте кнопки класса для быстрого просмотра\n\n"
        
        "🔧 *Основные команды:*\n"
        "`/start` - Главное меню\n"
        "`/help` - Эта справка\n"
        "`/settings` - Настройки уведомлений\n"
        
        "💡 *Особенности:*\n"
        "• Бот автоматически сохраняет ваш класс для каждой школы\n"
        "• Расписание обновляется автоматически\n"
        "• Показываются актуальные замены уроков\n"
        "• Поддерживается поиск по фамилии преподавателя\n"
        "• Уведомления о заменах можно отключить в настройках\n\n"
        
        "❓ *Частые вопросы:*\n"
        "• *Как сменить класс?* - Нажмите 'Сменить класс' в главном меню\n"
        "• *Как отключить уведомления?* - Перейдите в 'Настройки' и выключите уведомления\n"
        "• *Нет моей школы?* - Школа временно не поддерживается\n"
        "• *Нет расписания?* - Данные еще не загружены\n"
        "• *Ошибка в расписании?* - Сообщите администраторам школы"
    )
    
    keyboard = [
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings")],
        [InlineKeyboardButton("📚 Выбрать класс", callback_data="menu_today")],
        [InlineKeyboardButton("🏫 Сменить школу", callback_data="menu_change_school")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')