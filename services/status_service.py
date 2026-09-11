import logging
from datetime import datetime, timedelta

from config.config import get_timezone

logger = logging.getLogger(__name__)


def status_icon(status: dict) -> str:
    """Вытаскивает иконку статуса из status['status'] (уже содержит ✅/⚠️/🔴).

    Единый источник иконки для `/status`, админ-панели и меню — раньше админка
    сама выводила ⚠️ для всего, что не «Актуально», игнорируя 🔴 «Устарело».
    """
    s = status.get('status', '')
    for icon in ('✅', '⚠️', '🔴', '❌'):
        if icon in s:
            return icon
    return '⚠️'


class StatusService:
    def __init__(self, schools_data: dict):
        self.schools_data = schools_data
        self.moscow_tz = get_timezone()

    def get_school_status(self, school_id: str) -> dict:
        """Получает статус данных для школы"""
        school_data = self.schools_data.get(school_id)

        if not school_data:
            return {
                'loaded': False,
                'status': '❌ Не загружено',
                'last_update': None,
                'details': 'Данные не загружены'
            }

        # Получаем время экспорта из данных
        export_date = school_data.get('EXPORT_DATE', '')
        export_time = school_data.get('EXPORT_TIME', '')

        try:
            # Парсим дату и время экспорта - ИСПРАВЛЕНО ФОРМАТЫ
            if export_date and export_time:
                # Убираем секунды из времени если они есть
                time_without_seconds = export_time.split(':')[0] + ':' + export_time.split(':')[1]
                export_datetime_str = f"{export_date} {time_without_seconds}"

                # Пробуем разные форматы даты
                try:
                    export_datetime = datetime.strptime(export_datetime_str, '%d.%m.%Y %H:%M')
                except ValueError:
                    # Если не получилось, пробуем другой формат
                    try:
                        export_datetime = datetime.strptime(export_date, '%d.%m.%Y')
                        # Если время не парсится, используем только дату
                        if export_time:
                            try:
                                time_part = datetime.strptime(export_time, '%H:%M:%S').time()
                                export_datetime = datetime.combine(export_datetime.date(), time_part)
                            except ValueError:
                                try:
                                    time_part = datetime.strptime(export_time, '%H:%M').time()
                                    export_datetime = datetime.combine(export_datetime.date(), time_part)
                                except ValueError:
                                    # Если время вообще не парсится, используем только дату
                                    pass
                    except ValueError:
                        # Если дата тоже не парсится, используем текущее время
                        export_datetime = datetime.now()

                export_datetime = self.moscow_tz.localize(export_datetime)

                now = datetime.now(self.moscow_tz)
                time_diff = now - export_datetime

                if time_diff < timedelta(hours=1):
                    status_icon = "✅"
                    status_text = "Актуально"
                elif time_diff < timedelta(hours=24):
                    status_icon = "⚠️"
                    status_text = "Сегодня"
                else:
                    status_icon = "🔴"
                    status_text = "Устарело"

                last_update = export_datetime.strftime('%d.%m.%Y %H:%M')
                time_ago = self._format_time_ago(time_diff)

                return {
                    'loaded': True,
                    'status': f"{status_icon} {status_text}",
                    'last_update': last_update,
                    'time_ago': time_ago,
                    'export_datetime': export_datetime,
                    'details': f"Обновлено {time_ago} назад ({last_update})"
                }

        except Exception as e:
            logger.warning(f"Error parsing date for school {school_id}: {e}; "
                           f"export_date={export_date!r}, export_time={export_time!r}")

        # Если не удалось распарсить дату, показываем сырые данные
        return {
            'loaded': True,
            'status': "⚠️ Неизвестно",
            'last_update': f"{export_date} {export_time}",
            'details': f'Данные от {export_date} {export_time}'
        }

    def get_all_statuses(self) -> dict:
        """Получает статусы всех школ"""
        statuses = {}
        for school_id in self.schools_data.keys():
            statuses[school_id] = self.get_school_status(school_id)
        return statuses

    def is_school_data_loaded(self, school_id: str) -> bool:
        """Проверяет, загружены ли данные школы"""
        return school_id in self.schools_data and bool(self.schools_data[school_id])

    def get_last_update_time(self, school_id: str) -> datetime | None:
        """Получает время последнего обновления"""
        status = self.get_school_status(school_id)
        return status.get('export_datetime')

    def _format_time_ago(self, time_diff: timedelta) -> str:
        """Форматирует разницу во времени (делегирует общий хелпер)"""
        from services.base_schedule_service import format_time_ago
        return format_time_ago(time_diff)
