# services/base_schedule_service.py
from datetime import datetime, timedelta

from config.config import get_timezone
from services.exchange_service import ExchangeService


def format_time_ago(time_diff: timedelta) -> str:
    """Форматирует разницу во времени (единый хелпер)."""
    if time_diff < timedelta(minutes=1):
        return "только что"
    elif time_diff < timedelta(hours=1):
        return f"{int(time_diff.total_seconds() / 60)} мин"
    elif time_diff < timedelta(days=1):
        return f"{int(time_diff.total_seconds() / 3600)} ч"
    else:
        return f"{time_diff.days} дн"


def _nth(values, idx):
    """Параллельные списки: значение idx, иначе первое (или None)."""
    if isinstance(values, list):
        if idx < len(values):
            return values[idx]
        return values[0] if values else None
    return values


def find_class_id(school_data: dict, class_name: str) -> str | None:
    """Находит ID класса по точному совпадению имени (без учета регистра)."""
    if not class_name:
        return None
    classes = school_data.get('CLASSES', {})
    class_name_lower = class_name.strip().lower()
    for class_id, name in classes.items():
        if name.strip().lower() == class_name_lower:
            return class_id
    return None


class BaseScheduleService:
    """
    Базовый класс для всех сервисов расписания
    Содержит общую логику для teacher_service, room_service, schedule_service
    """

    @staticmethod
    def _escape_markdown(text: str) -> str:
        """Экранирует спецсимволы legacy Markdown (единый хелпер)."""
        from services.text_utils import escape_markdown
        return escape_markdown(text)

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

    def _get_holiday_info(self, date: datetime) -> dict | None:
        """Информация о переносе/каникулах для даты (HOLIDAY_TRANSFER).

        Формат Nikasoft: {"дд.мм.гггг": {"type": "vacation"|"transfer",
        "daynum": 1..7, "weeknum": 1|2, "period": id}}.
        """
        date_str = date.strftime('%d.%m.%Y')
        info = self.school_data.get('HOLIDAY_TRANSFER', {}).get(date_str)
        return info if isinstance(info, dict) else None

    def _is_vacation_day(self, date: datetime) -> bool:
        """True, если дата — неучебный день (каникулы/праздник)."""
        info = self._get_holiday_info(date)
        return bool(info and info.get('type') == 'vacation')

    def _get_effective_day(self, date: datetime,
                           period_id: str | None = None) -> tuple[str | None, int] | None:
        """(period_id, day_num) с учётом переноса праздников - ОБЩАЯ ЛОГИКА.

        Возвращает None, если дата — каникулы (занятий нет).
        При переносе ("transfer") день работает по расписанию daynum
        (опционально weeknum-недели и period-периода), как на сайте.
        period_id в результате может быть None, если период даты не найден —
        вызывающие уже проверяют это выше по потоку.
        """
        info = self._get_holiday_info(date)
        if not info:
            return period_id, date.isoweekday()

        htype = info.get('type')
        if htype == 'vacation':
            return None

        if htype == 'transfer':
            raw_day = info.get('daynum')
            try:
                day_num = int(raw_day) if raw_day is not None else date.isoweekday()
            except (TypeError, ValueError):
                day_num = date.isoweekday()
            eff_period = info.get('period') or period_id
            return eff_period, day_num

        # неизвестный тип — обычный день
        return period_id, date.isoweekday()

    def _format_time_ago(self, time_diff: timedelta) -> str:
        """Форматирует разницу во времени - ОБЩАЯ ЛОГИКА"""
        return format_time_ago(time_diff)

    def _find_class_id(self, class_name: str) -> str | None:
        """Находит ID класса по имени - ОБЩАЯ ЛОГИКА"""
        return find_class_id(self.school_data, class_name)

    def _get_lesson_times(self, lesson_num: int) -> list[str]:
        """Получает время урока по номеру - ОБЩАЯ ЛОГИКА"""
        return self.school_data.get('LESSON_TIMES', {}).get(str(lesson_num), ['?', '?'])

    def _day_payload(self, kind: str, entity: str, date: datetime) -> dict:
        """Общий каркас дневного payload: даты, каникулы, выходные."""
        return {
            'date': date.strftime('%d.%m.%Y'),
            'day_name': self._get_day_name(date),
            'kind': kind,
            'entity': entity,
            'lessons': [],
            'vacation': False,
            'weekend': False,
        }

    def _lessons_payload(self, schedule_data: list[dict]) -> list[dict]:
        """Преобразует внутренние lesson-словари в JSON-payload.

        data['s'/'t'/'r'] — параллельные списки: s[0] идёт с t[0] и r[0] (группы).
        Дедупликация не нужна: группы валидны по отдельности. Имена неизвестных
        id (замены TEACH_EXCHANGE кладут имена, не id) — показываем как есть.
        """
        lessons = []
        for lesson in schedule_data:
            times = self._get_lesson_times(lesson['lesson_num'])
            data = lesson.get('data', {})
            items = []
            length = max(len(data.get('s', [])), len(data.get('t', [])), len(data.get('r', [])))
            for i in range(length):
                subject_id = _nth(data.get('s'), i)
                teacher_id = _nth(data.get('t'), i)
                room_id = _nth(data.get('r'), i)
                items.append({
                    'subject': self.school_data.get('SUBJECTS', {}).get(subject_id, str(subject_id) if subject_id is not None else None),
                    'teacher': self.school_data.get('TEACHERS', {}).get(teacher_id, str(teacher_id) if teacher_id is not None else None),
                    'room': self.school_data.get('ROOMS', {}).get(room_id, str(room_id) if room_id is not None else None),
                    'class_name': lesson.get('class_name'),
                })
            lessons.append({
                'num': lesson['lesson_num'],
                'start': times[0],
                'end': times[1],
                'items': items,
                'has_exchange': lesson.get('has_exchange', False),
                'is_cancelled': lesson.get('is_cancelled', False),
            })
        return lessons

    def _week_dates(self, week_offset: int) -> list[datetime]:
        """Список дат Пн-Пт указанной недели."""
        today = datetime.now(self.moscow_tz)
        monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        return [monday + timedelta(days=d) for d in range(5)]

    def get_next_lesson(self, schedule_data: list[dict], date: datetime,
                        now: datetime | None = None) -> dict | None:
        """Возвращает текущий или следующий урок по времени LESSON_TIMES.

        Приоритет — предстоящий урок; если его нет (текущий был последним),
        возвращается идущий сейчас урок.
        """
        if not schedule_data:
            return None
        now = now or datetime.now(self.moscow_tz)
        current = None
        for lesson in sorted(schedule_data, key=lambda x: x['lesson_num']):
            times = self._get_lesson_times(lesson['lesson_num'])
            if len(times) < 2 or times[0] == '?':
                continue
            try:
                start = now.replace(hour=int(times[0][:2]), minute=int(times[0][3:5]),
                                    second=0, microsecond=0)
                end = start.replace(hour=int(times[1][:2]), minute=int(times[1][3:5]))
            except (ValueError, IndexError):
                continue
            if start < now and now <= end:
                current = lesson
            elif now <= start:
                return lesson
        return current

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

    def _format_lesson_line(self, lesson_data: dict, has_exchange: bool = False,
                            is_cancelled: bool = False) -> str:
        """Форматирует строку урока - ОБЩАЯ ЛОГИКА"""
        lesson_num = lesson_data['lesson_num']
        lesson_times = self._get_lesson_times(lesson_num)

        if is_cancelled:
            return f"❌ *{lesson_num}. {lesson_times[0]}-{lesson_times[1]} • ОТМЕНЕНО*"

        # Класс урока (для расписаний учителя/кабинета)
        class_name = lesson_data.get('class_name')
        class_part = ''
        if class_name:
            safe_class = self._escape_markdown(str(class_name))
            class_part = f" ({safe_class})"

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

        # Кабинеты (убираем дубли).
        # Значение может быть как id (базовое расписание), так и готовым
        # именем (замены TEACH_EXCHANGE) — неизвестное показываем как есть.
        rooms = []
        for room_id in lesson_data['data'].get('r', []):
            room_name = self.school_data.get('ROOMS', {}).get(room_id, str(room_id))
            # Экранируем специальные символы Markdown в названии кабинета
            room_name = self._escape_markdown(room_name)
            if room_name not in rooms:
                rooms.append(room_name)

        # Если есть несколько преподавателей или кабинетов, форматируем в виде списка
        if len(teachers) > 1 or len(rooms) > 1:
            lines = []
            # Основная строка с временем и предметом в курсиве (в Telegram отображается как жирный)
            subject_part = f"{', '.join(subjects)}" if subjects else "?"
            main_line = f"{'🔄 ' if has_exchange else ''}*{lesson_num}. {lesson_times[0]}-{lesson_times[1]} • {subject_part}{class_part}*"
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
            main_line = f"{'🔄 ' if has_exchange else ''}*{lesson_num}. {lesson_times[0]}-{lesson_times[1]} • {subject_part}{class_part}*"

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

    def _get_week_schedule(self, entity_type: str, entity_name: str, get_daily_schedule_func,
                           week_offset: int = 0) -> str:
        """Получает расписание на неделю - ОБЩАЯ ЛОГИКА"""
        today = datetime.now(self.moscow_tz)
        current_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)

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
