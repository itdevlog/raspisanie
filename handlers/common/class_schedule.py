from telegram import Update
from telegram.ext import ContextTypes
from services.schedule_service import ScheduleService

async def class_schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения (номера классов и поиск преподавателей)"""
    user_id = update.effective_user.id
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})
    
    message_text = update.message.text.strip()
    
    # Если пользователь ввел номер кабинета для поиска
    if context.user_data.get('waiting_for_room_search'):
        # Очищаем флаг
        del context.user_data['waiting_for_room_search']
        
        # Получаем данные школы пользователя
        if not user_service or not schools_data:
            await update.message.reply_text("❌ Сервис не доступен")
            return
        
        current_school_id = user_service.get_user_school(user_id)
        school_data = schools_data.get(current_school_id)
        
        if not school_data:
            await update.message.reply_text("❌ Данные для вашей школы не загружены")
            return
        
        # Используем функцию поиска кабинетов
        from handlers.rooms.room_schedule import handle_room_search_results
        await handle_room_search_results(update, context, message_text)
        return

    # Если пользователь ввел фамилию учителя (поиск преподавателя)
    if context.user_data.get('waiting_for_teacher') or context.user_data.get('waiting_for_teacher_search'):
        # Очищаем флаги
        if 'waiting_for_teacher' in context.user_data:
            del context.user_data['waiting_for_teacher']
        if 'waiting_for_teacher_search' in context.user_data:
            del context.user_data['waiting_for_teacher_search']
        
        # Получаем данные школы пользователя
        if not user_service or not schools_data:
            await update.message.reply_text("❌ Сервис не доступен")
            return
        
        current_school_id = user_service.get_user_school(user_id)
        school_data = schools_data.get(current_school_id)
        
        if not school_data:
            await update.message.reply_text("❌ Данные для вашей школы не загружены")
            return
        
        # Используем функцию поиска преподавателей
        from handlers.teachers.teacher_menu import handle_teacher_search_results
        await handle_teacher_search_results(update, context, message_text)
        return
    
    # Обработка запроса расписания класса (существующая логика)
    if not user_service or not schools_data:
        await update.message.reply_text("❌ Сервис не доступен")
        return
    
    # Получаем выбранную школу пользователя
    current_school_id = user_service.get_user_school(user_id)
    school_data = schools_data.get(current_school_id)
    
    if not school_data:
        await update.message.reply_text("❌ Данные для вашей школы не загружены")
        return
    
    class_name = message_text
    schedule_service = ScheduleService(school_data)
    
    # Проверяем существование класса
    available_classes = schedule_service.get_available_classes()
    
    # Точное сравнение классов
    class_exists = False
    exact_class_name = None
    
    for cls in available_classes:
        if class_name.lower() == cls.lower():
            class_exists = True
            exact_class_name = cls  # Сохраняем правильное написание
            break
    
    if not class_exists:
        # Предложим выбрать из кнопок
        from handlers.common.callback_handler import show_class_selection
        await show_class_selection(update, context, "today")
        return
    
    # Получаем расписание
    schedule_today = schedule_service.get_class_schedule_today(exact_class_name or class_name)
    schedule_tomorrow = schedule_service.get_class_schedule_tomorrow(exact_class_name or class_name)
    
    response = f"{schedule_today}\n\n"
    response += "➡️ *Завтра:*\n"
    response += schedule_tomorrow
    
    await update.message.reply_text(response, parse_mode='Markdown')