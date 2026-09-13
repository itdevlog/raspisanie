# services/schedule_service.py
from datetime import datetime, timedelta

from .base_schedule_service import BaseScheduleService


class ScheduleService(BaseScheduleService):
    """Сервис для работы с расписанием классов"""

    def __init__(self, school_data: dict, cache_service=None, school_id: str = ""):
        super().__init__(school_data)
        self.cache_service = cache_service
        self.school_id = school_id

    def _cache_key(self, kind: str, class_name: str, date: datetime) -> str:
        """Ключ кэша с префиксом школы — иначе классы-тёзки (5и, 8б) в разных
        школах перетирали бы друг друга в общем CacheService."""
        return f"{self.school_id}:{kind}:{class_name}:{date.strftime('%Y%m%d')}"

    def get_class_schedule_today(self, class_name: str) -> str:
        """Получает расписание класса на сегодня с учетом замен"""
        # Используем кэширование если доступно
        if self.cache_service:
            cache_key = self._cache_key("today", class_name, datetime.now(self.moscow_tz))
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        today = datetime.now(self.moscow_tz)
        result = self._get_class_schedule_for_date(class_name, today, include_header=True)

        # Сохраняем в кэш если доступно
        if self.cache_service and result:
            cache_key = self._cache_key("today", class_name, datetime.now(self.moscow_tz))
            self.cache_service.set(cache_key, result)

        return result

    def get_class_schedule_tomorrow(self, class_name: str) -> str:
        """Получает расписание класса на завтра с учетом замен"""
        # Используем кэширование если доступно
        if self.cache_service:
            tomorrow = datetime.now(self.moscow_tz) + timedelta(days=1)
            cache_key = self._cache_key("tomorrow", class_name, tomorrow)
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        tomorrow = datetime.now(self.moscow_tz) + timedelta(days=1)
        result = self._get_class_schedule_for_date(class_name, tomorrow, include_header=True)

        # Сохраняем в кэш если доступно
        if self.cache_service and result:
            tomorrow = datetime.now(self.moscow_tz) + timedelta(days=1)
            cache_key = self._cache_key("tomorrow", class_name, tomorrow)
            self.cache_service.set(cache_key, result)

        return result

    def get_class_schedule_week(self, class_name: str, week_offset: int = 0) -> str:
        """Получает расписание класса на учебную неделю со смещением."""
        # Используем кэширование если доступно
        if self.cache_service:
            today = datetime.now(self.moscow_tz)
            current_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
            cache_key = self._cache_key(f"week{week_offset}", class_name, current_monday)
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached

        result = self._get_week_schedule('class', class_name, self._get_class_schedule_for_date, week_offset)

        # Сохраняем в кэш если доступно
        if self.cache_service and result:
            today = datetime.now(self.moscow_tz)
            current_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
            cache_key = self._cache_key(f"week{week_offset}", class_name, current_monday)
            self.cache_service.set(cache_key, result)

        return result

    def get_available_classes(self) -> list[str]:
        """Возвращает список доступных классов"""
        classes = self.school_data.get('CLASSES', {})
        return list(classes.values())

    def _get_class_schedule_for_date(self, class_name: str, date: datetime, include_header: bool = False) -> str:
        """Основная логика получения расписания класса"""
        # Находим ID класса по имени
        class_id = self._find_class_id(class_name)
        if not class_id:
            return f"❌ Класс '{class_name}' не найден"

        # Получаем период для даты
        period_id = self._get_period_for_date(date)
        if not period_id:
            return "❌ Не удалось определить учебный период"

        # Перенос праздников: каникулы — занятий нет; transfer —
        # расписание другого дня недели (как на сайте)
        info = self._get_holiday_info(date) or {}
        week_num = int(info.get('weeknum') or 0)
        effective = self._get_effective_day(date, period_id)
        if effective is None:
            day_name = self._get_day_name(date)
            date_str = date.strftime('%d.%m.%Y')
            return f"📅 *{class_name} - {day_name}, {date_str}*\n\n🏖️ Каникулы/праздник — занятий нет"
        eff_period_id, day_num = effective
        if not eff_period_id:
            return "❌ Не удалось определить учебный период"

        # Выходные (проверяем реальный день — перенесённый может быть рабочим,
        # например пн→сб)
        if date.isoweekday() > 5 and not self._get_holiday_info(date):
            day_name = self._get_day_name(date)
            date_str = date.strftime('%d.%m.%Y')
            return f"📅 *{class_name} - {day_name}, {date_str}*\n\n🏖️ Выходной день"

        # Получаем базовое расписание
        schedule_data = self._get_schedule_data(eff_period_id, class_id, day_num, week_num)

        # Применяем замены
        schedule_data = self.exchange_service.apply_exchanges_to_schedule(class_name, schedule_data, date)

        return self._format_schedule_response('class', class_name, date, schedule_data, include_header)

    def get_day(self, class_name: str, date: datetime) -> dict:
        """Структурный payload дня для API (см. спеку §2)."""
        from services.schedule_exceptions import EntityNotFoundError, PeriodNotFoundError

        class_id = self._find_class_id(class_name)
        if not class_id:
            raise EntityNotFoundError('class', class_name, f"❌ Класс '{class_name}' не найден")

        period_id = self._get_period_for_date(date)
        if not period_id:
            raise PeriodNotFoundError()

        payload = self._day_payload('class', self.school_data['CLASSES'][class_id], date)

        effective = self._get_effective_day(date, period_id)
        if effective is None:
            payload['vacation'] = True
            return payload
        eff_period_id, day_num = effective
        if not eff_period_id:
            raise PeriodNotFoundError()

        if date.isoweekday() > 5 and not self._get_holiday_info(date):
            payload['weekend'] = True
            return payload

        info = self._get_holiday_info(date) or {}
        week_num = int(info.get('weeknum') or 0)
        schedule_data = self._get_schedule_data(eff_period_id, class_id, day_num, week_num)
        schedule_data = self.exchange_service.apply_exchanges_to_schedule(
            self.school_data['CLASSES'][class_id], schedule_data, date)
        payload['lessons'] = self._lessons_payload(schedule_data)
        return payload

    def get_week(self, class_name: str, week_offset: int = 0) -> list[dict]:
        """5 структурных payload'ов Пн-Пт."""
        return [self.get_day(class_name, d) for d in self._week_dates(week_offset)]

    def _get_schedule_data(self, period_id: str, class_id: str, day_num: int,
                           week_num: int = 0) -> list[dict]:
        """Получает данные расписания класса - СПЕЦИФИЧНАЯ ЛОГИКА.

        week_num > 0 — номер учебной недели (ключи с префиксом недели:
        "{week}{day}{lesson}", как в Nikasoft при переносе на неделю N).
        """
        schedule = []
        class_schedule = self.school_data.get('CLASS_SCHEDULE', {}).get(period_id, {}).get(class_id, {})

        # ПРАВИЛЬНЫЙ ФОРМАТ: "401" = день4 урок1, "410" = день4 урок10;
        # при week_num>0 — "{week}{day}{lesson}" (неделя с префиксом)
        for lesson_num in range(1, self.school_data.get('LESSONSINDAY', 12) + 1):
            # Формируем ключ: "401" для дня4 урока1, "410" для дня4 урока10
            key = f"{day_num}{lesson_num:02d}"
            if week_num > 0:
                key = f"{week_num}{key}"

            if key in class_schedule:
                # Глубокая копия данных урока, чтобы замены не мутировали исходное расписание
                lesson_data = {
                    's': list(class_schedule[key].get('s', [])),
                    't': list(class_schedule[key].get('t', [])),
                    'r': list(class_schedule[key].get('r', []))
                }
                schedule.append({
                    'lesson_num': lesson_num,
                    'data': lesson_data,
                    'has_exchange': False,
                    'is_cancelled': False
                })

        return schedule
