# services/reminder_service.py
"""Напоминания о начале уроков.

Сервис чистый: по данным школ и карте «пользователь → (школа, класс)»
вычисляет, у каких пользователей урок начнётся в ближайшее окно, и
возвращает готовые тексты напоминаний. Отправкой занимается фоновый цикл
(`BackgroundUpdater._reminder_loop`).
"""
from datetime import datetime, timedelta

from services.base_schedule_service import find_class_id
from services.schedule_service import ScheduleService


class ReminderService:
    """Вычисляет напоминания об уроках, начинающихся в заданном окне."""

    @staticmethod
    def to_user_classes(users: list[dict]) -> dict:
        """Строит карту `user_id -> (school_id, class_name)` из записей users.

        У пользователя может быть несколько школ. Напоминание — один target на
        пользователя, поэтому остаётся класс последней школы в порядке обхода
        `school_classes` (обычно это текущая/последняя выбранная школа).
        Пользователи без user_id или без классов пропускаются.
        """
        mapping: dict[int, tuple[str, str]] = {}
        for user in users:
            user_id = user.get('user_id')
            if not user_id:
                continue
            for school_id, class_name in (user.get('school_classes') or {}).items():
                if class_name:
                    mapping[user_id] = (school_id, class_name)
        return mapping

    def get_due_reminders(
        self,
        schools_data: dict,
        user_classes: dict,
        now: datetime,
        window_minutes: int = 10,
    ) -> list[tuple[int, str]]:
        """Возвращает список `(user_id, text)` для уроков в окне напоминания.

        Args:
            schools_data: `{school_id: school_data}` — данные школ.
            user_classes: `{user_id: (school_id, class_name)}` — карта, какой
                класс выбрал пользователь в какой школе.
            now: текущее время (с таймзоной).
            window_minutes: на сколько минут вперёд смотреть.

        Каждый текст начинается со слова «через». Пользователи без данных
        школы/класса или без подходящего урока пропускаются.
        """
        return [
            (user_id, text)
            for user_id, text, _key in self.get_due_reminders_detailed(
                schools_data, user_classes, now, window_minutes
            )
        ]

    def get_due_reminders_detailed(
        self,
        schools_data: dict,
        user_classes: dict,
        now: datetime,
        window_minutes: int = 10,
    ) -> list[tuple[int, str, str]]:
        """Как `get_due_reminders`, но добавляет стабильный ключ дедупликации.

        Ключ имеет вид `user:school:class:ГГГГММДД:номер_урока` и не зависит
        от текста (число минут в тексте меняется каждую минуту). `user_id`
        входит в ключ, чтобы напоминания разных пользователей одного класса
        не «съедали» друг друга при дедупликации.
        """
        reminders: list[tuple[int, str, str]] = []
        if not schools_data or not user_classes or now is None:
            return reminders

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

            day_num = now.isoweekday()
            if day_num > 5:
                continue

            class_key = (school_id, class_name)
            schedule = lessons_by_class.get(class_key)
            if schedule is None:
                class_id = find_class_id(school_data, class_name)
                if not class_id:
                    lessons_by_class[class_key] = []
                    continue
                period_id = svc._get_period_for_date(now)
                if not period_id:
                    lessons_by_class[class_key] = []
                    continue
                schedule = svc._get_schedule_data(period_id, class_id, day_num)
                lessons_by_class[class_key] = schedule

            due = self._next_lesson_reminder(school_data, schedule, now, window_minutes)
            if due:
                text, lesson_num = due
                key = f"{user_id}:{school_id}:{class_name}:{now.strftime('%Y%m%d')}:{lesson_num}"
                reminders.append((user_id, text, key))

        return reminders

    def _next_lesson_reminder(
        self,
        school_data: dict,
        schedule: list[dict],
        now: datetime,
        window_minutes: int,
    ) -> tuple[str, int] | None:
        """Текст напоминания и номер урока о ближайшем уроке в окне или None."""
        lesson_times = school_data.get('LESSON_TIMES', {})
        subjects = school_data.get('SUBJECTS', {})
        window = timedelta(minutes=window_minutes)

        for lesson in sorted(schedule, key=lambda item: item['lesson_num']):
            lesson_num = lesson['lesson_num']
            times = lesson_times.get(str(lesson_num))
            if not times or len(times) < 2 or times[0] == '?':
                continue
            try:
                start = now.replace(
                    hour=int(times[0][:2]),
                    minute=int(times[0][3:5]),
                    second=0,
                    microsecond=0,
                )
            except (ValueError, IndexError):
                continue

            delta = start - now
            if delta < timedelta(0) or delta > window:
                continue

            minutes = int(delta.total_seconds() // 60)
            subject_names = [
                subjects.get(subject_id, '')
                for subject_id in lesson.get('data', {}).get('s', [])
            ]
            subject = ', '.join(name for name in subject_names if name) or 'урок'
            text = (
                f"через {minutes} мин начнётся урок {lesson_num} "
                f"в {times[0]} — {subject}"
            )
            return text, lesson_num

        return None
