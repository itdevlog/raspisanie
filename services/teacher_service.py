# services/teacher_service.py
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from .base_schedule_service import BaseScheduleService

class TeacherService(BaseScheduleService):
    """Сервис для работы с расписанием преподавателей"""
    
    def get_available_teachers(self) -> List[str]:
        """Возвращает список всех преподавателей школы"""
        teachers = self.school_data.get('TEACHERS', {})
        return list(teachers.values())
    
    def search_teachers(self, query: str) -> List[str]:
        """Ищет преподавателей по фамилии или имени"""
        if not query or len(query) < 2:
            return []
        
        all_teachers = self.get_available_teachers()
        query = query.lower().strip()
        
        found_teachers = []
        for teacher in all_teachers:
            if query in teacher.lower():
                found_teachers.append(teacher)
        
        return sorted(found_teachers)
    
    def find_teacher_id(self, teacher_name: str) -> Optional[str]:
        """Находит ID преподавателя по имени"""
        teachers = self.school_data.get('TEACHERS', {})
        for teacher_id, name in teachers.items():
            if teacher_name.lower() == name.lower():
                return teacher_id
        return None
    
    def get_teacher_schedule_today(self, teacher_name: str) -> str:
        """Получает расписание преподавателя на сегодня"""
        today = datetime.now(self.moscow_tz)
        return self._get_teacher_schedule_for_date(teacher_name, today, include_header=True)

    def get_teacher_schedule_tomorrow(self, teacher_name: str) -> str:
        """Получает расписание преподавателя на завтра"""
        tomorrow = datetime.now(self.moscow_tz) + timedelta(days=1)
        return self._get_teacher_schedule_for_date(teacher_name, tomorrow, include_header=True)
    
    def get_teacher_schedule_week(self, teacher_name: str) -> str:
        """Получает расписание преподавателя на текущую учебную неделю"""
        return self._get_week_schedule('teacher', teacher_name, self._get_teacher_schedule_for_date)
    
    def _get_teacher_schedule_for_date(self, teacher_name: str, date: datetime, include_header: bool = False) -> str:
        """Основная логика получения расписания преподавателя"""
        teacher_id = self.find_teacher_id(teacher_name)
        if not teacher_id:
            # Экранируем специальные символы Markdown в имени преподавателя
            safe_teacher_name = teacher_name.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            return f"❌ Преподаватель '{safe_teacher_name}' не найден"
        
        # Получаем период для даты
        period_id = self._get_period_for_date(date)
        if not period_id:
            return "❌ Не удалось определить учебный период"
        
        # Получаем день недели (1-понедельник, 7-воскресенье)
        day_num = date.isoweekday()
        if day_num > 5:  # Выходные
            day_name = self._get_day_name(date)
            date_str = date.strftime('%d.%m.%Y')
            # Экранируем специальные символы Markdown в имени преподавателя
            safe_teacher_name = teacher_name.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            return f"📅 *{safe_teacher_name} - {day_name}, {date_str}*\n\n🏖️ Выходной день"
        
        # Получаем расписание преподавателя
        schedule_data = self._get_teacher_schedule_data(period_id, teacher_id, day_num, date)
        
        return self._format_schedule_response('teacher', teacher_name, date, schedule_data, include_header)
    
    def _get_teacher_schedule_data(self, period_id: str, teacher_id: str, day_num: int, date: datetime) -> List[Dict]:
        """Получает данные расписания преподавателя - СПЕЦИФИЧНАЯ ЛОГИКА"""
        schedule = []
        class_schedule = self.school_data.get('CLASS_SCHEDULE', {}).get(period_id, {})
        
        # Ищем уроки, где преподает этот учитель
        for class_id, class_lessons in class_schedule.items():
            for lesson_num in range(1, self.school_data.get('LESSONSINDAY', 12) + 1):
                key = f"{day_num}{lesson_num:02d}"  # "401", "410" и т.д.

                if key in class_lessons:
                    raw_lesson_data = class_lessons[key]

                    # Проверяем, есть ли этот преподаватель в уроке
                    if 't' in raw_lesson_data and teacher_id in raw_lesson_data['t']:
                        # Глубокая копия данных урока, чтобы замены не мутировали исходное расписание
                        lesson_data = {
                            's': list(raw_lesson_data.get('s', [])),
                            't': list(raw_lesson_data.get('t', [])),
                            'r': list(raw_lesson_data.get('r', []))
                        }
                        raw_class_name = self.school_data.get('CLASSES', {}).get(class_id, 'Неизвестно')
                        # Используем ЧИСТОЕ имя класса для поиска замен: эскапирование
                        # только для отображения, а _find_class_id сравнивает с «чистыми»
                        # именами из CLASSES. Экранированная версия здесь ломала бы поиск.
                        class_name = raw_class_name

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