import { describe, it, expect } from 'vitest';
import {
  calendarDayAriaLabel,
  dayNumber,
  mondayIndex,
  monthGrid,
  monthLabel,
  RU_MONTHS,
  shiftMonth,
} from './calendar';
import { formatRuDate } from './dates';
import { makeCalendarDay } from '../test-helpers';

describe('calendar helpers', () => {
  it('labels a month in Russian', () => {
    expect(RU_MONTHS).toHaveLength(12);
    expect(monthLabel(2026, 10)).toBe('Октябрь 2026');
    expect(monthLabel(2026, 1)).toBe('Январь 2026');
    expect(monthLabel(2026, 12)).toBe('Декабрь 2026');
  });

  it('shifts months across year boundaries', () => {
    expect(shiftMonth(2026, 1, -1)).toEqual({ year: 2025, month: 12 });
    expect(shiftMonth(2026, 12, 1)).toEqual({ year: 2027, month: 1 });
    expect(shiftMonth(2026, 10, 0)).toEqual({ year: 2026, month: 10 });
    expect(shiftMonth(2026, 10, 14)).toEqual({ year: 2027, month: 12 });
    expect(shiftMonth(2026, 1, -13)).toEqual({ year: 2024, month: 12 });
  });

  it('computes a Monday-first weekday index without the browser clock', () => {
    // 05.10.2026 is a Monday (the server day_name confirms it).
    expect(mondayIndex(2026, 10, 5)).toBe(0);
    expect(mondayIndex(2026, 10, 1)).toBe(3); // Thursday
    expect(mondayIndex(2026, 10, 4)).toBe(6); // Sunday
  });

  it('pads the month grid to Monday-first full weeks', () => {
    const days = Array.from({ length: 31 }, (_, i) =>
      makeCalendarDay({ date: formatRuDate(2026, 10, i + 1) }),
    );
    const cells = monthGrid(days, 2026, 10);

    // 1 Oct 2026 is a Thursday → 3 leading blanks; 3 + 31 = 34 → padded to 35.
    expect(cells).toHaveLength(35);
    expect(cells.slice(0, 3)).toEqual([null, null, null]);
    expect(cells[3]?.date).toBe('01.10.2026');
    expect(cells[33]?.date).toBe('31.10.2026');
    expect(cells[34]).toBeNull();
  });

  it('falls back to the requested month for an empty day list', () => {
    // With no days the grid can only anchor on the 1st; it still pads to a week.
    const cells = monthGrid([], 2026, 10);
    expect(cells).toHaveLength(7);
    expect(cells.every((cell) => cell === null)).toBe(true);
  });

  it('extracts the two-digit day of month', () => {
    expect(dayNumber('05.10.2026')).toBe('05');
    expect(dayNumber('31.12.2026')).toBe('31');
  });

  it('describes markers in the accessible label (not colour alone)', () => {
    expect(
      calendarDayAriaLabel(
        makeCalendarDay({ date: '05.10.2026', lesson_count: 6, has_exchange: true }),
      ),
    ).toBe('05.10.2026, Понедельник, уроков: 6, замена');
    expect(calendarDayAriaLabel(makeCalendarDay({ has_cancelled: true }))).toContain('отмена');
    expect(calendarDayAriaLabel(makeCalendarDay({ vacation: true }))).toContain('каникулы');
    expect(calendarDayAriaLabel(makeCalendarDay({ weekend: true }))).toContain('выходной');
    expect(calendarDayAriaLabel(makeCalendarDay({ no_period: true }))).toContain(
      'нет учебного периода',
    );
    expect(calendarDayAriaLabel(makeCalendarDay())).toContain('нет уроков');
  });
});
