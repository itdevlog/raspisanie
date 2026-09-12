# services/room_service.py
from datetime import datetime, timedelta

from .base_schedule_service import BaseScheduleService


class RoomService(BaseScheduleService):
    """Сервис для работы с расписанием кабинетов"""

    def get_available_rooms(self) -> list[str]:
        """Возвращает список всех кабинетов школы"""
        rooms = self.school_data.get('ROOMS', {})
        return list(rooms.values())

    def search_rooms(self, query: str) -> list[str]:
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

    def find_room_id(self, room_name: str) -> str | None:
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

        # Перенос праздников: каникулы — занятий нет; transfer —
        # расписание другого дня недели (как на сайте)
        effective = self._get_effective_day(date, period_id)
        if effective is None:
            day_name = self._get_day_name(date)
            date_str = date.strftime('%d.%m.%Y')
            # Экранируем специальные символы Markdown в названии кабинета
            safe_room_name = room_name.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            return f"📅 *Кабинет {safe_room_name} - {day_name}, {date_str}*\n\n🏖️ Каникулы/праздник — занятий нет"
        eff_period_id, day_num = effective
        if not eff_period_id:
            return "❌ Не удалось определить учебный период"

        # Выходные (реальный день — перенесённый может быть рабочим)
        if date.isoweekday() > 5 and not self._get_holiday_info(date):
            day_name = self._get_day_name(date)
            date_str = date.strftime('%d.%m.%Y')
            # Экранируем специальные символы Markdown в названии кабинета
            safe_room_name = room_name.replace('*', '\\*').replace('_', '\\_').replace('`', '\\`')
            return f"📅 *Кабинет {safe_room_name} - {day_name}, {date_str}*\n\n🏖️ Выходной день"

        # Получаем расписание кабинета
        schedule_data = self._get_room_schedule_data(eff_period_id, room_id, day_num, date)

        return self._format_schedule_response('room', room_name, date, schedule_data, include_header)

    def _get_room_schedule_data(self, period_id: str, room_id: str, day_num: int, date: datetime) -> list[dict]:
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

    # ---------- свободные кабинеты («Найти свободный кабинет» с сайта) ----------

    def get_free_rooms(self, date: datetime, lesson_num: int) -> list[str]:
        """Имена свободных кабинетов на урок lesson_num в дату.

        Кабинет свободен, если после применения всех замен (CLASS_EXCHANGE,
        TEACH_EXCHANGE, отмены 'F') в нём нет занятий в этот слот.
        В каникулы/выходные свободны все.
        """
        all_rooms = self.school_data.get('ROOMS', {})
        if not all_rooms:
            return []

        period_id = self._get_period_for_date(date)
        if not period_id:
            return []

        effective = self._get_effective_day(date, period_id)
        if effective is None:  # каникулы — все свободны
            return list(all_rooms.values())
        eff_period_id, day_num = effective
        if not eff_period_id or day_num > 5:
            return []

        busy = self._get_busy_rooms_for_lesson(eff_period_id, day_num, date, lesson_num)
        free = [name for room_id, name in all_rooms.items() if room_id not in busy]
        return sorted(free, key=_room_sort_key)

    def _get_busy_rooms_for_lesson(self, period_id: str, day_num: int,
                                   date: datetime, lesson_num: int) -> set[str]:
        """ID кабинетов, занятых на урок lesson_num (с учётом замен)."""
        busy: set[str] = set()
        rooms_dict = self.school_data.get('ROOMS', {})
        date_str = date.strftime('%d.%m.%Y')
        key = f"{day_num}{lesson_num:02d}"

        # 1) Базовое расписание + CLASS_EXCHANGE
        class_schedule = self.school_data.get('CLASS_SCHEDULE', {}).get(period_id, {})
        for class_id, class_lessons in class_schedule.items():
            lesson = class_lessons.get(key)
            if not lesson:
                continue
            exchange = (self.school_data.get('CLASS_EXCHANGE', {})
                        .get(class_id, {}).get(date_str, {}).get(str(lesson_num)))
            if exchange is not None:
                if isinstance(exchange.get('s'), str) and exchange['s'] == 'F':
                    continue  # урок отменён — кабинет свободен
                rooms = exchange.get('r', [])
            else:
                rooms = lesson.get('r', [])
            for room in rooms if isinstance(rooms, list) else [rooms]:
                if room in rooms_dict:
                    busy.add(room)

        # 2) TEACH_EXCHANGE: замещающий учитель ведёт урок в кабинете r
        for teacher_id, by_date in self.school_data.get('TEACH_EXCHANGE', {}).items():
            exchange = by_date.get(date_str, {}).get(str(lesson_num))
            if not exchange or exchange.get('s') == 'F':
                continue
            for room in exchange.get('r', []) if isinstance(exchange.get('r'), list) else [exchange.get('r')]:
                if room in rooms_dict:
                    busy.add(room)

        return busy

    def get_free_rooms_message(self, date: datetime, lesson_num: int) -> str:
        """Готовый текст «свободные кабинеты на урок N» (как на сайте)."""
        free = self.get_free_rooms(date, lesson_num)
        date_str = date.strftime('%d.%m.%Y')
        times = self._get_lesson_times(lesson_num)
        safe_date = self._escape_markdown(date_str)

        header = f"🔍 *Свободные кабинеты на {lesson_num}-й урок*\n"
        header += f"🕐 {times[0]}-{times[1]} • {safe_date}\n\n"

        if not free:
            return header + "❌ Все кабинеты заняты"

        lines = [self._escape_markdown(name) for name in free]
        return header + " ".join(lines)


def _room_sort_key(name: str):
    """Числовая сортировка кабинетов: 101, 102, 2а, актовый."""
    digits = ''.join(ch for ch in name if ch.isdigit())
    return (int(digits) if digits else 10 ** 9, name)
