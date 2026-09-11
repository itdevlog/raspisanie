# services/notification_service.py
from telegram import Update
from telegram.ext import ContextTypes
from config.config import Config, get_timezone
from config.schools import get_display_name
from datetime import datetime
from typing import Dict, List, Set
import logging
import hashlib
import json
import os
import pytz

class NotificationService:
    def __init__(self):
         self.config = Config()
         self.logger = logging.getLogger(__name__)
         # Кэш для отслеживания уже отправленных уведомлений
         self.sent_notifications: Dict[str, Set[str]] = {}
         self.moscow_tz = get_timezone()  # ДОБАВЬТЕ ЭТУ СТРОКУ
         self.logger.info("NotificationService инициализирован с пустым кэшом отправленных уведомлений")
         self.notifications_cache_file = self._get_cache_file()
         self.load_notifications_cache()

    @staticmethod
    def _get_cache_file() -> str:
        """Путь к кэшу уведомлений в общей data-директории (не от cwd)."""
        db_path = Config().DB_PATH
        data_dir = os.path.dirname(db_path) or './data'
        return os.path.join(data_dir, 'notifications_cache.json')
         
    def load_notifications_cache(self):
         """Загружает кэш отправленных уведомлений из файла"""
         try:
             if os.path.exists(self.notifications_cache_file):
                 with open(self.notifications_cache_file, 'r', encoding='utf-8') as f:
                     cache_data = json.load(f)
                     # Преобразуем списки обратно в множества
                     for key, value in cache_data.items():
                         if isinstance(value, list):
                             cache_data[key] = set(value)
                     self.sent_notifications = cache_data
                 self.logger.info(f"Загружен кэш уведомлений из {self.notifications_cache_file}")
             else:
                 self.logger.info("Файл кэша уведомлений не найден, используется пустой кэш")
         except Exception as e:
             self.logger.error(f"Ошибка загрузки кэша уведомлений: {e}")
             self.sent_notifications = {}
             
    def save_notifications_cache(self):
         """Сохраняет кэш отправленных уведомлений в файл"""
         try:
             # Создаем директорию, если она не существует
             os.makedirs(os.path.dirname(self.notifications_cache_file), exist_ok=True)
             
             # Преобразуем множества в списки для JSON сериализации
             cache_data = {}
             for key, value in self.sent_notifications.items():
                 if isinstance(value, set):
                     cache_data[key] = list(value)
                 else:
                     cache_data[key] = value
             
             with open(self.notifications_cache_file, 'w', encoding='utf-8') as f:
                 json.dump(cache_data, f, ensure_ascii=False, indent=2)
             self.logger.info(f"Кэш уведомлений сохранен в {self.notifications_cache_file}")
         except Exception as e:
             self.logger.error(f"Ошибка сохранения кэша уведомлений: {e}")
             
    async def notify_admins(self, context: ContextTypes.DEFAULT_TYPE, message: str, parse_mode: str = 'Markdown'):
        """Отправляет уведомление всем администраторам"""
        try:
            for admin_id in self.config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode=parse_mode
                    )
                except Exception as e:
                    self.logger.error(f"Failed to send notification to admin {admin_id}: {e}")
        except Exception as e:
            self.logger.error(f"Error in notify_admins: {e}")
    
    async def notify_exchange_updates(self, context: ContextTypes.DEFAULT_TYPE, school_id: str,
                                    class_name: str, exchanges: List[Dict]) -> bool:
        """Уведомляет пользователей о новых заменах в формате полного расписания"""
        try:
            # Проверяем, доступен ли bot_data
            if not hasattr(context, 'bot_data') or context.bot_data is None:
                self.logger.error("Context не содержит bot_data")
                return False
            
            user_service = context.bot_data.get('user_service')
            if not user_service:
                self.logger.error("User service not available for exchange notifications")
                return False
            
            # Получаем пользователей, которые следят за этим классом
            users = self._get_users_by_class(user_service, school_id, class_name)
            self.logger.info(f"Найдено {len(users)} пользователей, следящих за классом {class_name} в школе {school_id}")
            if not users:
                self.logger.info(f"No users found for class {class_name} in school {school_id}")
                return False
            
            # Получаем дату из первой замены (предполагаем, что все замены на одну дату)
            date = exchanges[0].get('timestamp') if exchanges else datetime.now(self.moscow_tz)
            
            # Форматируем уведомление
            notification_text = self._format_exchange_notification(class_name, exchanges, date)
            if not notification_text:
                self.logger.info(f"No new exchanges to notify for class {class_name}")
                return False
            
            # Проверяем, не отправляли ли мы уже эти конкретные замены
            # Создаем уникальный ключ для каждой комбинации замен
            import hashlib
            exchanges_signature = "_".join([
                f"{ex.get('lesson_num', '')}_{ex.get('new_subject', '')}_{ex.get('new_teacher', '')}_{ex.get('new_room', '')}_{ex.get('is_cancelled', '')}"
                for ex in exchanges
            ])
            notification_key = f"{school_id}_{class_name}_{date.strftime('%Y%m%d')}_{hashlib.md5(exchanges_signature.encode()).hexdigest()[:8]}"
            
            if self._is_notification_sent(notification_key):
                self.logger.info(f"Notification already sent for {notification_key}")
                return False
            
            # Отправляем уведомления только тем пользователям, у которых включены уведомления
            sent_count = 0
            for user_id in users:
                try:
                    # Проверяем настройки уведомлений пользователя
                    notifications_enabled = user_service.get_user_notification_settings(user_id, school_id)
                    self.logger.info(f"User {user_id} notification setting for school {school_id}: {notifications_enabled}")
                    if not notifications_enabled:
                        self.logger.info(f"Notifications disabled for user {user_id}, skipping notification")
                        continue
                    else:
                        self.logger.info(f"Notifications enabled for user {user_id}, sending notification")

                    try:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=notification_text,
                            parse_mode='Markdown'
                        )
                        sent_count += 1
                        self.logger.info(f"Exchange notification sent to user {user_id}")
                    except Exception as e:
                        self.logger.error(f"Failed to send message to user {user_id}: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing user {user_id} for exchange notification: {e}")

            # Сохраняем в кэш отправленных уведомлений ТОЛЬКО если что-то действительно отправлено
            if sent_count > 0:
                self._mark_notification_sent(notification_key)
                self.save_notifications_cache()

            self.logger.info(f"Exchange notifications sent to {sent_count}/{len(users)} users for class {class_name}")
            return sent_count > 0
            
        except Exception as e:
            self.logger.error(f"Error in notify_exchange_updates: {e}", exc_info=True)
            return False
    
    def _get_users_by_class(self, user_service, school_id: str, class_name: str) -> List[int]:
        """Получает список пользователей, которые следят за указанным классом"""
        try:
            # Получаем всех пользователей
            users_collection = user_service.db.get_collection('users')
            all_users = users_collection.find()
            
            users_watching_class = []
            for user_data in all_users:
                user_id = user_data.get('user_id')
                if not user_id:
                    continue
                
                # Проверяем, следит ли пользователь за этим классом
                user_class = user_service.get_user_class(user_id, school_id)
                self.logger.info(f"Checking user {user_id}: user_class={user_class}, target_class={class_name}")
                if user_class and user_class.lower() == class_name.lower():
                    users_watching_class.append(user_id)
                    self.logger.info(f"User {user_id} added to notification list for class {class_name}")
            
            self.logger.info(f"Found {len(users_watching_class)} users watching class {class_name}")
            return users_watching_class
            
        except Exception as e:
            self.logger.error(f"Error getting users by class: {e}", exc_info=True)
            return []
    
    def _format_exchange_notification(self, class_name: str, exchanges: List[Dict], date: datetime = None) -> str:
        """Форматирует уведомление о заменах в кратком виде"""
        if not exchanges:
            return ""
        
        # Если дата не передана, используем текущую
        if not date:
            date = datetime.now(self.moscow_tz)
        
        # Форматируем сообщение
        date_str = date.strftime('%d.%m.%Y')
        day_name = self._get_day_name(date)
        
        message = [
            f"🔄 *{class_name.upper()} - {day_name}, {date_str}*",
            "",
            "📝 *Новые замены в расписании:*",
            ""
        ]
        
        # Добавляем информацию о заменах
        for exchange in exchanges:
            lesson_num = exchange.get('lesson_num', '?')
            original_subject = exchange.get('original_subject', 'Неизвестно')
            new_subject = exchange.get('new_subject', '')
            new_teacher = exchange.get('new_teacher', '')
            new_room = exchange.get('new_room', '')
            is_cancelled = exchange.get('is_cancelled', False)
            
            # Формируем строку урока
            if is_cancelled:
                lesson_line = f"❌ {lesson_num}. {original_subject} - *ОТМЕНЕНО*"
            else:
                lesson_line = f"🔄 {lesson_num}. {original_subject}"
                if new_subject:
                    lesson_line += f" → {new_subject}"
                if new_teacher:
                    lesson_line += f" 👨‍🏫{new_teacher}"
                if new_room:
                    lesson_line += f" 🏫{new_room}"
            
            message.append(lesson_line)
        
        message.extend([
            "",
            "💡 Уведомления о заменах можно отключить в /settings"
        ])
        
        return "\n".join(message)

    def _get_day_name(self, date: datetime) -> str:
        """Получает название дня недели"""
        day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        return day_names[date.weekday()]

    # Вспомогательные методы для доступа к сервисам
    def _get_user_service(self):
        """Получает user_service (нужно реализовать доступ к context)"""
        # В реальной реализации нужно получить доступ к context
        return None

    # def _get_schools_data(self):
    #     """Получает schools_data (нужно реализовать доступ к context)"""
    #     # В реальной реализации нужно получить доступ к context
    #     return None

    # def _get_example_user_id(self):
    #     """Возвращает пример user_id (в реальности нужно получить из контекста)"""
    #     return 123456  # Заглушка

    # def _get_subject_name(self, subject_code: str) -> str:
    #     """Получает название предмета по коду"""
    #     # Нужно добавить логику получения названий предметов из данных школы
    #     subject_names = {
    #         '009': 'Математика',
    #         '032': 'Русский язык', 
    #         '010': 'Литература',
    #         '015': 'История',
    #         '014': 'География',
    #         '023': 'Биология'
    #         # Добавьте остальные коды предметов
    #     }
    #     return subject_names.get(subject_code, subject_code)

    # def _get_teacher_name(self, teacher_code: str) -> str:
    #     """Получает ФИО преподавателя по коду"""
    #     # Нужно добавить логику получения ФИО из данных школы
    #     teacher_names = {
    #         '033': 'Иванова И.И.',
    #         '002': 'Петров П.П.',
    #         '075': 'Сидорова С.С.',
    #         '087': 'Кузнецов К.К.',
    #         '058': 'Николаева Н.Н.'
    #         # Добавьте остальные коды преподавателей
    #     }
    #     return teacher_names.get(teacher_code, teacher_code)

    # def _get_room_name(self, room_code: str) -> str:
    #     """Получает номер кабинета по коду"""
    #     # Нужно добавить логику получения номеров кабинетов из данных школы
    #     room_names = {
    #         '022': '22',
    #         '052': '52', 
    #         '038': '38',
    #         '058': '58',
    #         '023': '23',
    #         '001': '1'
    #         # Добавьте остальные коды кабинетов
    #     }
    #     return room_names.get(room_code, room_code)

    # def _get_exchanges_hash(self, exchanges: List[Dict]) -> str:
    #     """Создает хэш для идентификации уникальных замен"""
    #     import hashlib
    #     import json
        
    #     # Создаем упрощенное представление замен для хэширования
    #     simplified = []
    #     for exchange in exchanges:
    #         simplified.append({
    #             'lesson': exchange.get('lesson_num'),
    #             'cancelled': exchange.get('is_cancelled', False),
    #             'subject': exchange.get('new_subject', ''),
    #             'teacher': exchange.get('new_teacher', ''),
    #             'room': exchange.get('new_room', '')
    #         })
        
    #     # Сортируем для consistent хэширования
    #     simplified.sort(key=lambda x: x['lesson'])
    #     exchanges_str = json.dumps(simplified, sort_keys=True)
        
    #     return hashlib.md5(exchanges_str.encode()).hexdigest()[:8]
    
    def _is_notification_sent(self, notification_key: str) -> bool:
        """Проверяет, было ли уведомление уже отправлено"""
        # Очищаем старые уведомления (старше 24 часов)
        self._cleanup_old_notifications()
        
        # Проверяем наличие ключа в любом месте словаря
        for key_set in self.sent_notifications.values():
            if notification_key in key_set:
                return True
        return False
    
    def _mark_notification_sent(self, notification_key: str):
        """Помечает уведомление как отправленное"""
        # Используем общий словарь для всех уведомлений
        if 'exchanges' not in self.sent_notifications:
            self.sent_notifications['exchanges'] = set()
        self.sent_notifications['exchanges'].add(notification_key)
    
    def _cleanup_old_notifications(self):
        """Очищает старые уведомления (простая реализация - можно улучшить)"""
        # В production лучше использовать Redis с TTL
        # Здесь просто ограничиваем размер кэша
        if 'exchanges' in self.sent_notifications and len(self.sent_notifications['exchanges']) > 200:
            # Оставляем только последние 100 уведомлений
            exchanges_list = list(self.sent_notifications['exchanges'])
            self.sent_notifications['exchanges'] = set(exchanges_list[-100:])
    
    # Существующие методы оставляем без изменений
    async def notify_school_down(self, context: ContextTypes.DEFAULT_TYPE, school_name: str, error: str = ""):
        """Уведомляет о недоступности школы"""
        message = (
            f"🚨 *Школа недоступна*\n\n"
            f"🏫 *{school_name}*\n"
            f"❌ Не удалось загрузить данные\n"
        )
        if error:
            message += f"\n📝 Ошибка: `{error}`"
        
        await self.notify_admins(context, message)
    
    async def notify_bot_started(self, context: ContextTypes.DEFAULT_TYPE):
        """Уведомляет о запуске бота"""
        from services.status_service import StatusService
        
        schools_data = context.bot_data.get('schools_data', {})
        status_service = StatusService(schools_data)
        
        loaded_schools = len(schools_data)
        total_schools = len([s for s in context.bot_data.get('schools_config', {}).values() if s.get('active', True)])
        
        message = (
            f"🤖 *Бот запущен*\n\n"
            f"✅ *Школы:* {loaded_schools}/{total_schools} загружены\n"
            f"🕒 *Время:* {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        )
        
        # Добавляем статус каждой школы
        for school_id, school_data in schools_data.items():
            school_name = get_display_name(school_id, school_data)
            status = status_service.get_school_status(school_id)
            message += f"• {status['status']} {school_name}\n"
        
        await self.notify_admins(context, message)