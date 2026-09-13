# services/schedule_exceptions.py
"""Исключения структурного слоя расписаний (для API)."""


class EntityNotFoundError(Exception):
    """Сущность (класс/учитель/кабинет) не найдена."""

    def __init__(self, entity_type: str, name: str, message: str):
        super().__init__(message)
        self.entity_type = entity_type
        self.name = name
        self.message = message


class PeriodNotFoundError(Exception):
    """Не удалось определить учебный период для даты."""

    def __init__(self, message: str = "❌ Не удалось определить учебный период"):
        super().__init__(message)
        self.message = message
