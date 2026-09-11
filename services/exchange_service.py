from datetime import datetime

from config.config import get_timezone


class ExchangeService:
    def __init__(self, school_data: dict):
        self.school_data = school_data
        self.moscow_tz = get_timezone()

    def apply_exchanges_to_schedule(self, class_name: str, schedule_data: list[dict], date: datetime) -> list[dict]:
        """Применяет замены к расписанию"""
        class_id = self._find_class_id(class_name)
        if not class_id:
            return schedule_data

        date_str = date.strftime('%d.%m.%Y')
        class_exchanges = self.school_data.get('CLASS_EXCHANGE', {}).get(class_id, {}).get(date_str, {})

        if not class_exchanges:
            return schedule_data

        updated_schedule = []
        for lesson in schedule_data:
            lesson_num = lesson['lesson_num']

            # Проверяем есть ли замена для этого урока
            exchange = class_exchanges.get(str(lesson_num))
            if exchange:
                # Применяем замену
                updated_lesson = self._apply_exchange(lesson, exchange)
                updated_schedule.append(updated_lesson)
            else:
                updated_schedule.append(lesson)

        return updated_schedule

    def _apply_exchange(self, lesson: dict, exchange: dict) -> dict:
        """Применяет конкретную замену к уроку (глубокая копия, не мутирует school_data)"""
        updated_lesson = {
            **lesson,
            'data': {**lesson.get('data', {})}
        }

        # Если урок отменен
        if exchange.get('s') == 'F':
            updated_lesson['is_cancelled'] = True
            return updated_lesson

        # Замена предмета: принимаем как строку, так и список
        if 's' in exchange:
            value = exchange['s']
            updated_lesson['data']['s'] = value if isinstance(value, list) else [value]

        # Замена преподавателя: принимаем как строку, так и список
        if 't' in exchange:
            value = exchange['t']
            updated_lesson['data']['t'] = value if isinstance(value, list) else [value]

        # Замена кабинета: принимаем как строку, так и список
        if 'r' in exchange:
            value = exchange['r']
            updated_lesson['data']['r'] = value if isinstance(value, list) else [value]

        updated_lesson['has_exchange'] = True
        return updated_lesson

    def _find_class_id(self, class_name: str) -> str | None:
        """Находит ID класса по имени (делегирует общий хелпер)"""
        from services.base_schedule_service import find_class_id
        return find_class_id(self.school_data, class_name)
