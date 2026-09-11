# services/exchange_detector.py
import json
import logging
import os
from datetime import datetime, timedelta

from config.config import Config, get_timezone


class ExchangeDetector:
    """Сервис для обнаружения новых замен в расписании"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.moscow_tz = get_timezone()
        # Храним предыдущее состояние расписаний для сравнения
        self.previous_schedules: dict[str, dict] = {}
        self.cache_file = self._get_cache_file()
        self.load_cache()

    @staticmethod
    def _get_cache_file() -> str:
        """Путь к кэшу замен в общей data-директории (не от cwd)."""
        db_path = Config().DB_PATH
        data_dir = os.path.dirname(db_path) or './data'
        return os.path.join(data_dir, 'exchange_cache.json')

    def load_cache(self):
        """Загружает кэш замен. Старый (плоский) формат сбрасывается."""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, encoding='utf-8') as f:
                    data = json.load(f)
                if self._is_legacy_cache(data):
                    self.logger.warning(
                        "Обнаружен старый формат кэша замен — сбрасываю (нужен сброс после смены схемы)")
                    self.previous_schedules = {}
                else:
                    self.previous_schedules = data
                    self.logger.info(
                        f"Загружен кэш замен из {self.cache_file}, школ: {len(self.previous_schedules)}")
            else:
                self.logger.info("Файл кэша замен не найден, используется пустой кэш")
        except Exception as e:
            self.logger.error(f"Ошибка загрузки кэша замен: {e}")
            self.previous_schedules = {}

    @staticmethod
    def _is_legacy_cache(data: dict) -> bool:
        """True, если структура не соответствует {school: {date: {...}}}."""
        import re
        date_re = re.compile(r'^\d{2}\.\d{2}\.\d{4}$')
        if not isinstance(data, dict):
            return True
        for _school, by_date in data.items():
            if not isinstance(by_date, dict):
                return True
            for key, value in by_date.items():
                if not date_re.match(str(key)) or not isinstance(value, dict):
                    return True
        return False

    def save_cache(self):
        """Атомарно сохраняет кэш; даты старше 3 суток удаляются."""
        try:
            self._prune_old_dates()
            os.makedirs(os.path.dirname(self.cache_file) or '.', exist_ok=True)
            tmp = f"{self.cache_file}.tmp"
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.previous_schedules, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.cache_file)
            self.logger.info(f"Кэш замен сохранен в {self.cache_file}")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения кэша замен: {e}")

    def _prune_old_dates(self):
        """Удаляет даты старше 3 суток, чтобы кэш не рос бесконечно."""
        cutoff = datetime.now(self.moscow_tz).date() - timedelta(days=3)
        for school_id in list(self.previous_schedules.keys()):
            by_date = self.previous_schedules[school_id]
            for date_str in list(by_date.keys()):
                try:
                    d = datetime.strptime(date_str, '%d.%m.%Y').date()
                except ValueError:
                    del by_date[date_str]
                    continue
                if d < cutoff:
                    del by_date[date_str]
            if not by_date:
                del self.previous_schedules[school_id]

    def clear_cache(self, school_id: str = None):
        """Очищает кэш замен"""
        if school_id:
            if school_id in self.previous_schedules:
                del self.previous_schedules[school_id]
                self.logger.info(f"Кэш для школы {school_id} очищен")
        else:
            self.previous_schedules = {}
            self.logger.info("Полный кэш замен очищен")
        self.save_cache()

    def detect_exchanges(self, school_id: str, school_data: dict, date: datetime,
                         persist: bool = True) -> list[dict]:
        """
        Обнаруживает новые замены для всех классов школы на конкретную дату.
        Состояние хранится отдельно для каждой даты, иначе проверка «завтра»
        перетирала бы baseline «сегодня». persist=False — не писать на диск
        (вызывающий делает один общий save_cache за цикл).
        """
        try:
            date_str = date.strftime('%d.%m.%Y')
            self.logger.info(f"Начало обнаружения замен для школы {school_id} на дату {date_str}")
            current_exchanges = self._get_current_exchanges(school_data, date)
            by_date = self.previous_schedules.get(school_id, {})
            previous_exchanges = by_date.get(date_str, {})

            self.logger.info(f"Найдено {len(current_exchanges)} классов с текущими заменами")

            new_exchanges = []
            for class_name, current_class_exchanges in current_exchanges.items():
                previous_class_exchanges = previous_exchanges.get(class_name, {})
                class_new_exchanges = self._compare_class_exchanges(
                    class_name, previous_class_exchanges, current_class_exchanges,
                    school_data, date
                )
                new_exchanges.extend(class_new_exchanges)

            # Классы, у которых замены были, а теперь их нет вовсе:
            # без этого удаление единственной замены класса не детектировалось бы
            for class_name, previous_class_exchanges in previous_exchanges.items():
                if class_name in current_exchanges:
                    continue
                removals = self._compare_class_exchanges(
                    class_name, previous_class_exchanges, {}, school_data, date
                )
                new_exchanges.extend(removals)

            # Сохраняем текущее состояние только для этой даты
            by_date[date_str] = current_exchanges
            self.previous_schedules[school_id] = by_date

            if persist:
                self.save_cache()

            self.logger.info(f"Обнаружено {len(new_exchanges)} новых замен всего для школы {school_id}")
            return new_exchanges

        except Exception as e:
            self.logger.error(f"Error detecting exchanges for school {school_id}: {e}")
            return []

    def _get_current_exchanges(self, school_data: dict, date: datetime) -> dict[str, dict]:
        """Получает текущие замены для всех классов"""
        exchanges = {}

        # Получаем все классы школы
        classes = school_data.get('CLASSES', {})

        for class_id, class_name in classes.items():
            try:
                # Получаем замены для класса
                class_exchanges = self._get_class_exchanges(class_name, class_id, date, school_data)
                if class_exchanges:
                    exchanges[class_name] = class_exchanges
            except Exception as e:
                self.logger.error(f"Error getting exchanges for class {class_name}: {e}")

        return exchanges

    def _get_class_exchanges(self, class_name: str, class_id: str, date: datetime, school_data: dict) -> dict:
        """Получает замены для конкретного класса. lesson_num всегда строка."""
        date_str = date.strftime('%d.%m.%Y')

        # Получаем замены из данных школы
        class_exchanges_data = school_data.get('CLASS_EXCHANGE', {}).get(class_id, {}).get(date_str, {})

        exchanges = {}
        for lesson_num_str, exchange_data in class_exchanges_data.items():
            try:
                # Единый формат ключа — строка
                key = str(int(lesson_num_str))
                formatted = self._format_exchange_for_notification(
                    class_name, {'lesson_num': key, 'data': exchange_data,
                                 'is_cancelled': exchange_data.get('s') == 'F'},
                    school_data, date
                )
                # timestamp — datetime, не сериализуется в JSON-кэш замен
                formatted.pop('timestamp', None)
                exchanges[key] = {
                    'lesson_num': key,
                    'data': exchange_data,
                    'is_cancelled': exchange_data.get('s') == 'F',
                    'formatted': formatted
                }
            except (ValueError, KeyError) as e:
                self.logger.warning(f"Error parsing exchange for class {class_name}, lesson {lesson_num_str}: {e}")

        return exchanges

    def _compare_class_exchanges(self, class_name: str, previous: dict, current: dict,
                                 school_data: dict = None, date: datetime = None) -> list[dict]:
        """Сравнивает замены класса и возвращает новые. Ключи lesson_num — строки."""
        new_exchanges = []

        # Ищем новые замены
        for lesson_num, current_exchange in current.items():
            previous_exchange = previous.get(lesson_num)

            # Если замена новая или изменилась
            if not previous_exchange or self._is_exchange_changed(previous_exchange, current_exchange):
                formatted_exchange = self._format_exchange_for_notification(
                    class_name, current_exchange, school_data, date
                )
                if formatted_exchange:
                    new_exchanges.append(formatted_exchange)

        # Симметричный diff: замены, исчезнувшие из текущего состояния
        for lesson_num, previous_exchange in previous.items():
            if lesson_num in current:
                continue
            formatted = previous_exchange.get('formatted') or {}
            new_exchanges.append({
                'class_name': class_name,
                'lesson_num': int(lesson_num),
                'removed': True,
                'original_subject': formatted.get('original_subject', f'Урок {lesson_num}'),
                'new_subject': '', 'new_teacher': '', 'new_room': '',
                'is_cancelled': False,
                'timestamp': date,
            })

        return new_exchanges

    def _is_exchange_changed(self, previous: dict, current: dict) -> bool:
        """Проверяет, изменилась ли замена"""
        # Сравниваем основные поля
        fields_to_compare = ['data', 'is_cancelled']
        for field in fields_to_compare:
            prev_val = previous.get(field)
            curr_val = current.get(field)

            # Преобразуем списки в строки для безопасного сравнения
            if isinstance(prev_val, list) or isinstance(curr_val, list):
                prev_val = str(prev_val) if isinstance(prev_val, list) else prev_val
                curr_val = str(curr_val) if isinstance(curr_val, list) else curr_val

            if prev_val != curr_val:
                self.logger.info(f"Обнаружено изменение в поле {field}: {prev_val} -> {curr_val}")
                return True
        return False

    def _format_exchange_for_notification(self, class_name: str, exchange: dict,
                                          school_data: dict = None, date: datetime = None) -> dict:
        """Форматирует замена для уведомления"""
        lesson_num = exchange.get('lesson_num')
        exchange_data = exchange.get('data', {})
        is_cancelled = exchange.get('is_cancelled', False)

        # Получаем информацию о предмете, преподавателе, кабинете
        original_subject = self._get_original_subject(class_name, lesson_num, school_data)

        # Преобразуем коды в реальные названия, если school_data доступен
        new_subject_code = exchange_data.get('s', '')
        new_teacher_code = exchange_data.get('t', '')
        new_room_code = exchange_data.get('r', '')

        # Обрабатываем возможные списки в кодах
        if isinstance(new_subject_code, list):
            new_subject_code = ','.join(new_subject_code) if new_subject_code else ''
        if isinstance(new_teacher_code, list):
            new_teacher_code = ','.join(new_teacher_code) if new_teacher_code else ''
        if isinstance(new_room_code, list):
            new_room_code = ','.join(new_room_code) if new_room_code else ''

        # Используем словари из school_data, если он доступен
        subjects_dict = school_data.get('SUBJECTS', {}) if school_data else {}
        teachers_dict = school_data.get('TEACHERS', {}) if school_data else {}
        rooms_dict = school_data.get('ROOMS', {}) if school_data else {}

        new_subject = self._convert_codes_to_names(new_subject_code, subjects_dict, 'subject') if new_subject_code and new_subject_code != 'F' else ''
        new_teacher = self._convert_codes_to_names(new_teacher_code, teachers_dict, 'teacher') if new_teacher_code else ''
        new_room = self._convert_codes_to_names(new_room_code, rooms_dict, 'room') if new_room_code else ''

        return {
            'class_name': class_name,
            'lesson_num': int(lesson_num) if lesson_num is not None else None,
            'original_subject': original_subject,
            'new_subject': new_subject,
            'new_teacher': new_teacher,
            'new_room': new_room,
            'is_cancelled': is_cancelled,
            'timestamp': date or datetime.now(self.moscow_tz)
        }

    def _convert_codes_to_names(self, codes_str, names_dict, type_name: str) -> str:
        """Преобразует коды в названия для предметов, преподавателей или кабинетов"""
        if not codes_str or not names_dict:
            return codes_str

        # Если строка содержит запятые, это список кодов
        if ',' in codes_str:
            codes = [code.strip() for code in codes_str.split(',')]
            names = []
            for code in codes:
                name = names_dict.get(code, code)  # Если нет в словаре, возвращаем сам код
                if type_name == 'teacher':
                    # Для преподавателей возвращаем полное имя
                    names.append(name)
                elif name != code:  # Добавляем только если нашли реальное имя
                    names.append(name)
                else:
                    # Если не нашли имя, добавляем код в кавычках как в текущем уведомлении
                    names.append(f"'{code}'")
            return ', '.join(names)
        else:
            # Один код
            name = names_dict.get(codes_str, codes_str)
            if type_name == 'teacher':
                # Для преподавателей возвращаем полное имя
                return name
            return name if name != codes_str else f"'{codes_str}'"

    def _get_original_subject(self, class_name: str, lesson_num: int, school_data: dict = None) -> str:
        """Получает оригинальное название предмета (упрощенная реализация)"""
        # Возвращаем стандартное обозначение урока, т.к. получение оригинального предмета из-за
        # сложной структуры данных расписания требует более тщательной проверки типов данных
        return f"Урок {lesson_num}"

    def clear_school_cache(self, school_id: str):
        """Очищает кэш для школы (например, при принудительном обновлении)"""
        if school_id in self.previous_schedules:
            del self.previous_schedules[school_id]
            self.save_cache()
