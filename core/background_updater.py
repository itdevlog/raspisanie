# core/background_updater.py
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict
from core.data_loader import DataLoader
from services.notification_service import NotificationService

class BackgroundUpdater:
    def __init__(self, application):
        self.application = application
        self.data_loader = DataLoader()
        self.notification_service = NotificationService()
        self.is_running = False
        self.update_interval = 1800  # 30 минут для более частой проверки замен
        self.logger = logging.getLogger(__name__)
        self._update_task = None

    def start_periodic_updates(self):
        """Запускает периодическое обновление внутри event loop бота"""
        if self.is_running:
            self.logger.warning("Фоновое обновление уже запущено")
            return

        self.is_running = True
        self._update_task = asyncio.create_task(self._update_loop())

        self.logger.info(f"✅ Фоновое обновление запущено (интервал: {self.update_interval} сек)")
        print(f"✅ Фоновое обновление запущено (интервал: {self.update_interval} сек)")

    def stop(self):
        """Останавливает фоновое обновление"""
        self.is_running = False
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()

    async def _update_loop(self):
        """Цикл обновления внутри event loop с оффлоадингом синхронного IO в to_thread"""
        self.logger.info("🔄 Цикл фонового обновления начал работу")

        while self.is_running:
            try:
                # Ждем до следующего обновления (asyncio.sleep не блокирует event loop)
                await asyncio.sleep(self.update_interval)

                if not self.is_running:
                    break

                self.logger.info("🔄 Запуск планового обновления данных...")
                print("🔄 Запуск планового обновления данных...")

                await self._perform_update()
                self.logger.info("✅ Плановое обновление завершено")

            except asyncio.CancelledError:
                self.logger.info("🔴 Цикл фонового обновления отменен")
                break
            except asyncio.TimeoutError:
                self.logger.error("❌ Таймаут при выполнении обновления")
                print("❌ Таймаут при выполнении обновления")
            except Exception as e:
                self.logger.error(f"❌ Ошибка в цикле обновления: {e}", exc_info=True)
                print(f"❌ Ошибка в цикле обновления: {e}")
                # Ждем перед повторной попыткой
                await asyncio.sleep(300)  # 5 минут при ошибке

        self.logger.info("🔴 Цикл фонового обновления остановлен")

    async def _perform_update(self):
        """Выполняет обновление данных и проверяет замены"""
        try:
            self.logger.info("🔄 Начало фонового обновления данных...")
            print("🔄 Фоновое обновление данных...")

            old_schools_data = self.application.bot_data.get('schools_data', {})
            # Оффлоадим синхронные HTTP-запросы в отдельный поток
            new_schools_data = await asyncio.to_thread(self.data_loader.load_all_schools_data)
            
            if new_schools_data:
                # Атомарно обновляем данные
                self.application.bot_data['schools_data'] = new_schools_data
                
                # Проверяем замены
                await self._check_exchange_updates(old_schools_data, new_schools_data)
                
                # Анализ изменений
                updated_schools = []
                for school_id in new_schools_data:
                    if school_id not in old_schools_data or old_schools_data[school_id] != new_schools_data[school_id]:
                        school_name = new_schools_data[school_id].get('SCHOOL_NAME', school_id)
                        updated_schools.append(school_name)
                
                if updated_schools:
                    self.logger.info(f"✅ Фоновое обновление завершено. Обновлено школ: {len(updated_schools)}")
                    print(f"✅ Фоновое обновление завершено. Обновлено школ: {len(updated_schools)}")

                    # Проверяем настройки уведомлений администратора перед отправкой
                    notification_settings = self._get_admin_notification_settings()
                    if notification_settings.get('update_notifications', False):
                        # Уведомляем админов об успешном обновлении
                        message = f"✅ *Автоматическое обновление*\n\nОбновлены школы:\n"
                        for school in updated_schools:
                            message += f"• {school}\n"

                        context = self._make_context()
                        await self.notification_service.notify_admins(context, message)
                else:
                    self.logger.info("✅ Фоновое обновление завершено. Изменений нет")
                    print("✅ Фоновое обновление завершено. Изменений нет")
                    
            else:
                error_msg = "❌ Фоновое обновление не удалось - не получены данные"
                self.logger.error(error_msg)
                print(error_msg)

                # Уведомляем админов об ошибке
                context = self._make_context()
                await self.notification_service.notify_admins(
                    context,
                    "❌ *Ошибка автоматического обновления*\n\nНе удалось загрузить данные школ"
                )

        except Exception as e:
            error_msg = f"❌ Ошибка фонового обновления: {e}"
            self.logger.error(error_msg, exc_info=True)
            print(error_msg)

            # Проверяем настройки уведомлений администратора перед отправкой уведомления об ошибке
            notification_settings = self._get_admin_notification_settings()
            if notification_settings.get('update_notifications', False):
                # Уведомляем админов об ошибке
                context = self._make_context()
                await self.notification_service.notify_admins(
                    context,
                    f"❌ *Ошибка автоматического обновления*\n\n`{str(e)}`"
                )
            
    def _get_admin_notification_settings(self):
        """Получает настройки уведомлений для администраторов"""
        try:
            # Получаем UserService из bot_data
            user_service = self.application.bot_data.get('user_service')
            if not user_service:
                # Если нет user_service, возвращаем настройки по умолчанию
                # (включенные уведомления для обратной совместимости)
                return {'update_notifications': True}
            
            # Получаем настройки уведомлений для каждого администратора
            config = self.application.bot_data.get('config')
            if not config or not hasattr(config, 'ADMIN_IDS'):
                return {'update_notifications': True}
            
            # Для упрощения возвращаем настройки первого администратора
            # В реальном приложении может потребоваться более сложная логика
            admin_ids = config.ADMIN_IDS
            if admin_ids:
                # Используем настройки уведомлений первого администратора
                from services.user_preferences import UserPreferencesService
                preferences_service = UserPreferencesService(user_service.db)
                settings = preferences_service.get_notification_settings(admin_ids[0])
                return settings
            
            return {'update_notifications': True}  # По умолчанию включены
            
        except Exception as e:
            self.logger.error(f"Ошибка получения настроек уведомлений администратора: {e}")
            return {'update_notifications': True}  # По умолчанию включены для безопасности
            
    def get_update_log_file(self):
        """Возвращает путь к файлу лога обновлений"""
        return 'updatelog.txt'
            
    def log_update_activity(self, message: str):
        """Записывает сообщение в лог обновлений"""
        try:
            with open(self.get_update_log_file(), 'a', encoding='utf-8') as f:
                timestamp = datetime.now(self.moscow_tz).strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            self.logger.error(f"Ошибка записи в лог обновлений: {e}")
            
    async def _check_exchange_updates(self, old_schools_data: Dict, new_schools_data: Dict):
        """Проверяет обновления замен и отправляет уведомления"""
        try:
            if 'exchange_detector' not in self.application.bot_data:
                from services.exchange_detector import ExchangeDetector
                self.application.bot_data['exchange_detector'] = ExchangeDetector()
            
            exchange_detector = self.application.bot_data['exchange_detector']
            notification_service = self.application.bot_data.get('notification_service')
            
            if not notification_service:
                self.logger.error("Notification service не найден в bot_data")
                # Используем self.notification_service как резервный вариант
                notification_service = self.notification_service
                if not notification_service:
                    self.logger.error("Notification service недоступен")
                    return
            
            today = datetime.now(exchange_detector.moscow_tz)
            
            self.logger.info(f"Проверка замен для {len(new_schools_data)} школ")
            
            # Проверяем замены для каждой школы
            for school_id, school_data in new_schools_data.items():
                try:
                    self.logger.info(f"Проверка замен для школы {school_id}")
                    new_exchanges = exchange_detector.detect_exchanges(school_id, school_data, today)
                    
                    if new_exchanges:
                        self.logger.info(f"Найдено {len(new_exchanges)} новых замен для школы {school_id}")
                        
                        # Группируем замены по классам
                        exchanges_by_class = {}
                        for exchange in new_exchanges:
                            class_name = exchange['class_name']
                            if class_name not in exchanges_by_class:
                                exchanges_by_class[class_name] = []
                            exchanges_by_class[class_name].append(exchange)
                        
                        self.logger.info(f"Найдено {len(exchanges_by_class)} классов с заменами в школе {school_id}")
                        
                        # Отправляем уведомления для каждого класса
                        for class_name, class_exchanges in exchanges_by_class.items():
                            self.logger.info(f"Обработка уведомлений для класса {class_name} в школе {school_id}, количество замен: {len(class_exchanges)}")
                            
                            # Создаем контекст для уведомлений
                            from telegram.ext import ContextTypes
                            context = ContextTypes.DEFAULT_TYPE
                            context.application = self.application
                            context.bot_data = self.application.bot_data
                            context.bot = self.application.bot  # Добавляем бота к контексту
                            
                            self.logger.info(f"Подготовлен контекст для уведомлений класса {class_name}")
                            
                            self.logger.info(f"Attempting to send exchange notifications for class {class_name} in school {school_id}, count: {len(class_exchanges)}")
                            result = await notification_service.notify_exchange_updates(
                                context, school_id, class_name, class_exchanges
                            )
                            self.logger.info(f"Notification result for class {class_name}: {result}")
                            
                            # Логируем активность обновления
                            self.log_update_activity(f"Отправлено {len(class_exchanges)} уведомлений для класса {class_name} в школе {school_id}, результат: {result}")
                            
                except Exception as e:
                    self.logger.error(f"Ошибка проверки замен для школы {school_id}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Ошибка в проверке обновлений замен: {e}")

    def _make_context(self):
        """Создает минимальный контекст для использования вне handler-ов"""
        from telegram.ext import ContextTypes
        context = ContextTypes.DEFAULT_TYPE
        context.application = self.application
        context.bot_data = self.application.bot_data
        context.bot = self.application.bot
        return context

    async def force_check_exchanges(self, context):
        """Принудительная проверка замен для всех школ"""
        try:
            if 'exchange_detector' not in self.application.bot_data:
                from services.exchange_detector import ExchangeDetector
                self.application.bot_data['exchange_detector'] = ExchangeDetector()

            exchange_detector = self.application.bot_data['exchange_detector']
            notification_service = self.application.bot_data.get('notification_service')

            if not notification_service:
                return

            today = datetime.now(exchange_detector.moscow_tz)
            schools_data = self.application.bot_data.get('schools_data', {})

            # Контекст создаем один раз
            exchange_context = self._make_context()

            for school_id, school_data in schools_data.items():
                try:
                    # Получаем текущие замены для всех классов школы
                    current_exchanges = exchange_detector._get_current_exchanges(school_data, today)

                    # Обрабатываем каждый класс отдельно
                    for class_name, class_exchanges in current_exchanges.items():
                        if class_exchanges:
                            # Форматируем замены для уведомления
                            formatted_exchanges = []
                            for lesson_num, exchange_data in class_exchanges.items():
                                formatted_exchange = exchange_detector._format_exchange_for_notification(
                                    class_name,
                                    {
                                        'lesson_num': lesson_num,
                                        'data': exchange_data['data'],
                                        'is_cancelled': exchange_data['is_cancelled']
                                    },
                                    school_data
                                )
                                formatted_exchanges.append(formatted_exchange)

                            # Отправляем уведомления для класса
                            await notification_service.notify_exchange_updates(
                                exchange_context, school_id, class_name, formatted_exchanges
                            )

                except Exception as e:
                    self.logger.error(f"Ошибка принудительной проверки замен для школы {school_id}: {e}")

        except Exception as e:
            self.logger.error(f"Ошибка в принудительной проверке замен: {e}")

    def stop(self):
        """Останавливает фоновое обновление"""
        self.is_running = False
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
        self.logger.info("Фоновое обновление остановлено")