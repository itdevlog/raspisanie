import { describe, it, expect } from 'vitest';
import { parseRuDate, formatRuDate, addDays, serverDateRef } from './dates';

describe('date helpers', () => {
  it('parses valid DD.MM.YYYY dates', () => {
    expect(parseRuDate('05.10.2026')).toEqual({ year: 2026, month: 10, day: 5 });
  });

  it('rejects malformed or impossible dates', () => {
    expect(parseRuDate('')).toBeNull();
    expect(parseRuDate('2026-10-05')).toBeNull();
    expect(parseRuDate('31.02.2026')).toBeNull();
    expect(parseRuDate('00.10.2026')).toBeNull();
  });

  it('formats with zero padding', () => {
    expect(formatRuDate(2026, 10, 5)).toBe('05.10.2026');
  });

  it('adds and subtracts whole days across month/year boundaries', () => {
    expect(addDays('05.10.2026', 1)).toBe('06.10.2026');
    expect(addDays('31.12.2026', 1)).toBe('01.01.2027');
    expect(addDays('01.01.2027', -1)).toBe('31.12.2026');
    expect(addDays('28.02.2028', 1)).toBe('29.02.2028'); // leap year
    expect(addDays('nope', 1)).toBeNull();
  });

  it('derives tomorrow/yesterday from the provided server today', () => {
    expect(serverDateRef('05.10.2026')).toEqual({
      today: '05.10.2026',
      tomorrow: '06.10.2026',
      yesterday: '04.10.2026',
    });
  });
});
