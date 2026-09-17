# services/school_types.py
"""Типизация структуры `school_data` (данные Nikasoft).

`SchoolData` описывает словарь школы, который грузит `DataLoader` и
передают по кругу сервисы расписания. Поля `total=False` — реальные
выгрузки содержат не все ключи, а потребители уже используют `.get(..., {})`.
Тип применяется на границах чтения/передачи, чтобы задокументировать
основные ключи, не переписывая внутреннюю логику.
"""
from __future__ import annotations

from typing import TypedDict


class PeriodInfo(TypedDict, total=False):
    """Учебный период: `b`/`e` — даты начала/конца в формате `дд.мм.гггг`."""

    b: str
    e: str


class LessonData(TypedDict, total=False):
    """Коды предмета/учителя/кабинета урока (могут быть строкой или списком)."""

    s: list[str] | str
    t: list[str] | str
    r: list[str] | str


class ExchangeData(TypedDict, total=False):
    """Замена урока из CLASS_EXCHANGE/TEACH_EXCHANGE.

    `s` == 'F' означает отмену; `s`/`t`/`r` — новые коды/имена.
    """

    s: list[str] | str
    t: list[str] | str
    r: list[str] | str


class HolidayInfo(TypedDict, total=False):
    """Перенос/каникулы (HOLIDAY_TRANSFER), ключ — дата `дд.мм.гггг`."""

    type: str
    daynum: int | str
    weeknum: int | str
    period: str


class SchoolData(TypedDict, total=False):
    """Данные одной школы: справочники, периоды, расписания и замены."""

    SCHOOL_NAME: str
    CITY_NAME: str
    EXPORT_DATE: str
    EXPORT_TIME: str
    HOMEPAGE_URL: str
    LESSONSINDAY: int
    STRIKEOUT_FREE_LSN: bool
    DAY_NAMES: list[str]
    CLASSES: dict[str, str]
    TEACHERS: dict[str, str]
    ROOMS: dict[str, str]
    SUBJECTS: dict[str, str]
    PERIODS: dict[str, PeriodInfo]
    LESSON_TIMES: dict[str, list[str]]
    # period_id -> class_id -> "day*100 + lesson" -> LessonData
    CLASS_SCHEDULE: dict[str, dict[str, dict[str, LessonData]]]
    # class_id -> date_str -> lesson_num -> ExchangeData
    CLASS_EXCHANGE: dict[str, dict[str, dict[str, ExchangeData]]]
    # teacher_id -> date_str -> lesson_num -> ExchangeData
    TEACH_EXCHANGE: dict[str, dict[str, dict[str, ExchangeData]]]
    HOLIDAY_TRANSFER: dict[str, HolidayInfo]
