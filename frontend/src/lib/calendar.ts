// frontend/src/lib/calendar.ts
//
// Pure helpers for the W38 month calendar. Framework-free and clock-free: all
// date math uses explicit UTC components (like `dates.ts`), never `Date.now()`,
// so the grid never depends on the browser's timezone or "today".

import type { CalendarDay } from './api/types';
import { formatRuDate, parseRuDate } from './dates';

/** Russian month names, January first (nominative, title case). */
export const RU_MONTHS: readonly string[] = [
  'Январь',
  'Февраль',
  'Март',
  'Апрель',
  'Май',
  'Июнь',
  'Июль',
  'Август',
  'Сентябрь',
  'Октябрь',
  'Ноябрь',
  'Декабрь',
];

/** Russian weekday names, Monday first (nominative, title case). */
export const RU_WEEKDAYS: readonly string[] = [
  'Понедельник',
  'Вторник',
  'Среда',
  'Четверг',
  'Пятница',
  'Суббота',
  'Воскресенье',
];

/** «Октябрь 2026» for a 1-based month. */
export function monthLabel(year: number, month: number): string {
  return `${RU_MONTHS[month - 1]} ${year}`;
}

/** Shift a 1-based year/month by `delta` months, rolling the year over. */
export function shiftMonth(
  year: number,
  month: number,
  delta: number,
): { year: number; month: number } {
  const total = year * 12 + (month - 1) + delta;
  return {
    year: Math.floor(total / 12),
    month: (((total % 12) + 12) % 12) + 1,
  };
}

/** Monday-first weekday index (Mon=0 … Sun=6) for an explicit calendar date. */
export function mondayIndex(year: number, month: number, day: number): number {
  // `getUTCDay()` is Sun=0 … Sat=6; rotate so Monday is 0.
  const jsDay = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  return (jsDay + 6) % 7;
}

/**
 * Full Russian weekday name for a `DD.MM.YYYY` date, or `''` for invalid input.
 * Clock-free: derived from the explicit UTC calendar date.
 */
export function weekdayLabel(date: string): string {
  const parsed = parseRuDate(date);
  if (!parsed) {
    return '';
  }
  return RU_WEEKDAYS[mondayIndex(parsed.year, parsed.month, parsed.day)];
}

/** «05.10.2026, Понедельник» — the day-view cursor heading. */
export function dayHeading(date: string): string {
  const weekday = weekdayLabel(date);
  return weekday ? `${date}, ${weekday}` : date;
}

/**
 * Pad the server's day list into Monday-first weeks.
 *
 * Leading/trailing cells are `null` (blanks). The first day's weekday comes
 * from its own `date`, so the grid is correct even if the list were sparse;
 * `year`/`month` are only the fallback for an empty list.
 */
export function monthGrid(
  days: readonly CalendarDay[],
  year: number,
  month: number,
): (CalendarDay | null)[] {
  const firstDate = days[0]?.date ?? formatRuDate(year, month, 1);
  const first = parseRuDate(firstDate);
  const lead = first ? mondayIndex(first.year, first.month, first.day) : 0;

  const cells: (CalendarDay | null)[] = Array.from({ length: lead }, () => null);
  for (const day of days) {
    cells.push(day);
  }
  while (cells.length % 7 !== 0) {
    cells.push(null);
  }
  return cells;
}

/** Two-digit day-of-month from a `DD.MM.YYYY` string. */
export function dayNumber(date: string): string {
  return date.slice(0, 2);
}

/**
 * Accessible name for a calendar cell. Status is conveyed in text (not colour
 * alone) so assistive tech and the tests can read it.
 */
export function calendarDayAriaLabel(day: CalendarDay): string {
  const parts: string[] = [day.date];
  if (day.day_name) {
    parts.push(day.day_name);
  }
  if (day.vacation) {
    parts.push('каникулы');
  } else if (day.weekend) {
    parts.push('выходной');
  } else if (day.no_period) {
    parts.push('нет учебного периода');
  } else if (day.lesson_count > 0) {
    parts.push(`уроков: ${day.lesson_count}`);
  } else {
    parts.push('нет уроков');
  }
  if (day.has_exchange) {
    parts.push('замена');
  }
  if (day.has_cancelled) {
    parts.push('отмена');
  }
  return parts.join(', ');
}
