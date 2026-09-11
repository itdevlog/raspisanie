# services/base_schedule_service.py
from datetime import datetime, timedelta

from config.config import get_timezone
from services.exchange_service import ExchangeService


class BaseScheduleService:
    """
    Базовый класс для всех сервисов расписания
    Содержит общую логику для teacher_service, room_service, schedule_service
    """

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Экранирует спецсимволы legacy Markdown.

        Помимо `*`/`_`/`` ` `` экранируем `[ ] ( )` — без них сообщение
        с именем/названием, содержащим эти символы, не уйдёт (Can't parse entities).
        """
        for ch in ('_', '*', '[', ']', '(', ')', '`'):
            text = text.replace(ch, '\\' + ch)
        return text

    def __init__(self, school_data: dict):
        self.school_data = school_data
        self.exchange_service = ExchangeService(school_data)
        self.moscow_tz = get_timezone()

    def _get_period_for_date(self, date: datetime) -> str | None:
        """Определяет учебный период для даты - ОБЩАЯ ЛОГИКА"""
        periods = self.school_data.get('PERIODS', {})

        for period_id, period_data in periods.items():
            try:
                start_date = datetime.strptime(period_data['b'], '%d.%m.%Y').date()
                end_date = datetime.strptime(period_data['e'], '%d.%m.%Y').date()

                if start_date <= date.date() <= end_date:
                    return period_id
            except (ValueError, KeyError):
                continue

        return None

    def _format_time_ago(self, time_diff: timedelta) -> str:
        """Форматирует разницу во времени - ОБЩАЯ ЛОГИКА"""
        if time_diff < timedelta(minutes=1):
            return "только что"
        elif time_diff < timedelta(hours=1):
            minutes = int(time_diff.total_seconds() / 60)
            return f"{minutes} мин"
        elif time_diff < timedelta(days=1):
            hours = int(time_diff.total_seconds() / 3600)
            return f"{hours} ч"
        else:
            days = time_diff.days
            return f"{days} дн"

    def _get_lesson_times(self, lesson_num: int) -> list[str]:
        """Получает время урока по номеру - ОБЩАЯ ЛОГИКА"""
        return self.school_data.get('LESSON_TIMES', {}).get(str(lesson_num), ['?', '?'])

    def _get_day_name(self, date: datetime) -> str:
        """Получает название дня недели - ОБЩАЯ ЛОГИКА"""
        day_names = self.school_data.get('DAY_NAMES', [])
        day_num = date.isoweekday()
        return day_names[day_num - 1] if 0 <= day_num - 1 < len(day_names) else f"День {day_num}"

    def _format_schedule_header(self, entity_type: str, entity_name: str, date: datetime, include_header: bool = True) -> str:
        """Форматирует заголовок расписания - ОБЩАЯ ЛОГИКА"""
        if not include_header:
            return ""

        date_str = date.strftime('%d.%m.%Y')
        day_name = self._get_day_name(date)

        # Экранируем специальные символы Markdown
        safe_entity_name = self._escape_markdown(entity_name)

        type_icons = {
            'class': '📅',
            'teacher': '👨‍🏫',
            'room': '🏫'
        }

        icon = type_icons.get(entity_type, '📅')
        return f"{icon} *{safe_entity_name} - {day_name}, {date_str}*\n\n"

    def _format_lesson_line(self, lesson_data: dict, has_exchange: bool = False, is_cancelled: bool = False) -> str:
        """Форматирует строку урока - ОБЩАЯ ЛОГИКА"""
        lesson_num = lesson_data['lesson_num']
        lesson_times = self._get_lesson_times(lesson_num)

        if is_cancelled:
            return f"❌ *{lesson_num}. {lesson_times[0]}-{lesson_times[1]} • ОТМЕНЕНО*"

        # Предметы (убираем дубли)
        subjects = []
        for subject_id in lesson_data['data'].get('s', []):
            subject_name = self.school_data.get('SUBJECTS', {}).get(subject_id, '?')
            # Экранируем специальные символы Markdown в названии предмета
            subject_name = self._escape_markdown(subject_name)
            if subject_name not in subjects:
                subjects.append(subject_name)

        # Преподаватели (убираем дубли)
        teachers = []
        for teacher_id in lesson_data['data'].get('t', []):
            teacher_name = self.school_data.get('TEACHERS', {}).get(teacher_id, '?')
            # Экранируем специальные символы Markdown в имени преподавателя
            teacher_name = self._escape_markdown(teacher_name)
            if teacher_name not in teachers:
                teachers.append(teacher_name)

        # Кабинеты (убираем дубли)
        rooms = []
        for room_id in lesson_data['data'].get('r', []):
            room_name = self.school_data.get('ROOMS', {}).get(room_id, '?')
            # Экранируем специальные символы Markdown в названии кабинета
            room_name = self._escape_markdown(room_name)
            if room_name not in rooms:
                rooms.append(room_name)

        # Если есть несколько преподавателей или кабинетов, форматируем в виде списка
        if len(teachers) > 1 or len(rooms) > 1:
            lines = []
            # Основная строка с временем и предметом в курсиве (в Telegram отображается как жирный)
            subject_part = f"{', '.join(subjects)}" if subjects else "?"
            main_line = f"{'🔄 ' if has_exchange else ''}*{lesson_num}. {lesson_times[0]}-{lesson_times[1]} • {subject_part}*"
            lines.append(main_line)

            # Создаем строки для каждой группы
            max_count = max(len(teachers), len(rooms)) if teachers and rooms else max(len(teachers), len(rooms))

            for i in range(max_count):
                teacher = teachers[i] if i < len(teachers) else None
                room = rooms[i] if i < len(rooms) else None

                if teacher and room:
                    detail_line = f"   группа {i+1} - {teacher} • {room}"
                elif teacher:
                    detail_line = f"   группа {i+1} - {teacher}"
                elif room:
                    detail_line = f"   группа {i+1} - {room}"
                else:
                    continue  # Пропускаем, если нет ни преподавателя, ни кабинета

                lines.append(detail_line)

            return "\n".join(lines)
        else:
            # Стандартное форматирование для одного преподавателя/кабинета
            subject_part = f"{', '.join(subjects)}" if subjects else "?"
            main_line = f"{'🔄 ' if has_exchange else ''}*{lesson_num}. {lesson_times[0]}-{lesson_times[1]} • {subject_part}*"

            if teachers and rooms:
                main_line += f"\n   {teachers[0]} • {rooms[0]}"
            elif teachers:
                main_line += f"\n   {teachers[0]}"
            elif rooms:
                main_line += f"\n   {rooms[0]}"

            return main_line

    def _format_schedule_response(self, entity_type: str, entity_name: str, date: datetime,
                                schedule_data: list[dict], include_header: bool = True) -> str:
        """Форматирует полный ответ с расписанием - ОБЩАЯ ЛОГИКА"""
        response = []

        # Добавляем заголовок
        header = self._format_schedule_header(entity_type, entity_name, date, include_header)
        if header:
            response.append(header)

        if not schedule_data:
            response.append("📭 Занятий нет")
            return "\n".join(response)

        # Проверяем есть ли замены или отмены
        has_exchanges = any(lesson.get('has_exchange') for lesson in schedule_data)
        has_cancellations = any(lesson.get('is_cancelled') for lesson in schedule_data)

        if has_exchanges or has_cancellations:
            response.append("🔄 Есть замены:")
            response.append("")

        # Добавляем уроки
        for item in schedule_data:
            if item.get('is_cancelled') and not self.school_data.get('STRIKEOUT_FREE_LSN', True):
                continue

            lesson_line = self._format_lesson_line(
                item,
                has_exchange=item.get('has_exchange', False),
                is_cancelled=item.get('is_cancelled', False)
            )
            response.append(lesson_line)

        return "\n".join(response)

    def _get_week_schedule(self, entity_type: str, entity_name: str, get_daily_schedule_func) -> str:
        """Получает расписание на неделю - ОБЩАЯ ЛОГИКА"""
        today = datetime.now(self.moscow_tz)
        current_monday = today - timedelta(days=today.weekday())

        week_schedule = []

        for day_offset in range(5):  # Пн-Пт
            date = current_monday + timedelta(days=day_offset)
            day_schedule = get_daily_schedule_func(entity_name, date, include_header=True)

            if day_schedule and "Занятий нет" not in day_schedule and "Выходной день" not in day_schedule:
                week_schedule.append(day_schedule)

        if not week_schedule:
            type_names = {
                'class': 'класса',
                'teacher': 'преподавателя',
                'room': 'кабинета'
            }
            type_name = type_names.get(entity_type, '')
            # Экранируем специальные символы Markdown в названии сущности
            safe_entity_name = self._escape_markdown(entity_name)
            return f"📅 *Недельное расписание {type_name} {safe_entity_name}*\n\n❌ Нет занятий на учебные дни этой недели"

        week_start = current_monday.strftime('%d.%m.%Y')
        week_end = (current_monday + timedelta(days=4)).strftime('%d.%m.%Y')

        type_icons = {
            'class': '📅',
            'teacher': '👨‍🏫',
            'room': '🏫'
        }
        icon = type_icons.get(entity_type, '📅')

        # Экранируем специальные символы Markdown в названии сущности
        safe_entity_name = self._escape_markdown(entity_name)

        week_header = f"{icon} *Недельное расписание {safe_entity_name}*\n*{week_start} - {week_end}*"
        return f"{week_header}\n\n" + "\n\n".join(week_schedule)
