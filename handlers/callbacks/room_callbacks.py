# handlers/callbacks/room_callbacks.py
from telegram import Update
from telegram.ext import ContextTypes

from handlers.common.typing import require_query, require_user, require_user_data


class RoomCallbackHandler:
    """Обработчик callback'ов для работы с кабинетами"""

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает room_* callback'ы"""
        query = require_query(update)

        if callback_data == "room_search_input":
            await self._handle_room_search_input(update, context)
        elif callback_data == "room_search_cancel":
            from handlers.rooms.room_schedule import room_menu_handler
            await room_menu_handler(update, context)
        elif callback_data == "room_free_now":
            from handlers.rooms.room_schedule import free_rooms_handler
            await free_rooms_handler(update, context)
        elif callback_data == "room_show_all":
            await self._handle_show_all_rooms(update, context)
        elif callback_data.startswith("room_show_all_"):
            await self._handle_room_pagination(update, context, callback_data)
        elif callback_data == "room_search_pages_info":
            await query.answer("Используйте кнопки навигации по страницам")
        elif callback_data == "room_pages_info":
            await query.answer("Используйте кнопки навигации по страницам")
        elif callback_data.startswith("room_search_page_"):
            await self._handle_room_search_pagination(update, context, callback_data)
        elif callback_data.startswith("room_subscribe_"):
            from handlers.rooms.room_schedule import handle_room_subscription
            await handle_room_subscription(update, context, callback_data)
        elif callback_data.startswith("room_"):
            await self._handle_room_selection(update, context, callback_data)
        else:
            await query.answer("❌ Неизвестная команда кабинета")

    async def _handle_room_search_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает запрос на ввод номера кабинета"""
        from handlers.rooms.room_schedule import handle_room_search_input
        await handle_room_search_input(update, context)

    async def _handle_show_all_rooms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает показ всех кабинетов"""
        from handlers.rooms.room_schedule import show_all_rooms
        await show_all_rooms(update, context)

    async def _handle_room_pagination(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает пагинацию списка кабинетов"""
        try:
            page = int(callback_data.replace("room_show_all_", ""))
            from handlers.rooms.room_schedule import show_all_rooms
            await show_all_rooms(update, context, page)
        except ValueError:
            await require_query(update).answer("❌ Ошибка пагинации")

    async def _handle_room_search_pagination(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает пагинацию результатов поиска кабинетов"""
        try:
            page = int(callback_data.replace("room_search_page_", ""))
            search_query = require_user_data(context).get('room_search_query', '')
            if not search_query:
                await require_query(update).answer("❌ Поисковый запрос не найден")
                return
            from handlers.rooms.room_schedule import handle_room_search_results
            await handle_room_search_results(update, context, search_query, page)
        except (ValueError, IndexError):
            await require_query(update).answer("❌ Ошибка пагинации")

    async def _handle_room_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает выбор кабинета"""
        query = require_query(update)
        user_id = require_user(update).id

        # Разбираем callback_data: "room_today_101" или "room_today_idx_0"
        parts = callback_data.split('_', 2)
        if len(parts) < 3:
            await query.answer("❌ Ошибка в данных кабинета")
            return

        schedule_type = parts[1]  # today, tomorrow, week

        # Определяем формат callback_data
        if parts[2].startswith("sidx_") and len(parts[2]) > 5:
            # Формат: room_today_sidx_0 — индекс из результатов поиска
            try:
                room_index = int(parts[2][5:])
                state_service = context.bot_data.get('state_service')

                if state_service:
                    rooms_list = state_service.get_user_list(user_id, 'search_rooms')
                    if rooms_list and 0 <= room_index < len(rooms_list):
                        room_name = rooms_list[room_index]
                        from handlers.rooms.room_schedule import handle_room_selection
                        await handle_room_selection(update, context, room_name, schedule_type)
                        return
                    else:
                        # Список устарел — перерисовываем актуальные результаты вместо мёртвого тоста
                        from handlers.rooms.room_schedule import handle_room_search_results
                        await handle_room_search_results(
                            update, context,
                            require_user_data(context).get('room_search_query', ''),
                            state_service.get_user_page(user_id, 'search_rooms', 0)
                        )
                        return
                else:
                    await query.answer("❌ Сервис состояния не доступен")
                    return
            except (ValueError, IndexError):
                await query.answer("❌ Ошибка в данных")
                return
        elif parts[2].startswith("idx_") and len(parts[2]) > 4:
            # Формат: room_today_idx_0 (по индексу из полного списка)
            try:
                room_index = int(parts[2][4:])
                state_service = context.bot_data.get('state_service')

                if state_service:
                    rooms_list = state_service.get_user_list(user_id, 'rooms')
                    if rooms_list and 0 <= room_index < len(rooms_list):
                        room_name = rooms_list[room_index]
                        from handlers.rooms.room_schedule import handle_room_selection
                        await handle_room_selection(update, context, room_name, schedule_type)
                        return
                    else:
                        # Список устарел — перерисовываем актуальный полный список вместо мёртвого тоста
                        from handlers.rooms.room_schedule import show_all_rooms
                        await show_all_rooms(
                            update, context,
                            state_service.get_user_page(user_id, 'rooms', 0)
                        )
                        return
                else:
                    await query.answer("❌ Сервис состояния не доступен")
                    return
            except (ValueError, IndexError):
                await query.answer("❌ Ошибка в данных")
                return
        else:
            # Старый формат для обратной совместимости
            room_name = parts[2]
            from handlers.rooms.room_schedule import handle_room_selection
            await handle_room_selection(update, context, room_name, schedule_type)
