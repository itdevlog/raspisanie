# services/room_service.py
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .base_schedule_service import BaseScheduleService

class RoomService(BaseScheduleService):
    """Сервис для работы с расписанием кабинетов"""
    
    def get_available_rooms(self) -> List[str]:
        """Возвращает список всех кабинетов школы"""
        rooms = self.school_data.get('ROOMS', {})
        return list(rooms.values())
    
    def search_rooms(self, query: str) -> List[str]:
        """Ищет кабинеты по номеру или названию"""
        if not query or len(query) < 1:
            return []
        
        all_rooms = self.get_available_rooms()
        query = query.lower().strip()
        
        found_rooms = []
        for room in all_rooms:
            if query in room.lower():
                found_rooms.append(room)
        
        return sorted(found_rooms)
    
    def find_room_id(self, room_name: str) -> Optional[str]:
        """Находит ID кабинета по названию"""
        rooms = self.school_data.get('ROOMS', {})
        for room_id, name in rooms.items():
            if room_name.lower() == name.lower():
                return room_id
        return None
    
    def get_room_schedule_today(self, room_name: str) -> str:
        """Получает расписание кабинета на сегодня"""
        today = datetime.now(self.moscow_tz)
        return self._get_room_schedule_for_date(room_name, today, include_header=True)

    def get_room_schedule_tomorrow(self, room_name: str) -> str:
        """Получает расписание кабинета на завтра"""
        tomorrow = datetime.now(self.moscow_tz) + timedelta(days=1)
        return self._get_room_schedule_for_date(room_name, tomorrow, include_header=True)
    
    def get_room_schedule_week(self, room_name: str) -> str:
        """Получает расписание кабинета на текущую учебную неделю"""
        return self._get_week_schedule('room', room_name, self._get_room_schedule_for_date)
    
    def _get_room_schedule_for_date(self, room_name: str, date: datetime, include_header: bool = False) -> str:
        """Основная логика получения расписания кабинета"""
        room_id = self.find_room_id(room_name)
        if not room_id:
            # Экранируем специальные символы Markdown в названии кабинета
            safe_room_name = room_name.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            return f"❌ Кабинет '{safe_room_name}' не найден"
        
        # Получаем период для даты
        period_id = self._get_period_for_date(date)
        if not period_id:
            return "❌ Не удалось определить учебный период"
        
        # Получаем день недели (1-понедельник, 7-воскресенье)
        day_num = date.isoweekday()
        if day_num > 5:  # Выходные
            day_name = self._get_day_name(date)
            date_str = date.strftime('%d.%m.%Y')
            # Экранируем специальные символы Markdown в названии кабинета
            safe_room_name = room_name.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            return f"📅 *Кабинет {safe_room_name} - {day_name}, {date_str}*\n\n🏖️ Выходной день"
        
        # Получаем расписание кабинета
        schedule_data = self._get_room_schedule_data(period_id, room_id, day_num, date)
        
        return self._format_schedule_response('room', room_name, date, schedule_data, include_header)
    
    def _get_room_schedule_data(self, period_id: str, room_id: str, day_num: int, date: datetime) -> List[Dict]:
        """Получает данные расписания кабинета - СПЕЦИФИЧНАЯ ЛОГИКА"""
        schedule = []
        class_schedule = self.school_data.get('CLASS_SCHEDULE', {}).get(period_id, {})
        
        # Ищем уроки, которые проходят в этом кабинете
        for class_id, class_lessons in class_schedule.items():
            for lesson_num in range(1, self.school_data.get('LESSONSINDAY', 12) + 1):
                key = f"{day_num}{lesson_num:02d}"  # "401", "410" и т.д.

                if key in class_lessons:
                    raw_lesson_data = class_lessons[key]

                    # Проверяем, есть ли этот кабинет в уроке
                    if 'r' in raw_lesson_data and room_id in raw_lesson_data['r']:
                        # Глубокая копия данных урока, чтобы замены не мутировали исходное расписание
                        lesson_data = {
                            's': list(raw_lesson_data.get('s', [])),
                            't': list(raw_lesson_data.get('t', [])),
                            'r': list(raw_lesson_data.get('r', []))
                        }
                        raw_class_name = self.school_data.get('CLASSES', {}).get(class_id, 'Неизвестно')
                        class_name = raw_class_name.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')

                        # Применяем замены для этого класса
                        class_lesson = [{
                            'lesson_num': lesson_num,
                            'data': lesson_data,
                            'has_exchange': False,
                            'is_cancelled': False
                        }]

                        class_lesson = self.exchange_service.apply_exchanges_to_schedule(class_name, class_lesson, date)
                        updated_lesson = class_lesson[0] if class_lesson else None

                        if updated_lesson and not updated_lesson.get('is_cancelled'):
                            schedule.append({
                                'lesson_num': lesson_num,
                                'class_name': class_name,
                                'data': updated_lesson['data'],
                                'has_exchange': updated_lesson.get('has_exchange', False),
                                'is_cancelled': updated_lesson.get('is_cancelled', False)
                            })
        
        # Сортируем по номеру урока
        schedule.sort(key=lambda x: x['lesson_num'])
        return schedule