# handlers/common/entity_menu.py
"""Общий обработчик меню «сущность» (преподаватели / кабинеты).

teacher_menu.py и room_schedule.py раньше дублировали ~90% кода (меню, поиск,
пагинация, выбор, «Сегодня/Завтра/Неделя»). Здесь — один параметризованный класс
`EntityMenuHandler`, различающий сущности через конфиг (надписи, callback-префиксы,
ключи state_service, сервис и его методы). Каждый модуль-обёртка лишь задаёт конфиг
и держит прежние имена публичных функций, чтобы callbacks-обработчики не менялись.
"""

from dataclasses import dataclass, field
from typing import Callable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.schools import SCHOOLS_CONFIG
from handlers.common.messaging import clear_search_flags, edit_long_message
from services.state_service import UserStateService


@dataclass
class EntityConfig:
    """Конфигурация сущности (преподаватель/кабинет) для EntityMenuHandler."""

    entity: str                        # 'teacher' | 'room' — основа callback-префиксов
    label_singular: str                # 'преподаватель' | 'кабинет'
    label_plural: str                  # 'преподавателей' | 'кабинетов'
    icon: str                          # '👨‍🏫' | '🏫'
    menu_title: str                    # 'Поиск преподавателя' | 'Расписание кабинетов'
    search_input_hint: str             # подсказка для ввода поиска
    search_example: str                # 'Например: *Иванов* или *Петрова*'
    empty_data_msg: str                # '❌ Нет данных о преподавателях...'
    button_truncate: int               # 20 (teacher) / 15 (room)
    state_full_key: str                # 'teachers' | 'rooms'
    state_search_key: str              # 'search_teachers' | 'search_rooms'
    search_query_key: str              # 'teacher_search_query' | 'room_search_query'

    # Фабрика сервиса из school_data
    service_factory: Callable = field(default=None)
    # методы сервиса (строки-имена)
    get_all_method: str = 'get_available_teachers'
    search_method: str = 'search_teachers'
    schedule_today_method: str = 'get_teacher_schedule_today'
    schedule_tomorrow_method: str = 'get_teacher_schedule_tomorrow'
    schedule_week_method: str = 'get_teacher_schedule_week'


