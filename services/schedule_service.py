# services/schedule_service.py
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .base_schedule_service import BaseScheduleService

class ScheduleService(BaseScheduleService):
    """Сервис для работы с расписанием классов"""
    
    def __init__(self, school_data: Dict, cache_service=None):
        super().__init__(school_data)
        self.cache_service = cache_service
    
    def get_class_schedule_today(self, class_name: str) -> str:
        """Получает расписание класса на сегодня с учетом замен"""
        # Используем кэширование если доступно
        if self.cache_service:
            cache_key = f"today_{class_name}_{datetime.now(self.moscow_tz).strftime('%Y%m%d')}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached
        
        today = datetime.now(self.moscow_tz)
        result = self._get_class_schedule_for_date(class_name, today, include_header=True)
        
        # Сохраняем в кэш если доступно
        if self.cache_service and result:
            cache_key = f"today_{class_name}_{datetime.now(self.moscow_tz).strftime('%Y%m%d')}"
            self.cache_service.set(cache_key, result)
        
        return result
    
    def get_class_schedule_tomorrow(self, class_name: str) -> str:
        """Получает расписание класса на завтра с учетом замен"""
        # Используем кэширование если доступно
        if self.cache_service:
            tomorrow = datetime.now(self.moscow_tz) + timedelta(days=1)
            cache_key = f"tomorrow_{class_name}_{tomorrow.strftime('%Y%m%d')}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached
        
        tomorrow = datetime.now(self.moscow_tz) + timedelta(days=1)
        result = self._get_class_schedule_for_date(class_name, tomorrow, include_header=True)
        
        # Сохраняем в кэш если доступно
        if self.cache_service and result:
            tomorrow = datetime.now(self.moscow_tz) + timedelta(days=1)
            cache_key = f"tomorrow_{class_name}_{tomorrow.strftime('%Y%m%d')}"
            self.cache_service.set(cache_key, result)
        
        return result
    
    def get_class_schedule_week(self, class_name: str) -> str:
        """Получает расписание класса на текущую учебную неделю"""
        # Используем кэширование если доступно
        if self.cache_service:
            today = datetime.now(self.moscow_tz)
            current_monday = today - timedelta(days=today.weekday())
            cache_key = f"week_{class_name}_{current_monday.strftime('%Y%m%d')}"
            cached = self.cache_service.get(cache_key)
            if cached:
                return cached
        
        result = self._get_week_schedule('class', class_name, self._get_class_schedule_for_date)
        
        # Сохраняем в кэш если доступно
        if self.cache_service and result:
            today = datetime.now(self.moscow_tz)
            current_monday = today - timedelta(days=today.weekday())
            cache_key = f"week_{class_name}_{current_monday.strftime('%Y%m%d')}"
            self.cache_service.set(cache_key, result)
        
        return result
    
    def get_available_classes(self) -> List[str]:
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
        
        # Получаем день недели (1-понедельник, 7-воскресенье)
        day_num = date.isoweekday()
        if day_num > 5:  # 6-суббота, 7-воскресенье
            day_name = self._get_day_name(date)
            date_str = date.strftime('%d.%m.%Y')
            return f"📅 *{class_name} - {day_name}, {date_str}*\n\n🏖️ Выходной день"
        
        # Получаем базовое расписание
        schedule_data = self._get_schedule_data(period_id, class_id, day_num)
        
        # Применяем замены
        schedule_data = self.exchange_service.apply_exchanges_to_schedule(class_name, schedule_data, date)
        
        return self._format_schedule_response('class', class_name, date, schedule_data, include_header)
    
    def _get_schedule_data(self, period_id: str, class_id: str, day_num: int) -> List[Dict]:
        """Получает данные расписания класса - СПЕЦИФИЧНАЯ ЛОГИКА"""
        schedule = []
        class_schedule = self.school_data.get('CLASS_SCHEDULE', {}).get(period_id, {}).get(class_id, {})

        # ПРАВИЛЬНЫЙ ФОРМАТ: "401" = день4 урок1, "410" = день4 урок10
        for lesson_num in range(1, self.school_data.get('LESSONSINDAY', 12) + 1):
            # Формируем ключ: "401" для дня4 урока1, "410" для дня4 урока10
            key = f"{day_num}{lesson_num:02d}"

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

    def _find_class_id(self, class_name: str) -> Optional[str]:
        """Находит ID класса по точному совпадению имени (без учета регистра)"""
        if not class_name:
            return None
        classes = self.school_data.get('CLASSES', {})
        class_name_lower = class_name.strip().lower()
        for class_id, name in classes.items():
            if name.strip().lower() == class_name_lower:
                return class_id
        return None