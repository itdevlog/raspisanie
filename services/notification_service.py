# services/notification_service.py
import asyncio
import json
import logging
import os
import time
from datetime import datetime

from telegram.error import RetryAfter
from telegram.ext import ContextTypes

from config.config import Config, get_timezone
from config.schools import get_display_name
from services.text_utils import escape_markdown


class NotificationService:
    def __init__(self):
         self.config = Config()
         self.logger = logging.getLogger(__name__)
         # Кэш для отслеживания уже отправленных уведомлений.
         # Значение категории — dict {notification_key: timestamp_сек} (с TTL 24 ч).
         self.sent_notifications: dict[str, dict[str, float]] = {}
         self.moscow_tz = get_timezone()  # ДОБАВЬТЕ ЭТУ СТРОКУ
         self.logger.info("NotificationService инициализирован с пустым кэшом отправленных уведомлений")
         self.notifications_cache_file = self._get_cache_file()
         self.load_notifications_cache()
         # Кэш индекса (school_id, class_lower) -> [user_id], строится один раз за цикл
         self._user_class_index: dict[tuple, list[int]] = {}
         self._index_loaded_for_school: str | None = None
         # Настройки уведомлений {user_id: enabled} для текущей школы, строится вместе с индексом
         self._settings_for_school: dict[int, bool] = {}
         # Анти-флуд: минимальный интервал между сообщениями одному чату.
         self._min_send_interval = 1.0
         self._last_sent_at: dict[int, float] = {}

    def _build_user_class_index(self, user_service, school_id: str):
        """Один проход по всем пользователям: (school_id, класс) -> [user_id].

        Снимает O(N²) при массовой рассылке замен по многим классам: раньше
        _get_users_by_class сканировал всех пользователей на каждый класс.
        """
        try:
            users_collection = user_service.db.get_collection('users')
            idx: dict[tuple, list[int]] = {}
            self._settings_for_school = {}
            for user_data in users_collection.find():
                user_id = user_data.get('user_id')
                if not user_id:
                    continue
                self._settings_for_school[user_id] = (user_data.get('notification_settings') or {}).get(school_id, True)
                school_classes = user_data.get('school_classes') or {}
                class_name = school_classes.get(school_id)
                if class_name:
                    key = (school_id, class_name.lower())
                    idx.setdefault(key, []).append(user_id)
            self._user_class_index = idx
            self._index_loaded_for_school = school_id
            return idx
        except Exception as e:
            self.logger.error(f"Error building user class index: {e}", exc_info=True)
            return {}

    def get_users_by_class_indexed(self, user_service, school_id: str, class_name: str) -> list[int]:
        """Возвращает пользователей класса, строя индекс один раз для school_id."""
        if self._index_loaded_for_school != school_id:
            self._build_user_class_index(user_service, school_id)
        return self._user_class_index.get((school_id, class_name.lower()), [])

    def get_users_for_exchange(self, school_id: str, class_name: str) -> list[int]:
        """Получатели класса, у которых уведомления включены для школы."""
        candidates = self._user_class_index.get((school_id, class_name.lower()), [])
        settings = getattr(self, '_settings_for_school', {}) or {}
        return [uid for uid in candidates if settings.get(uid, True)]

    def reset_user_class_index(self):
        """Сбрасывает индекс (например, после обновления данных)."""
        self._user_class_index = {}
        self._index_loaded_for_school = None
        self._settings_for_school = {}

    def _get_users_by_class(self, user_service, school_id: str, class_name: str) -> list[int]:
        """Получает пользователей, следящих за классом (с индексом)."""
        return self.get_users_by_class_indexed(user_service, school_id, class_name)

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
                 with open(self.notifications_cache_file, encoding='utf-8') as f:
                     cache_data = json.load(f)
                     # Старый формат хранил списки ключей -> преобразуем в dict с timestamp,
                     # а новые записи (dict) оставляем как есть.
                     for key, value in cache_data.items():
                         if isinstance(value, list):
                             cache_data[key] = {item: 0.0 for item in value}
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

             # Множества (старый формат) — в списки; dict с timestamp оставляем как есть
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

    def _now(self) -> datetime:
        """Текущее время в таймзоне приложения (точка подмены в тестах)."""
        return datetime.now(self.moscow_tz)

    @staticmethod
    def _is_quiet_hours(settings: dict, now: datetime) -> bool:
        """Включены ли сейчас тихие часы по настройкам пользователя.

        Поддерживает интервал через полночь (start > end), например 22–7.
        Некорректные/отсутствующие настройки считаются «не тихими».
        """
        if not isinstance(settings, dict):
            return False
        quiet = settings.get('quiet_hours')
        if not isinstance(quiet, dict) or not quiet.get('enabled'):
            return False
        try:
            start = int(quiet['start'])
            end = int(quiet['end'])
        except (KeyError, TypeError, ValueError):
            return False
        hour = now.hour
        if start == end:
            # Пустое окно (start == end) считается выключенным, а не «тихим весь день»
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    async def _send_message(self, bot, chat_id: int, text: str, parse_mode: str = 'Markdown',
                            max_attempts: int = 3) -> bool:
        """Отправляет сообщение, пережидая Telegram RetryAfter (429).

        Анти-флуд: одному чату не чаще, чем раз в `_min_send_interval`.
        Вместо дропа выжидаем остаток интервала и всё равно отправляем —
        так не теряются легитимные разные сообщения (замены в нескольких
        школах, подписчики, админ-получатель). Итоговое ожидание ограничено
        сверху, чтобы массовая рассылка не залипала надолго.
        """
        last_sent_at = getattr(self, '_last_sent_at', None)
        if last_sent_at is None:
            self._last_sent_at = last_sent_at = {}
        interval = getattr(self, '_min_send_interval', 1.0)
        wait = interval - (time.monotonic() - last_sent_at.get(chat_id, 0.0))
        if wait > 0:
            await asyncio.sleep(min(wait, 1.0))
        for attempt in range(max_attempts):
            try:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
                self._last_sent_at[chat_id] = time.monotonic()
                return True
            except RetryAfter as e:
                wait = float(getattr(e, 'retry_after', 1) or 1)
                self.logger.warning(f"Telegram RetryAfter {wait}s (попытка {attempt + 1})")
                await asyncio.sleep(wait)
            except Exception as e:
                self.logger.error(f"Failed to send message to {chat_id}: {e}")
                return False
        return False

    async def notify_subscribers(self, context: ContextTypes.DEFAULT_TYPE, school_id: str,
                                 kind: str, name: str, text: str,
                                 parse_mode: str = 'Markdown') -> tuple[int, int]:
        """Отправляет текст всем подписчикам преподавателя/кабинета.

        Возвращает пару `(доставлено, пропущено_по_тихим_часам)`. Best-effort:
        ошибки подписок/отправки не выбрасываются наружу.
        """
        try:
            subscription_service = None
            if getattr(context, 'bot_data', None):
                subscription_service = context.bot_data.get('subscription_service')
            if not subscription_service:
                return 0, 0

            subscribers = subscription_service.get_subscribers(school_id, kind, name)
            if not subscribers:
                return 0, 0

            # Тихие часы: читаем настройки подписчиков через UserPreferencesService.
            # Если user_service недоступен — фильтр пропускаем (best-effort).
            from services.user_preferences import UserPreferencesService

            user_service = context.bot_data.get('user_service')
            db = getattr(user_service, 'db', None)
            preferences_service = UserPreferencesService(db) if db is not None else None
            now = self._now()

            sent = 0
            skipped_quiet = 0
            for user_id in subscribers:
                try:
                    if preferences_service is not None:
                        settings = preferences_service.get_notification_settings(user_id)
                        if self._is_quiet_hours(settings, now):
                            # Не шлём, но считаем: до-не-беспокоить, не transient-фейл
                            skipped_quiet += 1
                            self.logger.info(f"Тихие часы: пропуск уведомления подписчику {user_id}")
                            continue
                    if await self._send_message(context.bot, user_id, text, parse_mode=parse_mode):
                        sent += 1
                        await asyncio.sleep(0.05)
                except Exception as e:
                    self.logger.error(f"Failed to notify subscriber {user_id}: {e}")
            self.logger.info(
                f"Subscription notification sent to {sent}/{len(subscribers)} "
                f"({kind} {name}, quiet skipped: {skipped_quiet})"
            )
            return sent, skipped_quiet
        except Exception as e:
            self.logger.error(f"Error in notify_subscribers: {e}", exc_info=True)
            return 0, 0

    async def notify_admins(self, context: ContextTypes.DEFAULT_TYPE, message: str, parse_mode: str = 'Markdown'):
        """Отправляет уведомление всем администраторам"""
        try:
            for admin_id in self.config.ADMIN_IDS:
                try:
                    await self._send_message(context.bot, admin_id, message, parse_mode=parse_mode)
                except Exception as e:
                    self.logger.error(f"Failed to send notification to admin {admin_id}: {e}")
        except Exception as e:
            self.logger.error(f"Error in notify_admins: {e}")

    async def notify_exchange_updates(self, context: ContextTypes.DEFAULT_TYPE, school_id: str,
                                    class_name: str, exchanges: list[dict]) -> bool:
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

            # Строим индекс (настройки + классы) и берём только тех, у кого уведомления включены
            self._get_users_by_class(user_service, school_id, class_name)
            users = self.get_users_for_exchange(school_id, class_name)
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

            # Настройки тихих часов читаем из UserPreferencesService
            from services.user_preferences import UserPreferencesService

            preferences_service = UserPreferencesService(getattr(user_service, 'db', None))
            now = self._now()

            # Получатели уже отфильтрованы по настройкам уведомлений в get_users_for_exchange
            sent_count = 0
            skipped_quiet = 0
            for user_id in users:
                try:
                    user_settings = preferences_service.get_notification_settings(user_id)
                    if self._is_quiet_hours(user_settings, now):
                        # Не шлём, но считаем обработанным — dedup не даст задублировать позже
                        skipped_quiet += 1
                        self.logger.info(f"Тихие часы: пропуск уведомления для {user_id}")
                        continue
                    if await self._send_message(context.bot, user_id, notification_text, parse_mode='Markdown'):
                        sent_count += 1
                        self.logger.info(f"Exchange notification sent to user {user_id}")
                    # Небольшая пауза между отправками — защита от flood-лимитов Telegram
                    await asyncio.sleep(0.05)
                except Exception as e:
                    self.logger.error(f"Failed to send message to user {user_id}: {e}")

            # Помечаем отправленным, если что-то реально ушло ИЛИ все получатели
            # были на тихих часах — иначе после них пришлём то же самое повторно.
            if sent_count > 0 or skipped_quiet:
                self._mark_notification_sent(notification_key)
                self.save_notifications_cache()

            self.logger.info(
                f"Exchange notifications sent to {sent_count}/{len(users)} users "
                f"for class {class_name} (quiet skipped: {skipped_quiet})"
            )
            return sent_count > 0

        except Exception as e:
            self.logger.error(f"Error in notify_exchange_updates: {e}", exc_info=True)
            return False


    def _format_exchange_notification(self, class_name: str, exchanges: list[dict], date: datetime = None) -> str:
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
            f"🔄 *{escape_markdown(class_name.upper())} - {day_name}, {date_str}*",
            "",
            self._exchange_header(exchanges),
            ""
        ]

        # Добавляем информацию о заменах
        for exchange in exchanges:
            lesson_num = exchange.get('lesson_num', '?')
            original_subject = escape_markdown(exchange.get('original_subject', 'Неизвестно'))
            new_subject = escape_markdown(exchange.get('new_subject', ''))
            new_teacher = escape_markdown(exchange.get('new_teacher', ''))
            new_room = escape_markdown(exchange.get('new_room', ''))
            is_cancelled = exchange.get('is_cancelled', False)

            # Формируем строку урока
            if exchange.get('removed'):
                lesson_line = f"↩️ {lesson_num}. {original_subject} — *замена снята*"
                message.append(lesson_line)
                continue
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

    @staticmethod
    def _exchange_header(exchanges: list[dict]) -> str:
        """Заголовок: только снятия → «Замены сняты», иначе общий."""
        if exchanges and all(e.get('removed') for e in exchanges):
            return "📝 *Замены сняты:*"
        return "📝 *Новые замены в расписании:*"

    def _get_day_name(self, date: datetime) -> str:
        """Получает название дня недели"""
        day_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        return day_names[date.weekday()]

    def _is_notification_sent(self, notification_key: str) -> bool:
        """Проверяет, было ли уведомление уже отправлено"""
        # Очищаем старые уведомления (старше 24 часов)
        self._cleanup_old_notifications()

        # Проверяем наличие ключа в любом месте словаря (set — старый формат, dict — новый с timestamp)
        for entries in self.sent_notifications.values():
            if notification_key in entries:
                return True
        return False

    def _mark_notification_sent(self, notification_key: str):
        """Помечает уведомление как отправленное (с временем отправки)."""
        # Значение хранит timestamp в секундах — это позволяет очищать по возрасту.
        if 'exchanges' not in self.sent_notifications:
            self.sent_notifications['exchanges'] = {}
        self.sent_notifications['exchanges'][notification_key] = time.time()

    def _cleanup_old_notifications(self):
        """Удаляет уведомления старше 24 часов (порядок не важен)."""
        cutoff = time.time() - self._notifications_ttl_seconds()
        for category, entries in list(self.sent_notifications.items()):
            if isinstance(entries, dict):
                stale = [k for k, ts in entries.items() if ts < cutoff]
                for k in stale:
                    del entries[k]
            elif isinstance(entries, set):
                # старый формат (множество без времени) — считаем свежими, оставляем
                continue

    @staticmethod
    def _notifications_ttl_seconds() -> float:
        return 24 * 60 * 60

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
