import { describe, it, expect } from 'vitest';
import type { Lesson } from './api/types';
import {
  dayState,
  dayTitle,
  entityHeading,
  isCancelled,
  isExchange,
  KIND_LABELS,
  LESSONS_PER_DAY,
  lessonNumbers,
  lessonStatusLabel,
  lessonTime,
} from './schedule-view';
import { makeDay } from '../test-helpers';

function makeLesson(overrides: Partial<Lesson> = {}): Lesson {
  return {
    num: 1,
    start: '08:00',
    end: '08:45',
    items: [{ subject: 'Математика', teacher: 'Иванов', room: '101', class_name: '5А' }],
    has_exchange: false,
    is_cancelled: false,
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
});
