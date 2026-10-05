// frontend/src/lib/schedule-view.ts
//
// Pure presentation helpers for the W20 schedule screens. Kept framework-free so
// they can be unit-tested directly and reused by several components.

import type { DaySchedule, Lesson, LessonItem, PeriodInfo, ScheduleKind } from './api/types';

/** Human-readable Russian labels for the schedule entity kinds. */
export const KIND_LABELS: Record<ScheduleKind, string> = {
  class: 'Класс',
  teacher: 'Учитель',
  room: 'Кабинет',
};

/**
 * Highest supported lesson number. Mirrors the server's `LESSONSINDAY`
 * default (12) and the API's `free-rooms` `lesson` range (1..12).
 */
export const LESSONS_PER_DAY = 12;

/** Lesson numbers `1..{@link LESSONS_PER_DAY}`, for inline selectors. */
export function lessonNumbers(max: number = LESSONS_PER_DAY): number[] {
  return Array.from({ length: max }, (_, index) => index + 1);
}

/** Plural form of the entity name used in a heading, e.g. «Класс 5А». */
export function entityHeading(kind: ScheduleKind, name: string): string {
  return `${KIND_LABELS[kind]} ${name}`;
}

/**
 * Classify a day payload into the state the UI must show. `lessons` is only
 * meaningful for `'lessons'`; the other states carry no timetable.
 */
export type DayState = 'lessons' | 'vacation' | 'weekend' | 'no_period' | 'empty';

/** Pick the visual state of a day from its payload flags (order matters). */
export function dayState(day: DaySchedule): DayState {
  if (day.vacation) {
    return 'vacation';
  }
  if (day.weekend) {
    return 'weekend';
  }
  if (day.no_period) {
    return 'no_period';
  }
  if (day.lessons.length === 0) {
    return 'empty';
  }
  return 'lessons';
}

/** True when a lesson should be visually marked as a substitution. */
export function isExchange(lesson: Lesson): boolean {
  return lesson.has_exchange;
}

/** True when a lesson should be visually marked as cancelled. */
export function isCancelled(lesson: Lesson): boolean {
  return lesson.is_cancelled;
}

/**
 * True when a lesson is a "free" slot (window) that the original site strikes
 * through (`STRIKEOUT_FREE_LSN`).
 *
 * The public API does not expose that flag (W32 `features` only covers
 * teachers/classrooms/rooms/homepage), so it is inferred from the lesson
 * payload: a lesson with no items, or whose items all lack a subject. Cancelled
 * lessons keep their own styling and are not treated as free.
 */
export function isFreeLesson(lesson: Lesson): boolean {
  if (lesson.is_cancelled) {
    return false;
  }
  if (lesson.items.length === 0) {
    return true;
  }
  return lesson.items.every((item) => !item.subject?.trim());
}

/**
 * Label for a lesson item's subject. Method hours (`is_method_hour`) are shown
 * as «Метод. час» rather than the raw `M` code; a missing subject becomes `—`.
 */
export function itemSubjectLabel(item: LessonItem): string {
  if (item.is_method_hour) {
    return 'Метод. час';
  }
  return item.subject?.trim() ? item.subject : '—';
}

/**
 * Label for the teaching period, e.g. «На период: 01.09.2026 - 31.05.2027».
 *
 * Prefers the server's `name`; falls back to the `b`–`e` bounds, then to a bare
 * «На период». Returns `null` when the day carries no period.
 */
export function periodLabel(period: PeriodInfo | null | undefined): string | null {
  if (!period) {
    return null;
  }
  const name = period.name?.trim();
  if (name) {
    return `На период: ${name}`;
  }
  const b = period.b?.trim();
  const e = period.e?.trim();
  if (b && e) {
    return `На период: ${b} – ${e}`;
  }
  return 'На период';
}

/** True when `shift` marks a non-first (second) shift. The server sends `> 1`. */
export function isSecondShift(shift: number | null | undefined): boolean {
  return typeof shift === 'number' && shift > 1;
}

/**
 * Label for the shift indicator, e.g. «Смена 2». The number is not assumed to
 * be `2` — real exports can use other values (e.g. `6`). `null` for the first
 * shift or when the server omits the shift.
 */
export function shiftLabel(shift: number | null | undefined): string | null {
  return isSecondShift(shift) ? `Смена ${shift}` : null;
}

/** `start–end` (en dash), falling back gracefully when a time is missing. */
export function lessonTime(lesson: Lesson): string {
  const start = lesson.start && lesson.start !== '?' ? lesson.start : '';
  const end = lesson.end && lesson.end !== '?' ? lesson.end : '';
  if (start && end) {
    return `${start}–${end}`;
  }
  return start || end || '';
}

/**
 * Accessibility label describing a lesson's status, used as `aria-label` /
 * visually-hidden text so status is not conveyed by colour alone.
 */
export function lessonStatusLabel(lesson: Lesson): string {
  if (isCancelled(lesson)) {
    return 'Отменён';
  }
  if (isExchange(lesson)) {
    return 'Замена';
  }
  return '';
}

/** Title-case-ish weekday display: the server sends a `day_name` string. */
export function dayTitle(day: DaySchedule): string {
  return day.day_name ? `${day.day_name}, ${day.date}` : day.date;
}
