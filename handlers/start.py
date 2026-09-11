from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config.schools import SCHOOLS_CONFIG
from services.status_service import StatusService

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start - показывает главное меню"""
    user = update.effective_user
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})
    
    # Приветственное сообщение
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот для просмотра школьного расписания.\n\n"
        "🎯 *С чего начать:*\n"
        "1. Выберите школу\n" 
        "2. Выберите класс через любое расписание\n"
        "3. Получайте расписание с заменами 🔄\n\n"
        "💡 *Быстрый доступ:*\n"
        "• Ваш класс сохраняется автоматически\n"
        "• Расписание обновляется каждый час\n\n"
        "👇 *Выберите нужный пункт ниже:*"
    )
    
    # Получаем текущую школу и класс пользователя
    current_school_id = user_service.get_user_school(user.id) if user_service else None
    current_school_name = "Не выбрана"
    current_class = user_service.get_current_class(user.id) if user_service else None
    
    # Получаем статус данных
    status_service = StatusService(schools_data)
    school_status = status_service.get_school_status(current_school_id) if current_school_id else None
    
    if user_service and current_school_id:
        school_config = None
        for school in SCHOOLS_CONFIG.values():
            if school['id'] == current_school_id:
                school_config = school
                break
        if school_config:
            current_school_name = school_config['name']
    
    # Создаем клавиатуру в зависимости от того, выбран ли класс
    keyboard = []
    
    if current_class:
        # Меню когда класс выбран
        keyboard.extend([
            [
                InlineKeyboardButton(f"📅 {current_class} - Сегодня", callback_data=f"class_today_{current_class}"),
                InlineKeyboardButton(f"📆 {current_class} - Завтра", callback_data=f"class_tomorrow_{current_class}"),
                InlineKeyboardButton(f"🗓️ {current_class} - Неделя", callback_data=f"class_week_{current_class}")
            ],
            [
                InlineKeyboardButton("👨‍🏫 Преподаватель", callback_data="menu_teacher"),
                InlineKeyboardButton("🏫 Кабинеты", callback_data="menu_room")
            ],
            [
                InlineKeyboardButton("🔄 Сменить класс", callback_data="change_class"),
                InlineKeyboardButton("🏫 Сменить школу", callback_data="menu_change_school")
            ],
            [
                InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help"),
                InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings"),
                InlineKeyboardButton("🏫 О школе", callback_data="menu_school_info")
            ]
        ])
    else:
        # Меню когда класс не выбран
        keyboard.extend([
            [InlineKeyboardButton("📅 Сегодня", callback_data="menu_today"),
             InlineKeyboardButton("📆 Завтра", callback_data="menu_tomorrow")],
            [
                InlineKeyboardButton("🗓️ Неделя", callback_data="menu_week"),
                InlineKeyboardButton("👨‍🏫 Преподаватель", callback_data="menu_teacher")],
             [
                InlineKeyboardButton("🏫 Кабинеты", callback_data="menu_room"),
                InlineKeyboardButton("🏫 Сменить школу", callback_data="menu_change_school")
            ],
            [
                InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help"),
                InlineKeyboardButton("🏫 О школе", callback_data="menu_school_info")
            ]
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Формируем текст с учетом статуса данных
    text = welcome_text + f"\n\n🏠 *Главное меню*\n\n"
    text += f"🏫 Текущая школа: *{current_school_name}*\n"
    
    # Добавляем статус данных, если школа выбрана
    if current_school_id and school_status:
        if school_status['loaded']:
            status_icon = "✅" if "Актуально" in school_status['status'] else "⚠️"
            text += f"📊 Статус: {status_icon} {school_status['details']}\n"
        else:
            text += f"📊 Статус: ❌ Данные не загружены\n"
    
    if current_class:
        text += f"📚 Текущий класс: *{current_class}*\n"
    
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help - показывает справку"""
    user = update.effective_user

    help_text = (
        "📚 *Помощь по боту расписания*\n\n"
        
        "🏠 *Главное меню:*\n"
        "• *Класс - Сегодня/Завтра/Неделя* - быстрый доступ к расписанию вашего класса\n"
        "• *👨‍🏫 Преподаватель* - поиск и расписание преподавателей\n"
        "• *Сменить класс* - выбрать другой класс\n"
        "• *Сменить школу* - выбрать другую школу\n"
        "• *О школе* - информация о текущей школе\n\n"
        
        "📅 *Основные разделы:*\n"
        "• *Сегодня* - расписание на сегодня\n" 
        "• *Завтра* - расписание на завтра\n"
        "• *Неделя* - расписание на всю неделю\n"
        "• *👨‍🏫 Преподаватель* - удобный поиск преподавателей\n\n"
        
        "🎯 *Как пользоваться:*\n"
        "1. Выберите школу\n"
        "2. Выберите класс через любой раздел расписания\n"
        "3. Класс сохранится для быстрого доступа\n"
        "4. Используйте `/start` для быстрого доступа к расписанию\n\n"
        
        "🔧 *Основные команды:*\n"
        "`/start` - Главное меню\n"
        "`/help` - Эта справка\n\n"
        
        "💡 *Новые возможности:*\n"
        "• *Удобное меню преподавателей* - поиск и выбор из списка\n"
        "• *Расписание преподавателя* - на сегодня, завтра и неделю\n"
        "• *Быстрая навигация* - переход между днями для одного преподавателя\n\n"
        
        "❓ *Частые вопросы:*\n"
        "• *Как посмотреть расписание преподавателя?* - Нажмите '👨‍🏫 Преподаватель' в главном меню\n"
        "• *Как сменить класс?* - Нажмите 'Сменить класс' в главном меню\n"
        "• *Нет моей школы?* - Школа временно не поддерживается\n"
        "• *Ошибка в расписании?* - Сообщите администраторам школы"
    )
    
    keyboard = [
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        [InlineKeyboardButton("📚 Выбрать класс", callback_data="menu_today")],
        [InlineKeyboardButton("🏫 Сменить школу", callback_data="menu_change_school")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')