# services/teacher_service.py
from datetime import datetime, timedelta

from .base_schedule_service import BaseScheduleService


class TeacherService(BaseScheduleService):
    """Сервис для работы с расписанием преподавателей"""

    def get_available_teachers(self) -> list[str]:
        """Возвращает список всех преподавателей школы"""
        teachers = self.school_data.get('TEACHERS', {})
        return list(teachers.values())

    def search_teachers(self, query: str) -> list[str]:
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

    def find_teacher_id(self, teacher_name: str) -> str | None:
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

        # Перенос праздников: каникулы — занятий нет; transfer —
        # расписание другого дня недели (как на сайте)
        effective = self._get_effective_day(date, period_id)
        if effective is None:
            day_name = self._get_day_name(date)
            date_str = date.strftime('%d.%m.%Y')
            # Экранируем специальные символы Markdown в имени преподавателя
            safe_teacher_name = teacher_name.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            return f"📅 *{safe_teacher_name} - {day_name}, {date_str}*\n\n🏖️ Каникулы/праздник — занятий нет"
        eff_period_id, day_num = effective
        if not eff_period_id:
            return "❌ Не удалось определить учебный период"

        # Выходные (реальный день — перенесённый может быть рабочим)
        if date.isoweekday() > 5 and not self._get_holiday_info(date):
            day_name = self._get_day_name(date)
            date_str = date.strftime('%d.%m.%Y')
            # Экранируем специальные символы Markdown в имени преподавателя
            safe_teacher_name = teacher_name.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            return f"📅 *{safe_teacher_name} - {day_name}, {date_str}*\n\n🏖️ Выходной день"

        # Получаем расписание преподавателя
        schedule_data = self._get_teacher_schedule_data(eff_period_id, teacher_id, day_num, date)

        return self._format_schedule_response('teacher', teacher_name, date, schedule_data, include_header)

    def _get_teacher_schedule_data(self, period_id: str, teacher_id: str, day_num: int, date: datetime) -> list[dict]:
        """Получает данные расписания преподавателя - СПЕЦИФИЧНАЯ ЛОГИКА"""
        schedule = []
        class_schedule = self.school_data.get('CLASS_SCHEDULE', {}).get(period_id, {})
        teacher_exchanges = self._get_teacher_exchanges_for_date(teacher_id, date)

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

        # Перекрытие классных замен замещающим уроком из TEACH_EXCHANGE
        # (заменяющий учитель ведёт чужой урок в это время)
        for lesson_num, exchange in teacher_exchanges.items():
            self._apply_teacher_exchange(schedule, lesson_num, exchange, teacher_id)

        # Сортируем по номеру урока
        schedule.sort(key=lambda x: x['lesson_num'])
        return schedule

    def _get_teacher_exchanges_for_date(self, teacher_id: str, date: datetime) -> dict[int, dict]:
        """Замены учителя на дату: {номер урока (int): данные замены}."""
        date_str = date.strftime('%d.%m.%Y')
        raw = (self.school_data.get('TEACH_EXCHANGE', {})
               .get(teacher_id, {}).get(date_str, {}))
        result: dict[int, dict] = {}
        for lesson_num, exchange in raw.items():
            try:
                result[int(lesson_num)] = exchange
            except (TypeError, ValueError):
                continue
        return result

    def _apply_teacher_exchange(self, schedule: list[dict], lesson_num: int,
                                exchange: dict, teacher_id: str) -> None:
        """Применяет TEACH_EXCHANGE к уже собранному списку уроков учителя.

        Семантика Nikasoft: запись в TEACH_EXCHANGE[учитель][дата][урок]
        полностью перекрывает слот на этот урок — у учителя в этот слот
        ведётся урок из записи (классы c, предмет s, кабинет r),
        а не то, что было в базовом расписании. `"s": "F"` — урок у
        учителя отменён (свободный слот).
        """
        # Существующие уроки учителя в этом слоте заменяет новая запись
        slot_items = [item for item in schedule if item['lesson_num'] == lesson_num]
        for item in slot_items:
            schedule.remove(item)

        if exchange.get('s') == 'F':
            # Урок отменён — слот остаётся пустым (как у сайта при
            # StrikeOutFreeLsn=False: строка не показывается)
            if slot_items:
                schedule.append({
                    'lesson_num': lesson_num,
                    'class_name': slot_items[0]['class_name'],
                    'data': slot_items[0]['data'],
                    'has_exchange': True,
                    'is_cancelled': True,
                })
            return

        classes = self.school_data.get('CLASSES', {})
        rooms = self.school_data.get('ROOMS', {})
        class_names = [classes.get(str(c), '') for c in (exchange.get('c') or [])]
        class_name = ', '.join(n for n in class_names if n) or (
            slot_items[0]['class_name'] if slot_items else 'Неизвестно')

        room = exchange.get('r')
        rooms_list = [rooms.get(str(r), str(r)) for r in (room if isinstance(room, list) else [room])] if room else []

        # Учитель записи сам ведёт этот урок; сохраняем исходных учителей
        # слота, если они есть (групповые уроки)
        base_teachers = list(slot_items[0]['data'].get('t', [])) if slot_items else []
        teachers = base_teachers or ([teacher_id] if teacher_id else [])

        schedule.append({
            'lesson_num': lesson_num,
            'class_name': class_name,
            'data': {
                's': [exchange['s']] if 's' in exchange else (slot_items[0]['data'].get('s', []) if slot_items else []),
                't': teachers,
                'r': rooms_list or (list(slot_items[0]['data'].get('r', [])) if slot_items else []),
            },
            'has_exchange': True,
            'is_cancelled': False,
        })