class EntityMenuHandler:
    """Реализует всё меню сущности (список, поиск, пагинация, выбор, дневные кнопки).

    Инстанс создаётся один на сущность с нужным EntityConfig; методы с теми же
    именами, что и старые публичные функции в teacher_menu/room_schedule,
    поэтому обёртки могут просто делегировать сюда.
    """

    def __init__(self, cfg: EntityConfig):
        self.cfg = cfg
        self.p = cfg.entity              # префикс callback_data: 'teacher' / 'room'
        self.n = cfg.label_singular      # 'преподаватель' / 'кабинет'

    # ---------- helpers ----------

    @staticmethod
    def _school_name(school_data: dict | None, current_school_id: str) -> str:
        cfg_school = SCHOOLS_CONFIG.get(current_school_id, {})
        return cfg_school.get('name') or 'Неизвестно'

    def _edit_or_reply(self, update, context, text, reply_markup=None, parse_mode='Markdown'):
        query = update.callback_query
        if query:
            return query.edit_message_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

    # ---------- меню ----------

    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает меню сущности."""
        clear_search_flags(context)
        user_id = update.effective_user.id

        user_service = context.bot_data.get('user_service')
        schools_data = context.bot_data.get('schools_data', {})

        if not user_service or not schools_data:
            return await self._edit_or_reply(update, context, "❌ Сервис не доступен")

        current_school_id = user_service.get_user_school(user_id)
        school_data = schools_data.get(current_school_id)
        if not school_data:
            return await self._edit_or_reply(update, context, "❌ Данные для вашей школы не загружены")

        try:
            service = self.cfg.service_factory(school_data)
            available = getattr(service, self.cfg.get_all_method)()

            if not available:
                return await self._edit_or_reply(update, context, self.cfg.empty_data_msg)

            school_name = self._school_name(school_data, current_school_id)
            return await self.show_search_menu(update, context, school_name, available)

        except Exception as e:
            return await self._edit_or_reply(
                update, context, f"❌ Ошибка при загрузке списка {self.cfg.label_plural}: {e}")

    async def show_search_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               school_name: str, available: list):
        """Меню «поиск или показать все»."""
        text = (
            f"{self.cfg.icon} *{school_name}*\n"
            f"*{self.cfg.menu_title}*\n\n"
            f"Всего {self.cfg.label_plural}: {len(available)}\n\n"
            f"Выберите действие:"
        )
        keyboard = [
            [InlineKeyboardButton("🔍 Поиск", callback_data=f"{self.p}_search_input")],
            [InlineKeyboardButton("📋 Показать все", callback_data=f"{self.p}_show_all_0")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")],
        ]
        return await self._edit_or_reply(update, context, text, InlineKeyboardMarkup(keyboard))

    # ---------- показ всех (пагинация) ----------

    async def show_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
        clear_search_flags(context)
        query = update.callback_query
        user_id = update.effective_user.id
        user_service = context.bot_data.get('user_service')
        schools_data = context.bot_data.get('schools_data', {})
        state_service = context.bot_data.get('state_service')

        if not user_service or not schools_data:
            return await query.edit_message_text("❌ Сервис не доступен")

        current_school_id = user_service.get_user_school(user_id)
        school_data = schools_data.get(current_school_id)
        if not school_data:
            return await query.edit_message_text("❌ Данные для вашей школы не загружены")

        try:
            service = self.cfg.service_factory(school_data)
            all_items = getattr(service, self.cfg.get_all_method)()

            if not all_items:
                return await query.edit_message_text(
                    f"❌ Нет данных о {self.cfg.label_plural}")

            all_items.sort()

            per_page = 30
            total = len(all_items)
            total_pages = (total + per_page - 1) // per_page
            if page < 0:
                page = 0
            elif page >= total_pages:
                page = total_pages - 1

            state_service.set_user_list(user_id, self.cfg.state_full_key, all_items)
            state_service.set_user_page(user_id, self.cfg.state_full_key, page)

            start_index = page * per_page
            end_index = min(start_index + per_page, total)
            on_page = all_items[start_index:end_index]

            keyboard = []
            row = []
            for local_index, name in enumerate(on_page):
                global_index = start_index + local_index
                button_text = name[:self.cfg.button_truncate] + "..." \
                    if len(name) > self.cfg.button_truncate else name
                row.append(InlineKeyboardButton(button_text,
                         callback_data=f"{self.p}_today_idx_{global_index}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

            pag_buttons = []
            if page > 0:
                pag_buttons.append(InlineKeyboardButton("◀️ Назад",
                    callback_data=f"{self.p}_show_all_{page-1}"))
            pag_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}",
                callback_data=f"{self.p}_pages_info"))
            if page < total_pages - 1:
                pag_buttons.append(InlineKeyboardButton("Вперёд ▶️",
                    callback_data=f"{self.p}_show_all_{page+1}"))
            if pag_buttons:
                keyboard.append(pag_buttons)

            keyboard.append([InlineKeyboardButton("🔍 Поиск", callback_data=f"{self.p}_search_input")])
            keyboard.append([
                InlineKeyboardButton("🔙 Назад", callback_data=f"menu_{self.p}"),
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ])

            text = (
                f"{self.cfg.icon} *Все {self.cfg.label_plural}*\n\n"
                f"*Всего:* {total} {self.cfg.label_plural}\n"
                f"*Показано:* {start_index+1}-{end_index}\n\n"
                f"Выберите {self.cfg.label_singular}:"
            )
            return await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard),
                                                 parse_mode='Markdown')
        except Exception as e:
            return await query.edit_message_text(
                f"❌ Ошибка при загрузке списка {self.cfg.label_plural}: {e}")

    # ---------- выбор сущности (расписание) ----------

    async def select(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                     entity_name: str, schedule_type: str = "today"):
        query = update.callback_query
        user_id = update.effective_user.id
        user_service = context.bot_data.get('user_service')
        schools_data = context.bot_data.get('schools_data', {})
        state_service = context.bot_data.get('state_service')

        if not user_service or not schools_data:
            return await query.edit_message_text("❌ Сервис не доступен")
        current_school_id = user_service.get_user_school(user_id)
        school_data = schools_data.get(current_school_id)
        if not school_data:
            return await query.edit_message_text("❌ Данные для вашей школы не загружены")

        await query.edit_message_text(f"🔄 Загружаем расписание для {self.n} {entity_name}...")

        try:
            service = self.cfg.service_factory(school_data)
            if schedule_type == "today":
                schedule = getattr(service, self.cfg.schedule_today_method)(entity_name)
            elif schedule_type == "tomorrow":
                schedule = getattr(service, self.cfg.schedule_tomorrow_method)(entity_name)
            elif schedule_type == "week":
                schedule = getattr(service, self.cfg.schedule_week_method)(entity_name)
            else:
                schedule = getattr(service, self.cfg.schedule_today_method)(entity_name)

            keyboard = []
            other_days = []
            source, idx = self._resolve_source(user_id, entity_name, state_service)
            suffix = 'sidx' if source == 'search' else 'idx'
            if schedule_type != "today" and idx is not None:
                other_days.append(InlineKeyboardButton("📅 Сегодня",
                    callback_data=f"{self.p}_today_{suffix}_{idx}"))
            if schedule_type != "tomorrow" and idx is not None:
                other_days.append(InlineKeyboardButton("📆 Завтра",
                    callback_data=f"{self.p}_tomorrow_{suffix}_{idx}"))
            if schedule_type != "week" and idx is not None:
                other_days.append(InlineKeyboardButton("🗓️ Неделя",
                    callback_data=f"{self.p}_week_{suffix}_{idx}"))
            if other_days:
                keyboard.append(other_days)

            keyboard.append([
                InlineKeyboardButton("🔄 Обновить", callback_data=f"{self.p}_{schedule_type}_{suffix}_{idx}"
                                     if idx is not None else f"{self.p}_{schedule_type}_{entity_name}"),
                InlineKeyboardButton("🔍 Найти другого", callback_data=f"menu_{self.p}"),
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ])

            return await edit_long_message(
                update, context, query, schedule, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            return await query.edit_message_text(
                f"❌ Произошла ошибка при загрузке расписания:\n{e}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"menu_{self.p}")]
                ]))

    def _resolve_source(self, user_id: int, entity_name: str, state_service: UserStateService) -> tuple:
        """Возвращает (source, index): source — 'search' или 'full'."""
        search_list = state_service.get_user_list(user_id, self.cfg.state_search_key)
        if search_list and entity_name in search_list:
            return ('search', search_list.index(entity_name))
        full_list = state_service.get_user_list(user_id, self.cfg.state_full_key)
        if full_list and entity_name in full_list:
            return ('full', full_list.index(entity_name))
        return ('full', None)

    # ---------- поиск ----------

    async def search_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        context.user_data[f'waiting_for_{self.p}_search'] = True

        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data=f"{self.p}_search_cancel")],
            [InlineKeyboardButton("🔙 Назад", callback_data=f"menu_{self.p}")],
        ]
        text = (
            f"🔍 *{self.cfg.menu_title}*\n\n"
            f"{self.cfg.search_input_hint}:\n"
            f"{self.cfg.search_example}"
        )
        return await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard),
                                             parse_mode='Markdown')

    async def search_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отменяет поиск: снимает флаг ожидания и возвращает в меню сущности."""
        clear_search_flags(context)
        return await self.menu(update, context)

    async def search_results(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                             search_query: str, page: int = 0):
        user_id = update.effective_user.id
        user_service = context.bot_data.get('user_service')
        schools_data = context.bot_data.get('schools_data', {})
        state_service = context.bot_data.get('state_service')

        if not user_service or not schools_data:
            return await self._edit_or_reply(update, context, "❌ Сервис не доступен")
        current_school_id = user_service.get_user_school(user_id)
        school_data = schools_data.get(current_school_id)
        if not school_data:
            return await self._edit_or_reply(update, context, "❌ Данные для вашей школы не загружены")

        try:
            service = self.cfg.service_factory(school_data)
            found = getattr(service, self.cfg.search_method)(search_query)

            if not found:
                context.user_data.pop(self.cfg.search_query_key, None)
                text = f"❌ {self.cfg.label_plural.capitalize()} со '{search_query}' не найдены"
                keyboard = [
                    [InlineKeyboardButton("🔍 Попробовать снова", callback_data=f"{self.p}_search_input")],
                    [InlineKeyboardButton("🔙 Назад", callback_data=f"menu_{self.p}")],
                ]
                return await self._edit_or_reply(update, context, text, InlineKeyboardMarkup(keyboard))

            found.sort()
            per_page = 30
            total = len(found)
            total_pages = (total + per_page - 1) // per_page
            if page < 0:
                page = 0
            elif total_pages > 0 and page >= total_pages:
                page = total_pages - 1

            start_index = page * per_page
            end_index = min(start_index + per_page, total)
            on_page = found[start_index:end_index]

            if not state_service:
                return await update.message.reply_text("❌ Сервис временно не доступен")

            context.user_data[self.cfg.search_query_key] = search_query
            state_service.set_user_list(user_id, self.cfg.state_search_key, found)
            state_service.set_user_page(user_id, self.cfg.state_search_key, page)

            keyboard = []
            row = []
            for local_index, name in enumerate(on_page):
                global_index = start_index + local_index
                button_text = name[:self.cfg.button_truncate] + "..." \
                    if len(name) > self.cfg.button_truncate else name
                row.append(InlineKeyboardButton(button_text,
                         callback_data=f"{self.p}_today_sidx_{global_index}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

            pag = []
            if page > 0:
                pag.append(InlineKeyboardButton("◀️ Назад", callback_data=f"{self.p}_search_page_{page-1}"))
            pag.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data=f"{self.p}_search_pages_info"))
            if page < total_pages - 1:
                pag.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"{self.p}_search_page_{page+1}"))
            if pag:
                keyboard.append(pag)

            keyboard.append([InlineKeyboardButton("🔍 Новый поиск", callback_data=f"{self.p}_search_input")])
            keyboard.append([
                InlineKeyboardButton("🔙 Назад", callback_data=f"menu_{self.p}"),
                InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")
            ])

            text = (
                f"🔍 *Результаты поиска:* '{search_query}'\n\n"
                f"*Найдено:* {total} {self.cfg.label_plural}\n"
                f"*Показано:* {start_index+1}-{end_index}\n\n"
                f"Выберите {self.cfg.label_singular}:"
            )
            return await self._edit_or_reply(update, context, text, InlineKeyboardMarkup(keyboard))
        except Exception as e:
            return await self._edit_or_reply(
                update, context, f"❌ Ошибка при поиске {self.cfg.label_plural}: {e}")
