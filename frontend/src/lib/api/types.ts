// frontend/src/lib/api/types.ts
//
// Response types for the public schedule API (see `web/api.py` and
// `docs/superpowers/specs/2026-09-24-public-schedule-site-design.md` §5).
//
// IMPORTANT: field names follow the *actual* server payloads, not the brief's
// shorthand. Endpoints wrap their lists in an object:
//   GET /api/{school}/classes  -> { classes: string[] }
//   GET /api/{school}/teachers -> { teachers: string[] }
//   GET /api/{school}/rooms    -> { rooms: string[] }
//   GET /api/{school}/search   -> { teachers, rooms }  (classes arrive in W32)
//   GET /api/{school}/free-rooms -> { free_rooms: string[] }

/** Schedule entity kind as used in URL paths: `class` | `teacher` | `room`. */
export type ScheduleKind = 'class' | 'teacher' | 'room';

/**
 * A school as returned by `GET /api/schools`.
 *
 * W19 ships only `id`/`name`/`loaded`. W32 adds `city`, `updated`,
 * `homepage_url` and `features`; those are declared optional here so the type
 * can absorb them without a breaking change.
 */
export interface School {
  id: string;
  name: string;
  /** Whether the edge/origin has schedule data loaded for this school. */
  loaded: boolean;
  /** W32+ — city name. */
  city?: string;
  /** W32+ — human-readable "updated" timestamp (EXPORT_DATE + EXPORT_TIME). */
  updated?: string;
  /** W32+ — school homepage URL. */
  homepage_url?: string;
  /** W32+ — feature flags gating UI (teachers/classrooms/rooms/homepage). */
  features?: SchoolFeatures;
}

/** W32+ feature flags for a school. */
export interface SchoolFeatures {
  teachers?: boolean;
  classrooms?: boolean;
  rooms?: boolean;
  homepage?: boolean;
}

/** Response of `GET /api/schools`. `today` is the server's date in DD.MM.YYYY. */
export interface SchoolsResponse {
  /** Authoritative server "today" as `DD.MM.YYYY` (school timezone). */
  today: string;
  schools: School[];
}

/** A single lesson item (one group/parallel row) inside a lesson. */
export interface LessonItem {
  subject: string | null;
  teacher: string | null;
  room: string | null;
  class_name: string | null;
}

/** One lesson entry in a day payload. */
export interface Lesson {
  num: number;
  /** Lesson start time `HH:MM`, or `?` when unknown. */
  start: string;
  /** Lesson end time `HH:MM`, or `?` when unknown. */
  end: string;
  items: LessonItem[];
  has_exchange: boolean;
  is_cancelled: boolean;
}

/**
 * Day payload returned by `GET /api/{school}/schedule/{kind}/{name}` and as
 * each element of the `/week` response's `days` array.
 */
export interface DaySchedule {
  /** Date as `DD.MM.YYYY`. */
  date: string;
  day_name: string;
  kind: ScheduleKind;
  entity: string;
  lessons: Lesson[];
  /** Holiday/university break — no lessons. */
  vacation: boolean;
  /** Weekend — no lessons. */
  weekend: boolean;
  /** Date falls outside a configured teaching period (week endpoint only). */
  no_period: boolean;
}

/** Response of `GET /api/{school}/schedule/{kind}/{name}/week`. */
export interface WeekScheduleResponse {
  days: DaySchedule[];
}

/**
 * One calendar day of the month (`GET .../calendar`).
 *
 * Same shape as {@link DaySchedule} but flattened: the server only needs the
 * markers, not the full lesson list. `has_exchange`/`has_cancelled` are `true`
 * when at least one lesson carries the flag; `lesson_count` is the number of
 * lessons on that day (0 on weekends/holidays/out-of-period days).
 */
export interface CalendarDay {
  /** Date as `DD.MM.YYYY`. */
  date: string;
  day_name: string;
  weekend: boolean;
  vacation: boolean;
  /** Date falls outside a configured teaching period. */
  no_period: boolean;
  /** At least one lesson is a substitution. */
  has_exchange: boolean;
  /** At least one lesson is cancelled. */
  has_cancelled: boolean;
  lesson_count: number;
}

/** Response of `GET /api/{school}/schedule/{kind}/{name}/calendar`. */
export interface CalendarResponse {
  days: CalendarDay[];
}

/** Response of `GET /api/{school}/classes`. */
export interface ClassesResponse {
  classes: string[];
}

/** Response of `GET /api/{school}/teachers`. */
export interface TeachersResponse {
  teachers: string[];
}

/** Response of `GET /api/{school}/rooms`. */
export interface RoomsResponse {
  rooms: string[];
}

/**
 * Response of `GET /api/{school}/search`.
 *
 * W19's server only returns `teachers` and `rooms`; the spec (§5.1) says search
 * will also return `classes` in W32, hence the optional field.
 */
export interface SearchResponse {
  teachers: string[];
  rooms: string[];
  /** W32+ — matching classes. */
  classes?: string[];
}

/** Response of `GET /api/{school}/free-rooms`. */
export interface FreeRoomsResponse {
  free_rooms: string[];
}

/** HTTP status carried by an {@link ApiError}. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}
