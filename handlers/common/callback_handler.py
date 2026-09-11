# handlers/common/callback_handler.py

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from config.schools import SCHOOLS_CONFIG

# Импортируем новый роутер callback'ов
from handlers.callbacks import callback_handler as new_callback_handler
from handlers.common.messaging import log_user_error, paginate, safe_edit_message
from services.schedule_service import ScheduleService


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все callback-и от инлайн-клавиатур (перенаправляет в новый роутер)"""
    await new_callback_handler(update, context)


def parse_all_classes_page(callback_data: str) -> tuple[str, int] | None:
    """Разбирает 'all_classes_page_{type}_{page}' -> (schedule_type, page).

    Раньше пагинация теряла тип расписания, и после первой страницы
    список классов молча переключался на «сегодня». Теперь тип кодируется
    в callback_data.
    """
    prefix = 'all_classes_page_'
    if not callback_data.startswith(prefix):
        return None
    rest = callback_data[len(prefix):]
    schedule_type, sep, page_str = rest.rpartition('_')
    if not sep or schedule_type not in ('today', 'tomorrow', 'week'):
        return None
    try:
        return schedule_type, int(page_str)
    except ValueError:
        return None

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
        schedule_service = ScheduleService(school_data, school_id=current_school_id)
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
                # Проверяем, есть ли классы с этой цифрой (ровно с цифрой, а не с десятком)
                has_classes = any(_class_matches_digit(cls, digit) for cls in available_classes)
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
        error_text = log_user_error("Failed to load class list", e)
        try:
            await send_text(error_text, InlineKeyboardMarkup([]))
        except Exception:
            pass

def _class_matches_digit(class_name: str, digit: int) -> bool:
    """True, если класс начинается с ровно этой цифры, за которой идёт БУКВА.

    Сравнение по сегментам, а не по `startswith`: цифра «1» не должна матчить
    класс «11а» (это отдельная цифра/десяток). Иначе кнопка «1» показывалась
    даже когда классов вида «1x» нет.
    """
    s = str(digit)
    if not class_name.startswith(s):
        return False
    rest = class_name[len(s):]
    return bool(rest) and not rest[0].isdigit()


def _get_class_letters_for_digit(available_classes: list[str], digit: int) -> list[str]:
    """Получает список букв для указанной цифры класса"""
    letters = set()
    for class_name in available_classes:
        if _class_matches_digit(class_name, digit):
            # Извлекаем букву (все что после цифры)
            letter = class_name[len(str(digit)):]
            if letter:  # Убедимся что буква не пустая
                letters.add(letter)

    return sorted(list(letters))

async def handle_show_all_classes(update: Update, context: ContextTypes.DEFAULT_TYPE, schedule_type: str, page: int = 0):
    """Показывает полный список классов постранично (альтернативный способ).

    При 60+ классах одностраничная клавиатура упиралась бы в лимит 100 кнопок,
    поэтому список классов кэшируется в state_service и разбивается на страницы
    (кнопки-номера «◀️ Назад/Вперёд ▶️» через all_classes_page_{type}_{page}).
    """
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
        schedule_service = ScheduleService(school_data, school_id=current_school_id)
        available_classes = schedule_service.get_available_classes()

        state_service = context.bot_data.get('state_service')
        if state_service:
            # Актуализируем кэш списка классов при первичном вызове (schedule_type != None)
            if schedule_type is not None:
                state_service.set_user_list(user_id, 'all_classes', available_classes)

        page, classes_on_page = paginate(available_classes, page, per_page=60)
        back_schedule = schedule_type or "today"

        # Создаем клавиатуру со всеми классами (группируем по цифрам)
        keyboard = []

        # Группируем классы текущей страницы по цифрам
        classes_by_digit = {}
        for class_name in classes_on_page:
            digit = ''.join(filter(str.isdigit, class_name))
            if digit:
                classes_by_digit.setdefault(digit, []).append(class_name)

        # Кнопки классов сгруппированы по цифрам
        for digit in sorted(classes_by_digit.keys(), key=int):
            row = []
            for class_name in sorted(classes_by_digit[digit]):
                row.append(InlineKeyboardButton(class_name, callback_data=f"class_{schedule_type or 'today'}_{class_name}"))
                if len(row) == 3:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

        # Пагинация
        total_classes = len(available_classes)
        total_pages = (total_classes + 60 - 1) // 60
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(InlineKeyboardButton(
                "◀️ Назад", callback_data=f"all_classes_page_{back_schedule}_{page-1}"))
        pagination_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="all_classes_pages_info"))
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton(
                "Вперёд ▶️", callback_data=f"all_classes_page_{back_schedule}_{page+1}"))
        if pagination_buttons:
            keyboard.append(pagination_buttons)

        # Кнопки навигации
        keyboard.append([
            InlineKeyboardButton("🔙 Назад", callback_data=f"menu_{back_schedule}"),
            InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
        ])

        reply_markup = InlineKeyboardMarkup(keyboard)

        type_text = {
            "today": "на сегодня",
            "tomorrow": "на завтра",
            "week": "на неделю"
        }

        await safe_edit_message(
            query,
            f"📚 Все классы *{type_text[back_schedule]}*:\n\n"
            f"*Всего классов:* {total_classes}\n"
            f"*Страница:* {page+1}/{total_pages}",
            reply_markup=reply_markup
        )

    except Exception as e:
        await safe_edit_message(query, log_user_error("Failed to load class list", e))

# ========== ФУНКЦИИ ДЛЯ ИНФОРМАЦИИ И ПОМОЩИ ==========


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
