# handlers/callbacks/teacher_callbacks.py
from telegram import Update
from telegram.ext import ContextTypes

class TeacherCallbackHandler:
    """Обработчик callback'ов для работы с преподавателями"""
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает teacher_* callback'ы"""
        query = update.callback_query
        
        if callback_data == "menu_teacher":
            await self._handle_teacher_menu(update, context)
        elif callback_data == "teacher_search_input":
            await self._handle_teacher_search_input(update, context)
        elif callback_data == "teacher_show_all":
            await self._handle_show_all_teachers(update, context)
        elif callback_data.startswith("teacher_show_all_"):
            await self._handle_teacher_pagination(update, context, callback_data)
        elif callback_data.startswith("teacher_search_"):
            await self._handle_teacher_search_pagination(update, context, callback_data)
        elif callback_data.startswith("teacher_"):
            await self._handle_teacher_selection(update, context, callback_data)
        else:
            await query.answer("❌ Неизвестная команда преподавателя")
    
    async def _handle_teacher_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает переход в меню преподавателей"""
        from handlers.teachers.teacher_menu import teacher_menu_handler
        await teacher_menu_handler(update, context)
    
    async def _handle_teacher_search_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает запрос на ввод фамилии преподавателя"""
        from handlers.teachers.teacher_menu import handle_teacher_search_input
        await handle_teacher_search_input(update, context)
    
    async def _handle_show_all_teachers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает показ всех преподавателей"""
        from handlers.teachers.teacher_menu import show_all_teachers
        await show_all_teachers(update, context)
    
    async def _handle_teacher_pagination(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает пагинацию списка преподавателей"""
        try:
            page = int(callback_data.replace("teacher_show_all_", ""))
            from handlers.teachers.teacher_menu import show_all_teachers
            await show_all_teachers(update, context, page)
        except ValueError:
            await update.callback_query.answer("❌ Ошибка пагинации")
    
    async def _handle_teacher_search_pagination(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает пагинацию результатов поиска преподавателей"""
        try:
            prefix = "teacher_search_"
            if not callback_data.startswith(prefix):
                await update.callback_query.answer("❌ Ошибка пагинации")
                return
            rest = callback_data[len(prefix):]
            search_query, page_str = rest.rsplit('_', 1)
            page = int(page_str)
            from handlers.teachers.teacher_menu import handle_teacher_search_results
            await handle_teacher_search_results(update, context, search_query, page)
        except (ValueError, IndexError):
            await update.callback_query.answer("❌ Ошибка пагинации")
    
    async def _handle_teacher_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
        """Обрабатывает выбор преподавателя"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        # Разбираем callback_data: "teacher_today_Иванов" или "teacher_today_idx_0"
        parts = callback_data.split('_', 2)
        if len(parts) < 3:
            await query.answer("❌ Ошибка в данных преподавателя")
            return
        
        schedule_type = parts[1]  # today, tomorrow, week
        
        # Определяем формат callback_data
        if parts[2].startswith("idx_") and len(parts[2]) > 4:
            # Формат: teacher_today_idx_0 (по индексу)
            try:
                teacher_index = int(parts[2][4:])
                state_service = context.bot_data.get('state_service')
                
                if state_service:
                    teachers_list = state_service.get_user_list(user_id, 'teachers')
                    if teachers_list and 0 <= teacher_index < len(teachers_list):
                        teacher_name = teachers_list[teacher_index]
                        from handlers.teachers.teacher_menu import handle_teacher_selection
                        await handle_teacher_selection(update, context, teacher_name, schedule_type)
                        return
                    else:
                        await query.answer("❌ Список преподавателей устарел")
                        return
                else:
                    await query.answer("❌ Сервис состояния не доступен")
                    return
            except (ValueError, IndexError):
                await query.answer("❌ Ошибка в данных")
                return
        else:
            # Старый формат для обратной совместимости
            teacher_name = parts[2]
            from handlers.teachers.teacher_menu import handle_teacher_selection
            await handle_teacher_selection(update, context, teacher_name, schedule_type)