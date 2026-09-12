# services/digest_service.py
"""Утренний дайджест: расписание на день перед первым уроком.

Сервис чистый: по данным школ и карте «пользователь → (школа, класс)»
вычисляет, у кого первый урок дня начинается в окне «за N минут», и
возвращает готовые тексты. Отправкой занимается фоновый цикл
(`BackgroundUpdater._send_digests`).

Привязка к первому уроку (а не к фиксированному часу) автоматически
учитывает две смены: у первой смены дайджест утром, у второй — днём.
В дни без уроков (выходные, каникулы, праздники) дайджест не приходит.
"""
from datetime import datetime, timedelta

from services.base_schedule_service import find_class_id
from services.schedule_service import ScheduleService

# За сколько минут до первого урока отправлять дайджест.
DIGEST_OFFSET_MINUTES = 60
# Окно догона: цикл тикает раз в минуту, после рестарта/паузы догоняем.
DIGEST_WINDOW_MINUTES = 15


class DigestService:
    """Вычисляет дайджесты для уроков, начинающихся в заданном окне."""

    def get_due_digests(
        self,
        schools_data: dict,
        user_classes: dict,
        now: datetime,
        offset_minutes: int = DIGEST_OFFSET_MINUTES,
        window_minutes: int = DIGEST_WINDOW_MINUTES,
    ) -> list[tuple[int, str, str]]:
        """Возвращает `(user_id, text, dedup_key)` для попавших в окно дайджестов.

        `user_classes` — карта `user_id -> (school_id, class_name)` (см.
        `ReminderService.to_user_classes`). Дедуп-ключ не зависит от текста:
        `digest:{user_id}:{school}:{class}:{ГГГГММДД}` — один дайджест в день,
        переживает рестарт.
        """
        digests: list[tuple[int, str, str]] = []
        if not schools_data or not user_classes or now is None:
            return digests

        period_cache: dict[str, ScheduleService] = {}
        lessons_by_class: dict[tuple[str, str], list[dict]] = {}

        for user_id, target in user_classes.items():
            if not target:
                continue
            school_id, class_name = target
            school_data = schools_data.get(school_id)
            if not school_data or not class_name:
                continue

            svc = period_cache.get(school_id)
            if svc is None:
                svc = ScheduleService(school_data, school_id=school_id)
                period_cache[school_id] = svc

            if now.isoweekday() > 5:
                continue

            class_key = (school_id, class_name)
            schedule = lessons_by_class.get(class_key)
            if schedule is None:
                class_id = find_class_id(school_data, class_name)
                period_id = svc._get_period_for_date(now) if class_id else None
                if not class_id or not period_id:
                    lessons_by_class[class_key] = []
                    continue
                schedule = svc._get_schedule_data(period_id, class_id, now.isoweekday())
                schedule = svc.exchange_service.apply_exchanges_to_schedule(
                    class_name, schedule, now)
                lessons_by_class[class_key] = schedule

            first_start = self._first_lesson_start(school_data, schedule, now)
            if not first_start:
                continue

            trigger = first_start - timedelta(minutes=offset_minutes)
            if not (trigger <= now <= trigger + timedelta(minutes=window_minutes)):
                continue

            text = self._format_digest(svc, class_name, schedule, now)
            key = f"digest:{user_id}:{school_id}:{class_name}:{now.strftime('%Y%m%d')}"
            digests.append((user_id, text, key))

        return digests

    @staticmethod
    def _first_lesson_start(school_data: dict, schedule: list[dict],
                            now: datetime) -> datetime | None:
        """Время начала первого неотменённого урока дня или None."""
        lesson_times = school_data.get('LESSON_TIMES', {})
        for lesson in sorted(schedule, key=lambda item: item['lesson_num']):
            if lesson.get('is_cancelled'):
                continue
            times = lesson_times.get(str(lesson['lesson_num']))
            if not times or len(times) < 2 or times[0] == '?':
                continue
            try:
                return now.replace(
                    hour=int(times[0][:2]), minute=int(times[0][3:5]),
                    second=0, microsecond=0)
            except (ValueError, IndexError):
                continue
        return None

    @staticmethod
    def _format_digest(svc: ScheduleService, class_name: str,
                       schedule: list[dict], now: datetime) -> str:
        """Текст дайджеста: заголовок + расписание дня с заменами."""
        date_str = now.strftime('%d.%m.%Y')
        day_name = svc._get_day_name(now)
        safe_class = svc._escape_markdown(class_name)
        header = f"📋 *{safe_class} — на сегодня ({day_name}, {date_str})*\n\n"
        body = svc._format_schedule_response(
            'class', class_name, now, schedule, include_header=False)
        return header + body
