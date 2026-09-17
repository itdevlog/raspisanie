# core/background_updater.py
import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

from config.config import Config, get_timezone
from config.schools import get_display_name
from core.data_loader import DataLoader
from services.digest_service import DigestService
from services.notification_service import NotificationService
from services.reminder_service import ReminderService


class BackgroundUpdater:
    def __init__(self, application):
        self.config = Config()
        self.application = application
        self.data_loader = DataLoader()
        # Резервный/инъектируемый экземпляр. В продакшене единственный сервис
        # живёт в bot_data, сюда не кладём — иначе два объекта над одним
        # notifications_cache.json дадут last-write-wins и дубли.
        self.notification_service: NotificationService | None = None
        self.is_running = False
        self.update_interval = self.config.UPDATE_INTERVAL
        self.logger = logging.getLogger(__name__)
        self.moscow_tz = get_timezone()
        self._update_task = None
        self._update_lock = asyncio.Lock()
        # Напоминания об уроках: отдельный цикл + дедуп (ключ -> timestamp).
        self.reminder_service = ReminderService()
        self._reminder_task = None
        self.sent_reminders: dict[str, float] = {}
        self.sent_reminders_file = self._get_sent_reminders_file()
        self._load_sent_reminders()
        # Утренний дайджест: тот же минутный цикл, отдельный кэш дедупа.
        self.digest_service = DigestService()
        self.sent_digests: dict[str, float] = {}
        self.sent_digests_file = self._get_sent_digests_file()
        self._load_sent_digests()
        # Дедуп уведомлений подписчиков преподавателей/кабинетов (ключ -> timestamp).
        self.sent_entity_notifications: dict[str, float] = {}

    def start_periodic_updates(self):
        """Запускает периодическое обновление внутри event loop бота"""
        if self.is_running:
            self.logger.warning("Фоновое обновление уже запущено")
            return

        self.is_running = True
        self._update_task = asyncio.create_task(self._update_loop())
        self._reminder_task = asyncio.create_task(self._reminder_loop())

        self.logger.info(f"✅ Фоновое обновление запущено (интервал: {self.update_interval} сек)")

    def stop(self):
        """Останавливает фоновое обновление"""
        self.is_running = False
        if self._update_task and not self._update_task.done():
            self._update_task.cancel()
        if self._reminder_task and not self._reminder_task.done():
            self._reminder_task.cancel()

    def _now(self):
        """Текущее время в таймзоне приложения (точка подмены в тестах)."""
        return datetime.now(self.moscow_tz)

    def _notification_service(self):
        """Единственный NotificationService: из bot_data, иначе инъектированный.

        В продакшене сервис создаётся один раз в `bot.py` и кладётся в
        bot_data; атрибут `notification_service` — только для тестов.
        """
        if self.application and hasattr(self.application, 'bot_data'):
            service = self.application.bot_data.get('notification_service')
            if service:
                return service
        return self.notification_service

    async def _reminder_loop(self):
        """Минутный цикл: напоминания об уроках и утренний дайджест."""
        self.logger.info("⏰ Цикл напоминаний об уроках начал работу")
        while self.is_running:
            try:
                await asyncio.sleep(60)
                if not self.is_running:
                    break
                await self._send_reminders()
                await self._send_digests()
            except asyncio.CancelledError:
                self.logger.info("🔴 Цикл напоминаний отменён")
                break
            except Exception as e:
                self.logger.error(f"❌ Ошибка в цикле напоминаний: {e}", exc_info=True)
        self.logger.info("🔴 Цикл напоминаний остановлен")

    async def _send_reminders(self):
        """Считает и отправляет напоминания, дедуп за 24 часа."""
        try:
            bot_data = self.application.bot_data
            user_service = bot_data.get('user_service')
            schools_data = bot_data.get('schools_data', {})
            if not user_service or not schools_data:
                return

            from services.user_preferences import UserPreferencesService

            users = user_service.get_users_with_classes()
            user_classes = self.reminder_service.to_user_classes(users)

            preferences_service = UserPreferencesService(user_service.db)
            enabled = {
                user['user_id']
                for user in users
                if user.get('user_id')
                and preferences_service.get_notification_settings(user['user_id']).get('lesson_reminders', False)
            }
            user_classes = {
                user_id: target
                for user_id, target in user_classes.items()
                if user_id in enabled
            }
            if not user_classes:
                return

            now = self._now()
            due = self.reminder_service.get_due_reminders_detailed(
                schools_data, user_classes, now
            )

            self._cleanup_sent_reminders()
            notification_service = self._notification_service()
            bot = bot_data.get('bot') or self.application.bot
            for user_id, text, key in due:
                if key in self.sent_reminders:
                    continue
                # Тихие часы: не шлём, но помечаем ключ, чтобы не дублировать позже
                settings = preferences_service.get_notification_settings(user_id)
                if NotificationService._is_quiet_hours(settings, now):
                    self.sent_reminders[key] = time.time()
                    self._save_sent_reminders()
                    self.logger.info(f"Тихие часы: пропуск напоминания для {user_id}")
                    continue
                try:
                    delivered = await notification_service._send_message(
                        bot, user_id, text, parse_mode=None
                    )
                    if delivered:
                        self.sent_reminders[key] = time.time()
                        self._save_sent_reminders()
                    else:
                        # Реальная ошибка отправки — не помечаем, чтобы повторить позже
                        self.logger.warning(f"Напоминание {user_id} не доставлено, будет повтор")
                except Exception as e:
                    self.logger.error(f"Ошибка отправки напоминания {user_id}: {e}")
                await asyncio.sleep(0.05)
        except Exception as e:
            self.logger.error(f"Ошибка в _send_reminders: {e}", exc_info=True)

    def _cleanup_sent_reminders(self):
        """Удаляет ключи напоминаний старше 24 часов."""
        cutoff = time.time() - 24 * 60 * 60
        stale = [k for k, ts in self.sent_reminders.items() if ts < cutoff]
        for key in stale:
            del self.sent_reminders[key]
        if stale:
            self._save_sent_reminders()

    @staticmethod
    def _get_sent_reminders_file() -> str:
        """Путь к кэшу отправленных напоминаний в общей data-директории."""
        db_path = Config().DB_PATH
        data_dir = os.path.dirname(db_path) or './data'
        return os.path.join(data_dir, 'sent_reminders.json')

    def _load_sent_reminders(self):
        """Загружает кэш отправленных напоминаний, отбрасывая записи старше 24 ч.

        Дедуп напоминаний переживает рестарт внутри окна напоминания — иначе
        бот, перезапущенный за пару минут до урока, прислал бы напоминание снова.
        """
        try:
            if os.path.exists(self.sent_reminders_file):
                with open(self.sent_reminders_file, encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.sent_reminders = {
                        str(k): float(v) for k, v in data.items()
                    }
            self._cleanup_sent_reminders()
        except Exception as e:
            self.logger.error(f"Ошибка загрузки кэша напоминаний: {e}")
            self.sent_reminders = {}

    def _save_sent_reminders(self):
        """Атомарно сохраняет кэш отправленных напоминаний."""
        try:
            path = getattr(self, 'sent_reminders_file', None)
            if not path:
                return
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            tmp = f"{path}.tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.sent_reminders, f, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения кэша напоминаний: {e}")

    async def _send_digests(self):
        """Считает и отправляет утренние дайджесты, дедуп за 48 часов."""
        try:
            bot_data = self.application.bot_data
            user_service = bot_data.get('user_service')
            schools_data = bot_data.get('schools_data', {})
            if not user_service or not schools_data:
                return

            from services.user_preferences import UserPreferencesService

            users = user_service.get_users_with_classes()
            user_classes = self.reminder_service.to_user_classes(users)

            preferences_service = UserPreferencesService(user_service.db)
            enabled = {
                user['user_id']
                for user in users
                if user.get('user_id')
                and preferences_service.get_notification_settings(user['user_id']).get('daily_digest', False)
            }
            user_classes = {
                user_id: target
                for user_id, target in user_classes.items()
                if user_id in enabled
            }
            if not user_classes:
                return

            now = self._now()
            due = self.digest_service.get_due_digests(schools_data, user_classes, now)

            self._cleanup_sent_digests()
            notification_service = self._notification_service()
            bot = bot_data.get('bot') or self.application.bot
            for user_id, text, key in due:
                if key in self.sent_digests:
                    continue
                # Тихие часы: не шлём, но помечаем ключ, чтобы не дублировать позже
                settings = preferences_service.get_notification_settings(user_id)
                if NotificationService._is_quiet_hours(settings, now):
                    self.sent_digests[key] = time.time()
                    self._save_sent_digests()
                    self.logger.info(f"Тихие часы: пропуск дайджеста для {user_id}")
                    continue
                try:
                    delivered = await notification_service._send_message(
                        bot, user_id, text, parse_mode='Markdown'
                    )
                    if delivered:
                        self.sent_digests[key] = time.time()
                        self._save_sent_digests()
                    else:
                        self.logger.warning(f"Дайджест {user_id} не доставлен, будет повтор")
                except Exception as e:
                    self.logger.error(f"Ошибка отправки дайджеста {user_id}: {e}")
                await asyncio.sleep(0.05)
        except Exception as e:
            self.logger.error(f"Ошибка в _send_digests: {e}", exc_info=True)

    def _cleanup_sent_digests(self):
        """Удаляет ключи дайджестов старше 48 часов."""
        cutoff = time.time() - 48 * 60 * 60
        stale = [k for k, ts in self.sent_digests.items() if ts < cutoff]
        for key in stale:
            del self.sent_digests[key]
        if stale:
            self._save_sent_digests()

    @staticmethod
    def _get_sent_digests_file() -> str:
        """Путь к кэшу отправленных дайджестов в общей data-директории."""
        db_path = Config().DB_PATH
        data_dir = os.path.dirname(db_path) or './data'
        return os.path.join(data_dir, 'sent_digests.json')

    def _load_sent_digests(self):
        """Загружает кэш дайджестов, отбрасывая записи старше 48 ч."""
        try:
            if os.path.exists(self.sent_digests_file):
                with open(self.sent_digests_file, encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.sent_digests = {
                        str(k): float(v) for k, v in data.items()
                    }
            self._cleanup_sent_digests()
        except Exception as e:
            self.logger.error(f"Ошибка загрузки кэша дайджестов: {e}")
            self.sent_digests = {}

    def _save_sent_digests(self):
        """Атомарно сохраняет кэш отправленных дайджестов."""
        try:
            path = getattr(self, 'sent_digests_file', None)
            if not path:
                return
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            tmp = f"{path}.tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.sent_digests, f, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения кэша дайджестов: {e}")

    def _cleanup_sent_entity_notifications(self):
        """Удаляет ключи уведомлений подписчиков старше 24 часов."""
        cutoff = time.time() - 24 * 60 * 60
        for key in [k for k, ts in self.sent_entity_notifications.items() if ts < cutoff]:
            del self.sent_entity_notifications[key]

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

                await self._perform_update()
                self.logger.info("✅ Плановое обновление завершено")

            except asyncio.CancelledError:
                self.logger.info("🔴 Цикл фонового обновления отменен")
                break
            except TimeoutError:
                self.logger.error("❌ Таймаут при выполнении обновления")
            except Exception as e:
                self.logger.error(f"❌ Ошибка в цикле обновления: {e}", exc_info=True)
                # Ждем перед повторной попыткой
                await asyncio.sleep(300)  # 5 минут при ошибке

        self.logger.info("🔴 Цикл фонового обновления остановлен")

    @staticmethod
    def _merge_schools_data(old: dict, new: dict) -> dict:
        """Свежие данные поверх last-known-good: не потерять школу при сбое загрузки."""
        merged = dict(old or {})
        merged.update(new or {})
        return merged

    def _on_data_replaced(self):
        """Единая реакция на замену schools_data: сброс кэша расписания и индекса уведомлений."""
        cache_service = self.application.bot_data.get('cache_service')
        if cache_service:
            cache_service.clear()
            self.logger.info("Кэш расписания очищен после обновления данных")
        notification_service = self.application.bot_data.get('notification_service')
        if notification_service and hasattr(notification_service, 'reset_user_class_index'):
            notification_service.reset_user_class_index()

    async def _perform_update(self) -> bool:
        """Обёртка с блокировкой: не допускает одновременный запуск обновлений.

        Возвращает True, если обновление реально выполнялось, и False, если
        был пропуск из-за уже идущего обновления.
        """
        if self._update_lock.locked():
            self.logger.warning("Обновление уже выполняется — пропуск повторного запуска")
            return False
        async with self._update_lock:
            await self._perform_update_locked()
        return True

    async def _perform_update_locked(self):
        """Выполняет обновление данных и проверяет замены"""
        try:
            self.logger.info("🔄 Начало фонового обновления данных...")

            old_schools_data = self.application.bot_data.get('schools_data', {})
            # Оффлоадим синхронные HTTP-запросы в отдельный поток
            new_schools_data = await asyncio.to_thread(self.data_loader.load_all_schools_data)

            if new_schools_data:
                # Мержим свежие данные поверх last-known-good, чтобы школы,
                # чья загрузка не удалась, не исчезали до следующего цикла
                merged = self._merge_schools_data(old_schools_data, new_schools_data)
                self.application.bot_data['schools_data'] = merged

                # Единая инвалидация: кэш расписания + индекс уведомлений
                self._on_data_replaced()

                # Проверяем замены
                await self._check_exchange_updates(old_schools_data, merged)

                # Анализ изменений
                updated_schools = []
                for school_id in new_schools_data:
                    if school_id not in old_schools_data or old_schools_data[school_id] != new_schools_data[school_id]:
                        school_name = get_display_name(school_id, new_schools_data[school_id])
                        updated_schools.append(school_name)

                if updated_schools:
                    self.logger.info(f"✅ Фоновое обновление завершено. Обновлено школ: {len(updated_schools)}")

                    # Проверяем настройки уведомлений администратора перед отправкой
                    notification_settings = self._get_admin_notification_settings()
                    if notification_settings.get('update_notifications', False):
                        # Уведомляем админов об успешном обновлении
                        message = "✅ *Автоматическое обновление*\n\nОбновлены школы:\n"
                        for school in updated_schools:
                            message += f"• {school}\n"

                        context = self._make_context()
                        notification_service = self._notification_service()
                        if notification_service:
                            await notification_service.notify_admins(context, message)
                else:
                    self.logger.info("✅ Фоновое обновление завершено. Изменений нет")

            else:
                error_msg = "❌ Фоновое обновление не удалось - не получены данные"
                self.logger.error(error_msg)

                # Уведомляем админов об ошибке
                context = self._make_context()
                notification_service = self._notification_service()
                if notification_service:
                    await notification_service.notify_admins(
                        context,
                        "❌ *Ошибка автоматического обновления*\n\nНе удалось загрузить данные школ"
                    )

        except Exception as e:
            error_msg = f"❌ Ошибка фонового обновления: {e}"
            self.logger.error(error_msg, exc_info=True)

            # Проверяем настройки уведомлений администратора перед отправкой уведомления об ошибке
            notification_settings = self._get_admin_notification_settings()
            if notification_settings.get('update_notifications', False):
                # Уведомляем админов об ошибке
                context = self._make_context()
                notification_service = self._notification_service()
                if notification_service:
                    await notification_service.notify_admins(
                        context,
                        f"❌ *Ошибка автоматического обновления*\n\n`{str(e)}`"
                    )

    def _get_admin_notification_settings(self):
        """Получает настройки уведомлений для администраторов.

        Читает сохранённые предпочтения через UserPreferencesService — тот же
        источник, что и меню настроек (settings.py). Уведомление отправляется,
        если хотя бы один администратор включил `update_notifications`. Если нет
        сохранённых настроек ни у кого, возвращает False, чтобы совпадать с тем,
        что показывает UI («Уведомления об обновлениях: Выкл»).
        Раньше здесь жёстко возвращалось True -> тосты-предупреждения расходились
        с отображением.
        """
        try:
            # Получаем UserService из bot_data
            user_service = self.application.bot_data.get('user_service')
            if not user_service:
                # Если нет user_service, возвращаем настройки по умолчанию
                return {'update_notifications': False}

            # Получаем настройки уведомлений для каждого администратора
            config = self.application.bot_data.get('config')
            if not config or not hasattr(config, 'ADMIN_IDS'):
                return {'update_notifications': False}

            # Уведомления об обновлениях — общий флаг для админов: шлём, если
            # хотя бы один администратор включил их в меню настроек.
            admin_ids = config.ADMIN_IDS
            if admin_ids:
                from services.user_preferences import UserPreferencesService
                preferences_service = UserPreferencesService(user_service.db)
                any_enabled = any(
                    preferences_service.get_notification_settings(admin_id).get('update_notifications', False)
                    for admin_id in admin_ids
                )
                return {'update_notifications': any_enabled}

            return {'update_notifications': False}  # По умолчанию выключены

        except Exception as e:
            self.logger.error(f"Ошибка получения настроек уведомлений администратора: {e}")
            return {'update_notifications': False}  # По умолчанию выключены

    def get_update_log_file(self):
        """Возвращает путь к файлу лога обновлений"""
        return self.config.get_updatelog_path()

    def log_update_activity(self, message: str):
        """Записывает сообщение в лог обновлений"""
        try:
            with open(self.get_update_log_file(), 'a', encoding='utf-8') as f:
                timestamp = datetime.now(self.moscow_tz).strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            self.logger.error(f"Ошибка записи в лог обновлений: {e}")

    async def _check_exchange_updates(self, old_schools_data: dict, new_schools_data: dict):
        """Проверяет обновления замен и отправляет уведомления"""
        try:
            if 'exchange_detector' not in self.application.bot_data:
                from services.exchange_detector import ExchangeDetector
                self.application.bot_data['exchange_detector'] = ExchangeDetector()

            exchange_detector = self.application.bot_data['exchange_detector']
            notification_service = self._notification_service()

            if not notification_service:
                self.logger.error("Notification service недоступен")
                return

            # Проверяем замены на сегодня И завтра — раньше смотрели только «сегодня»,
            # из-за чего замены на завтра обнаруживались только после полуночи (или вовсе
            # терялись, если данные выгружены заранее), а заголовок даты уводился неверно.
            dates = [
                datetime.now(exchange_detector.moscow_tz),
                datetime.now(exchange_detector.moscow_tz) + timedelta(days=1),
            ]

            for today in dates:
                date_str = today.strftime('%d.%m.%Y')
                self.logger.info(f"Проверка замен на дату {date_str} для {len(new_schools_data)} школ")

                # Проверяем замены для каждой школы
                for school_id, school_data in new_schools_data.items():
                    try:
                        self.logger.info(f"Проверка замен для школы {school_id} на {date_str}")
                        new_exchanges, current_exchanges = await asyncio.to_thread(
                            exchange_detector.detect_exchanges_deferred, school_id, school_data, today
                        )

                        if new_exchanges:
                            self.logger.info(f"Найдено {len(new_exchanges)} новых замен для школы {school_id} на {date_str}")

                            # Группируем замены по классам
                            exchanges_by_class: dict[str, list[dict]] = {}
                            for exchange in new_exchanges:
                                class_name = exchange['class_name']
                                if class_name not in exchanges_by_class:
                                    exchanges_by_class[class_name] = []
                                exchanges_by_class[class_name].append(exchange)

                            self.logger.info(f"Найдено {len(exchanges_by_class)} классов с заменами в школе {school_id}")

                            # Создаем один контекст для всех уведомлений
                            context = self._make_context()

                            # Отправляем уведомления для каждого класса
                            all_handled = True
                            for class_name, class_exchanges in exchanges_by_class.items():
                                self.logger.info(f"Обработка уведомлений для класса {class_name} в школе {school_id}, количество замен: {len(class_exchanges)}")

                                result = await notification_service.notify_exchange_updates(
                                    context, school_id, class_name, class_exchanges
                                )
                                self.logger.info(f"Notification result for class {class_name}: {result}")
                                if not result:
                                    all_handled = False

                                # Best-effort: уведомляем подписчиков преподавателей/кабинетов
                                await self._notify_entity_subscribers(
                                    context, notification_service, school_id, class_name,
                                    class_exchanges, today
                                )

                                # Логируем активность обновления
                                await asyncio.to_thread(
                                    self.log_update_activity,
                                    f"Отправлено {len(class_exchanges)} уведомлений для класса {class_name} в школе {school_id} на {date_str}, результат: {result}",
                                )

                            # Baseline коммитим только после подтверждённой доставки:
                            # иначе следующий цикл повторит находку, а per-user dedup
                            # не даст задвоить уже доставленное.
                            if all_handled:
                                await asyncio.to_thread(
                                    exchange_detector.commit_exchanges,
                                    school_id, today, current_exchanges,
                                )
                            else:
                                self.logger.info(
                                    f"Не все уведомления доставлены для школы {school_id} на {date_str} — "
                                    f"baseline не зафиксирован, будет повтор"
                                )
                        else:
                            # Новых замен нет — просто фиксируем текущий baseline даты
                            await asyncio.to_thread(
                                exchange_detector.commit_exchanges,
                                school_id, today, current_exchanges,
                            )

                    except Exception as e:
                        self.logger.error(f"Ошибка проверки замен для школы {school_id}: {e}")

            # Один общий flush кэша замен за цикл (а не запись на каждую школу/дату)
            try:
                await asyncio.to_thread(exchange_detector.save_cache)
            except Exception as e:
                self.logger.error(f"Ошибка сохранения кэша замен: {e}")

        except Exception as e:
            self.logger.error(f"Ошибка в проверке обновлений замен: {e}")

    @staticmethod
    def _entity_exchanges_signature(class_exchanges: list, kind: str, name: str,
                                    class_name: str = '') -> str:
        """Стабильная подпись замен, ссылающихся на конкретного преподавателя/кабинет.

        `class_name` входит в подпись, иначе два класса одной школы с идентичными
        полями замены дают коллизию и одна из легитимных нотификаций глушится.
        """
        field = 'new_teacher' if kind == 'teacher' else 'new_room'
        parts = []
        for ex in class_exchanges:
            if (ex.get(field) or '').strip() != name:
                continue
            parts.append(
                f"{ex.get('lesson_num', '')}_{ex.get('new_subject', '')}_"
                f"{ex.get('new_teacher', '')}_{ex.get('new_room', '')}_{ex.get('is_cancelled', '')}"
            )
        prefix = f"{class_name}|" if class_name else ""
        return prefix + '|'.join(parts)

    async def _notify_entity_subscribers(self, context, notification_service, school_id: str,
                                         class_name: str, class_exchanges: list, date) -> None:
        """Best-effort уведомление подписчиков новых преподавателей/кабинетов.

        Для каждой замены с непустым `new_teacher`/`new_room` шлём подписчикам
        текст уведомления о замене. Ошибки не влияют на детекцию замен.

        Дедуп за 24 часа: и периодический цикл, и ручной `/check_exchanges`
        передают полный текущий набор замен, поэтому без ключа подписчики
        получали бы спам на каждом запуске. Ключ включает подпись замен,
        ссылающихся на сущность, — новая замена снова уведомит.
        """
        try:
            if not notification_service or not hasattr(notification_service, 'notify_subscribers'):
                return

            text = notification_service._format_exchange_notification(class_name, class_exchanges, date)
            if not text:
                return

            self._cleanup_sent_entity_notifications()
            date_str = date.strftime('%Y%m%d') if hasattr(date, 'strftime') else 'unknown'

            seen: set[tuple[str, str]] = set()
            for exchange in class_exchanges:
                for kind, field in (('teacher', 'new_teacher'), ('room', 'new_room')):
                    name = (exchange.get(field) or '').strip()
                    if not name or (kind, name) in seen:
                        continue
                    seen.add((kind, name))

                    signature = self._entity_exchanges_signature(
                        class_exchanges, kind, name, class_name)
                    digest = hashlib.md5(signature.encode()).hexdigest()[:8]
                    key = f"{school_id}:{class_name}:{kind}:{name}:{date_str}:{digest}"
                    if key in self.sent_entity_notifications:
                        continue
                    try:
                        delivered, skipped_quiet = await notification_service.notify_subscribers(
                            context, school_id, kind, name, text
                        )
                        # Помечаем только если что-то доставлено или все получатели
                        # были на тихих часах. Transient-фейл отправки НЕ глушит
                        # сущность на 24 часа.
                        if delivered > 0 or skipped_quiet > 0:
                            self.sent_entity_notifications[key] = time.time()
                    except Exception as e:
                        self.logger.error(f"Ошибка уведомления подписчиков {kind} {name}: {e}")
        except Exception as e:
            self.logger.error(f"Ошибка в _notify_entity_subscribers: {e}", exc_info=True)

    def _make_context(self):
        """Создает минимальный контекст для использования вне handler-ов"""
        context = SimpleNamespace(
            application=self.application,
            bot_data=self.application.bot_data,
            bot=self.application.bot
        )
        return context

    async def force_check_exchanges(self, context):
        """Принудительная проверка замен для всех школ"""
        try:
            if 'exchange_detector' not in self.application.bot_data:
                from services.exchange_detector import ExchangeDetector
                self.application.bot_data['exchange_detector'] = ExchangeDetector()

            exchange_detector = self.application.bot_data['exchange_detector']
            notification_service = self._notification_service()

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
                                    school_data,
                                    today
                                )
                                formatted_exchanges.append(formatted_exchange)

                            # Отправляем уведомления для класса
                            await notification_service.notify_exchange_updates(
                                exchange_context, school_id, class_name, formatted_exchanges
                            )

                            # Best-effort: уведомляем подписчиков преподавателей/кабинетов
                            try:
                                await self._notify_entity_subscribers(
                                    exchange_context, notification_service, school_id,
                                    class_name, formatted_exchanges, today
                                )
                            except Exception as e:
                                self.logger.error(
                                    f"Ошибка уведомления подписчиков класса {class_name} "
                                    f"в школе {school_id}: {e}"
                                )

                except Exception as e:
                    self.logger.error(f"Ошибка принудительной проверки замен для школы {school_id}: {e}")

        except Exception as e:
            self.logger.error(f"Ошибка в принудительной проверке замен: {e}")
