// frontend/src/lib/schedule-view.ts
//
// Pure presentation helpers for the W20 schedule screens. Kept framework-free so
// they can be unit-tested directly and reused by several components.

import type {
  DaySchedule,
  Lesson,
  LessonExchange,
  LessonItem,
  PeriodInfo,
  ScheduleKind,
} from './api/types';

/** Human-readable Russian labels for the schedule entity kinds. */
export const KIND_LABELS: Record<ScheduleKind, string> = {
  class: 'Класс',
  teacher: 'Учитель',
  room: 'Кабинет',
};

/**
 * Plural labels for the schedule entity kinds — used by the global kind tab
 * bar and the per-kind list headings («Классы» / «Учителя» / «Кабинеты»).
 */
export const KIND_PLURAL_LABELS: Record<ScheduleKind, string> = {
  class: 'Классы',
  teacher: 'Учителя',
  room: 'Кабинеты',
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
 * Free-ness is inferred from the lesson payload: a lesson with no items, or
 * whose items all lack a subject. Cancelled lessons keep their own styling and
 * are not treated as free.
 *
 * W41: the school feature flag `strikeout_free_lsn` gates the strike-through
 * (default `true` when absent). When it is `false`, no lesson is marked free.
 */
export function isFreeLesson(lesson: Lesson, strikeoutFreeLsn = true): boolean {
  if (!strikeoutFreeLsn) {
    return false;
  }
  if (lesson.is_cancelled) {
    return false;
  }
  if (lesson.items.length === 0) {
    return true;
  }
  return lesson.items.every((item) => !item.subject?.trim());
}

/**
 * W41 fix — whether a lesson row must be **hidden** (not rendered) when the
 * school's `STRIKEOUT_FREE_LSN` flag is `false`.
 *
 * The original site hides cancelled/free lessons entirely when the flag is off
 * (the server formatter skips them: `services/base_schedule_service.py`). In
 * this codebase the real "free" lesson is `s:'F'` → `is_cancelled` (it keeps its
 * original subject); subject-less items are the degenerate case. When the flag
 * is `true` (the default) nothing is hidden — the existing strike-through
 * behavior is kept.
 */
export function isHiddenFreeLesson(lesson: Lesson, strikeoutFreeLsn = true): boolean {
  if (strikeoutFreeLsn) {
    return false;
  }
  return lesson.is_cancelled || isFreeLesson(lesson, true);
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

/**
 * One row of the «было → стало» diff shown in the exchange popover.
 *
 * `from`/`to` are display-ready; an unknown side is the em dash «—» so the row
 * still communicates that a change happened (the backend sends `null` rather
 * than fabricating a value).
 */
export interface ExchangeDiffLine {
  /** Field caption, e.g. «Предмет». */
  label: string;
  /** «Было» value, or «—» when unknown. */
  from: string;
  /** «Стало» value, or «—» when unknown. */
  to: string;
}

/** The exchange diff fields, in display order, with their «было»/«стало» keys. */
type ExchangeStringField =
  | 'original_subject'
  | 'original_teacher'
  | 'original_room'
  | 'new_subject'
  | 'new_teacher'
  | 'new_room';

const EXCHANGE_FIELDS: ReadonlyArray<readonly [string, ExchangeStringField, ExchangeStringField]> =
  [
    ['Предмет', 'original_subject', 'new_subject'],
    ['Учитель', 'original_teacher', 'new_teacher'],
    ['Кабинет', 'original_room', 'new_room'],
  ];

/**
 * Build the «было → стало» rows for a lesson's {@link LessonExchange}.
 *
 * A field is omitted when it did not change (partial exchanges keep the
 * unchanged side on both ends). Cancelled lessons have no "new" side, so they
 * yield no rows — the caller shows a single cancellation note instead. Never
 * throws; an unknown (`null`) side becomes «—».
 */
export function exchangeDiffLines(exchange: LessonExchange): ExchangeDiffLine[] {
  if (exchange.is_cancelled) {
    return [];
  }
  const lines: ExchangeDiffLine[] = [];
  for (const [label, fromKey, toKey] of EXCHANGE_FIELDS) {
    const from = exchange[fromKey];
    const to = exchange[toKey];
    if (from === to || (from == null && to == null)) {
      continue;
    }
    lines.push({ label, from: from ?? '—', to: to ?? '—' });
  }
  return lines;
}

/** Title-case-ish weekday display: the server sends a `day_name` string. */
export function dayTitle(day: DaySchedule): string {
  return day.day_name ? `${day.day_name}, ${day.date}` : day.date;
}

/**
 * A current-time hint for the «Сейчас / далее» layout: the lesson numbers the
 * server reports as running (`current`) and upcoming (`next`). Both may be
 * `null` when no server clock is available — the layout then degrades to
 * showing the first lesson as the hero.
 */
export interface NowHint {
  current: number | null;
  next: number | null;
}

/** Result of {@link pickNowNext}: the hero lesson plus the remaining list. */
export interface NowNextPick<T> {
  /** The lesson to feature (current, else next, else the first), or `null`. */
  hero: T | null;
  /** The other lessons, in their original order. */
  rest: T[];
  /** True when {@link hero} is the running lesson (eyebrow «Сейчас»). */
  heroIsCurrent: boolean;
}

/**
 * Split a day's lessons for the «Сейчас / далее» layout. Uses the server's
 * `current`/`next` hint when it matches a lesson number; otherwise falls back
 * to the first lesson. Never throws — an empty day yields `hero: null`.
 */
export function pickNowNext<T extends { num: number }>(
  lessons: readonly T[],
  now?: NowHint | null,
): NowNextPick<T> {
  if (lessons.length === 0) {
    return { hero: null, rest: [], heroIsCurrent: false };
  }
  const current = now?.current ?? null;
  const next = now?.next ?? null;
  let index = 0;
  let heroIsCurrent = false;
  if (current !== null) {
    const found = lessons.findIndex((lesson) => lesson.num === current);
    if (found >= 0) {
      index = found;
      heroIsCurrent = true;
    }
  }
  if (!heroIsCurrent && next !== null) {
    const found = lessons.findIndex((lesson) => lesson.num === next);
    if (found >= 0) {
      index = found;
    }
  }
  const hero = lessons[index];
  return {
    hero,
    rest: lessons.filter((_, i) => i !== index),
    heroIsCurrent,
  };
}
