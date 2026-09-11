# handlers/callbacks/__init__.py
from telegram import Update
from telegram.ext import ContextTypes
from .class_callbacks import ClassCallbackHandler
from .teacher_callbacks import TeacherCallbackHandler
from .room_callbacks import RoomCallbackHandler
from .admin_callbacks import AdminCallbackHandler
from .navigation_callbacks import NavigationCallbackHandler

class CallbackRouter:
    """
    Главный роутер для всех callback'ов
    Заменяет гигантскую функцию callback_handler
    """
    
    def __init__(self):
        self.handlers = {
            'admin': AdminCallbackHandler(),
            'teacher': TeacherCallbackHandler(),
            'room': RoomCallbackHandler(),
            'class': ClassCallbackHandler(),
            'menu': NavigationCallbackHandler(),
            'school': NavigationCallbackHandler(),
            'show_all': NavigationCallbackHandler(),
            'clear_digit': NavigationCallbackHandler(),
            'class_digit': NavigationCallbackHandler(),
            'main_menu': NavigationCallbackHandler(),
            'change_class': NavigationCallbackHandler(),
            'toggle_notifications': NavigationCallbackHandler(),
            'toggle_update_notifications': NavigationCallbackHandler()
        }
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает все callback'ы через соответствующие обработчики"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        # Определяем тип обработчика по префиксу callback_data
        handler_key = self._get_handler_key(callback_data)
        handler = self.handlers.get(handler_key)
        
        if handler:
            await handler.handle(update, context, callback_data)
        else:
            # Если не нашли обработчик, пробуем навигацию как fallback
            await self.handlers['menu'].handle(update, context, callback_data)
    
    def _get_handler_key(self, callback_data: str) -> str:
        """Определяет тип обработчика по callback_data"""
        # Сначала проверяем class_digit - это навигация, а не выбор класса
        if callback_data.startswith('class_digit_'):
            return 'class_digit'
        elif callback_data.startswith('admin_'):
            return 'admin'
        elif callback_data.startswith('teacher_'):
            return 'teacher'
        elif callback_data.startswith('room_'):
            return 'room'
        elif callback_data.startswith('class_'):
            return 'class'
        elif callback_data.startswith('menu_'):
            return 'menu'
        elif callback_data.startswith('school_'):
            return 'school'
        elif callback_data.startswith('show_all_'):
            return 'show_all'
        elif callback_data.startswith('clear_digit_'):
            return 'clear_digit'
        elif callback_data.startswith('toggle_notifications_'):
            return 'toggle_notifications'
        elif callback_data.startswith('toggle_update_notifications_'):
            return 'toggle_update_notifications'
        elif callback_data in ['main_menu', 'change_class']:
            return callback_data
        
        # По умолчанию используем навигацию
        return 'menu'

# Создаем глобальный экземпляр роутера
callback_router = CallbackRouter()

async def callback_handler(update, context):
    await callback_router.handle(update, context)