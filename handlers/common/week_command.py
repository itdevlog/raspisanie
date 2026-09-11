from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from services.schedule_service import ScheduleService
from handlers.common.messaging import reply_long_message, log_user_error

async def week_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /week <класс> - показывает расписание на неделю"""
    user = update.effective_user
    user_service = context.bot_data.get('user_service')
    schools_data = context.bot_data.get('schools_data', {})
    
    if not user_service or not schools_data:
        await update.message.reply_text("❌ Сервис не доступен")
        return
    
    # Получаем выбранную школу пользователя
    current_school_id = user_service.get_user_school(user.id)
    school_data = schools_data.get(current_school_id)
    
    if not school_data:
        await update.message.reply_text("❌ Данные для вашей школы не загружены")
        return
    
    # Создаем сервис ОДИН РАЗ
    schedule_service = ScheduleService(school_data)
    
    if not context.args:
        # Показываем список классов
        available_classes = schedule_service.get_available_classes()
        
        if not available_classes:
            await update.message.reply_text("❌ Нет доступных классов в расписании")
            return
        
        classes_text = "\n".join([f"• {cls}" for cls in available_classes[:10]])
        if len(available_classes) > 10:
            classes_text += f"\n• ... и еще {len(available_classes) - 10} классов"
        
        await update.message.reply_text(
            f"📚 *Расписание на неделю*\n\n"
            f"Доступные классы:\n{classes_text}\n\n"
            "Использование: /week <класс>\n"
            "Пример: /week 5и",
            parse_mode='Markdown'
        )
        return
    
    class_name = ' '.join(context.args)
    
    # Проверяем существование класса
    available_classes = schedule_service.get_available_classes()
    
    # ИСПРАВЛЕННАЯ ПРОВЕРКА: точное сравнение
    class_exists = False
    exact_class_name = None
    
    for cls in available_classes:
        if class_name.lower() == cls.lower():
            class_exists = True
            exact_class_name = cls  # Сохраняем правильное написание
            break
    
    if not class_exists:
        await update.message.reply_text(
            f"❌ Класс '{class_name}' не найден\n\n"
            "Доступные классы:\n" + 
            "\n".join([f"• {cls}" for cls in available_classes[:10]]),
            parse_mode='Markdown'
        )
        return
    
    # Показываем что идет обработка
    processing_msg = await update.message.reply_text("🔄 Формируем расписание на неделю...")
    
    try:
        # Используем правильное написание класса
        week_schedule = schedule_service.get_class_schedule_week(exact_class_name or class_name)
        
        await reply_long_message(update, context, week_schedule)
    
    except Exception as e:
        await update.message.reply_text(
            log_user_error("Failed to build week schedule", e),
            parse_mode='Markdown'
        )
    
    # Удаляем сообщение о обработке
    await processing_msg.delete()