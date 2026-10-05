import { describe, it, expect } from 'vitest';
import type { Lesson, LessonItem } from './api/types';
import {
  dayState,
  dayTitle,
  entityHeading,
  isCancelled,
  isExchange,
  isFreeLesson,
  isHiddenFreeLesson,
  isSecondShift,
  itemSubjectLabel,
  KIND_LABELS,
  LESSONS_PER_DAY,
  lessonNumbers,
  lessonStatusLabel,
  lessonTime,
  periodLabel,
  shiftLabel,
} from './schedule-view';
import { makeDay } from '../test-helpers';

function makeLesson(overrides: Partial<Lesson> = {}): Lesson {
  return {
    num: 1,
    start: '08:00',
    end: '08:45',
    items: [
      {
        subject: 'Математика',
        teacher: 'Иванов',
        room: '101',
        class_name: '5А',
        groups: null,
        is_method_hour: false,
      },
    ],
    has_exchange: false,
    is_cancelled: false,
    ...overrides,
  };
}

function makeItem(overrides: Partial<LessonItem> = {}): LessonItem {
  return {
    subject: 'Математика',
    teacher: 'Иванов',
    room: '101',
    class_name: '5А',
    groups: null,
    is_method_hour: false,
    ...overrides,
  };
}

describe('schedule-view helpers', () => {
  it('labels every entity kind', () => {
    expect(KIND_LABELS.class).toBe('Класс');
    expect(KIND_LABELS.teacher).toBe('Учитель');
    expect(KIND_LABELS.room).toBe('Кабинет');
    expect(entityHeading('room', '101')).toBe('Кабинет 101');
  });

  it('classifies day state with vacation/weekend/no_period precedence', () => {
    expect(dayState(makeDay({ lessons: [makeLesson()] }))).toBe('lessons');
    expect(dayState(makeDay())).toBe('empty');
    expect(dayState(makeDay({ no_period: true }))).toBe('no_period');
    expect(dayState(makeDay({ weekend: true }))).toBe('weekend');
    expect(dayState(makeDay({ vacation: true }))).toBe('vacation');
    // vacation wins even if weekend is also set.
    expect(dayState(makeDay({ vacation: true, weekend: true }))).toBe('vacation');
  });

  it('detects exchange/cancelled lessons', () => {
    expect(isExchange(makeLesson({ has_exchange: true }))).toBe(true);
    expect(isExchange(makeLesson())).toBe(false);
    expect(isCancelled(makeLesson({ is_cancelled: true }))).toBe(true);
    expect(isCancelled(makeLesson())).toBe(false);
  });

  it('formats times and omits unknown placeholders', () => {
    expect(lessonTime(makeLesson())).toBe('08:00–08:45');
    expect(lessonTime(makeLesson({ start: '?', end: '?' }))).toBe('');
    expect(lessonTime(makeLesson({ end: '?' }))).toBe('08:00');
  });

  it('prioritises cancellation over exchange in the status label', () => {
    expect(lessonStatusLabel(makeLesson({ is_cancelled: true, has_exchange: true }))).toBe(
      'Отменён',
    );
    expect(lessonStatusLabel(makeLesson({ has_exchange: true }))).toBe('Замена');
    expect(lessonStatusLabel(makeLesson())).toBe('');
  });

  it('builds a day title', () => {
    expect(dayTitle(makeDay())).toBe('Понедельник, 05.10.2026');
  });

  it('returns the date alone when the server omits day_name', () => {
    expect(dayTitle(makeDay({ day_name: '' }))).toBe('05.10.2026');
  });

  it('lists lesson numbers 1..LESSONS_PER_DAY by default', () => {
    const numbers = lessonNumbers();
    expect(LESSONS_PER_DAY).toBe(12);
    expect(numbers).toHaveLength(LESSONS_PER_DAY);
    expect(numbers[0]).toBe(1);
    expect(numbers[numbers.length - 1]).toBe(12);
    // Contiguous 1..12, no gaps or duplicates.
    expect(numbers).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
  });

  it('honours an explicit lessonNumbers max', () => {
    expect(lessonNumbers(3)).toEqual([1, 2, 3]);
    expect(lessonNumbers(0)).toEqual([]);
  });

  it('labels the teaching period from name, bounds, or bare', () => {
    expect(periodLabel({ b: '01.09.2026', e: '31.05.2027', name: '01.09.2026 - 31.05.2027' })).toBe(
      'На период: 01.09.2026 - 31.05.2027',
    );
    expect(periodLabel({ b: '01.09.2026', e: '31.05.2027', name: null })).toBe(
      'На период: 01.09.2026 – 31.05.2027',
    );
    expect(periodLabel({ b: null, e: null, name: null })).toBe('На период');
    expect(periodLabel(null)).toBeNull();
    expect(periodLabel(undefined)).toBeNull();
  });

  it('detects a non-first shift without assuming it is 2', () => {
    expect(isSecondShift(2)).toBe(true);
    expect(isSecondShift(6)).toBe(true);
    expect(isSecondShift(1)).toBe(false);
    expect(isSecondShift(null)).toBe(false);
    expect(isSecondShift(undefined)).toBe(false);
    expect(shiftLabel(2)).toBe('Смена 2');
    expect(shiftLabel(6)).toBe('Смена 6');
    expect(shiftLabel(1)).toBeNull();
    expect(shiftLabel(null)).toBeNull();
  });

  it('labels method hours and missing subjects', () => {
    expect(itemSubjectLabel(makeItem({ is_method_hour: true, subject: 'M' }))).toBe('Метод. час');
    expect(itemSubjectLabel(makeItem({ subject: 'Математика' }))).toBe('Математика');
    expect(itemSubjectLabel(makeItem({ subject: null }))).toBe('—');
    expect(itemSubjectLabel(makeItem({ subject: '  ' }))).toBe('—');
  });

  it('detects free (subject-less) lessons but not cancelled ones', () => {
    expect(isFreeLesson(makeLesson())).toBe(false);
    expect(isFreeLesson(makeLesson({ items: [] }))).toBe(true);
    expect(isFreeLesson(makeLesson({ items: [makeItem({ subject: null })] }))).toBe(true);
    // A cancelled lesson keeps its own styling, not the "free" one.
    expect(isFreeLesson(makeLesson({ is_cancelled: true, items: [] }))).toBe(false);
  });

  it('strikes free lessons when the flag is true or absent (default)', () => {
    const free = makeLesson({ items: [] });
    expect(isFreeLesson(free, true)).toBe(true);
    // Explicit `undefined` falls back to the default (enabled).
    expect(isFreeLesson(free, undefined)).toBe(true);
  });

  it('does not strike any lesson when strikeout_free_lsn is false', () => {
    const free = makeLesson({ items: [] });
    expect(isFreeLesson(free, false)).toBe(false);
    // Even a genuinely subject-less lesson is not marked free when gated off.
    expect(isFreeLesson(makeLesson({ items: [makeItem({ subject: null })] }), false)).toBe(false);
  });

  it('hides nothing while strikeout_free_lsn is true/absent (default)', () => {
    expect(isHiddenFreeLesson(makeLesson({ items: [] }), true)).toBe(false);
    expect(isHiddenFreeLesson(makeLesson({ items: [] }))).toBe(false);
    expect(isHiddenFreeLesson(makeLesson({ is_cancelled: true }), true)).toBe(false);
  });

  it('hides free and cancelled lessons when strikeout_free_lsn is false (W41 fix)', () => {
    // Subject-less (degenerate "free") row.
    expect(isHiddenFreeLesson(makeLesson({ items: [] }), false)).toBe(true);
    expect(isHiddenFreeLesson(makeLesson({ items: [makeItem({ subject: null })] }), false)).toBe(true);
    // The real "free" lesson in this codebase: `s:'F'` -> is_cancelled.
    expect(isHiddenFreeLesson(makeLesson({ is_cancelled: true }), false)).toBe(true);
    // A normal lesson is never hidden.
    expect(isHiddenFreeLesson(makeLesson(), false)).toBe(false);
  });
});
