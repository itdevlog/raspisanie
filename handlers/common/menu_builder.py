# handlers/common/menu_builder.py
"""Общие строители клавиатуры/текста главного меню.

start.py и main_menu.py раньше дублировали построение клавиатуры и заголовка.
Здесь — единый построитель; оба используют одинаковую раскладку кнопок.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config.schools import SCHOOLS_CONFIG
from services.text_utils import escape_markdown


def build_main_menu_keyboard(current_class: str | None) -> InlineKeyboardMarkup:
    """Клавиатура главного меню; меняется в зависимости от того, выбран ли класс."""
    if current_class:
        rows = [
            [
                InlineKeyboardButton(f"📅 {current_class} - Сегодня", callback_data=f"class_today_{current_class}"),
                InlineKeyboardButton(f"📆 {current_class} - Завтра", callback_data=f"class_tomorrow_{current_class}"),
                InlineKeyboardButton(f"🗓️ {current_class} - Неделя", callback_data=f"class_week_{current_class}"),
            ],
            [
                InlineKeyboardButton("👨‍🏫 Преподаватель", callback_data="menu_teacher"),
                InlineKeyboardButton("🏫 Кабинеты", callback_data="menu_room"),
            ],
            [
                InlineKeyboardButton("🔄 Сменить класс", callback_data="change_class"),
                InlineKeyboardButton("🏫 Сменить школу", callback_data="menu_change_school"),
            ],
            [
                InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help"),
                InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings"),
                InlineKeyboardButton("🏫 О школе", callback_data="menu_school_info"),
            ],
        ]
    else:
        rows = [
            [
                InlineKeyboardButton("📅 Сегодня", callback_data="menu_today"),
                InlineKeyboardButton("📆 Завтра", callback_data="menu_tomorrow"),
                InlineKeyboardButton("🗓️ Неделя", callback_data="menu_week"),
            ],
            [
                InlineKeyboardButton("👨‍🏫 Преподаватель", callback_data="menu_teacher"),
                InlineKeyboardButton("🏫 Кабинеты", callback_data="menu_room"),
                InlineKeyboardButton("🏫 Сменить школу", callback_data="menu_change_school"),
            ],
            [
                InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help"),
                InlineKeyboardButton("🏫 О школе", callback_data="menu_school_info"),
            ],
        ]
    return InlineKeyboardMarkup(rows)


def resolve_school_name(current_school_id: str | None) -> str:
    """Название школы по id из конфигурации (иначе 'Не выбрана')."""
    if not current_school_id:
        return "Не выбрана"
    cfg = SCHOOLS_CONFIG.get(current_school_id, {})
    return cfg.get('name') or "Не выбрана"


def build_main_menu_text(school_status, current_school_id: str | None,
                         current_class: str | None, welcome: str = "") -> str:
    """Текст главного меню с учётом статуса данных и выбранного класса."""
    school_name = resolve_school_name(current_school_id)

    text = welcome
    if welcome:
        text += "\n\n"
    text += "🏠 *Главное меню*\n\n"
    text += f"🏫 Текущая школа: *{escape_markdown(school_name)}*\n"

    if current_school_id and school_status:
        if school_status['loaded']:
            status_icon = "✅" if "Актуально" in school_status['status'] else "⚠️"
            text += f"📊 Статус: {status_icon} {school_status['details']}\n"
        else:
            text += "📊 Статус: ❌ Данные не загружены\n"

    if current_class:
        text += f"📚 Текущий класс: *{escape_markdown(current_class)}*\n"

    text += "\nВыберите нужный пункт:"
    return text


HELP_TEXT = (
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


def build_help_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для справки."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="menu_settings")],
        [InlineKeyboardButton("📚 Выбрать класс", callback_data="menu_today")],
        [InlineKeyboardButton("🏫 Сменить школу", callback_data="menu_change_school")],
    ])
