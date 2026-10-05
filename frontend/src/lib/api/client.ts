// frontend/src/lib/api/client.ts
//
// Typed, fetch-based client for the public read-only schedule API.
//
// The frontend is served by the edge at the same origin, so the base URL is
// left relative (`/api/...`) — no CORS, no hard-coded host. URL construction is
// split into pure `build*Url` helpers so it can be unit-tested without network.

import {
  ApiError,
  type CalendarResponse,
  type ClassesResponse,
  type DaySchedule,
  type FreeRoomsResponse,
  type NowResponse,
  type RoomsResponse,
  type ScheduleKind,
  type SchoolsResponse,
  type SearchResponse,
  type TeachersResponse,
  type WeekScheduleResponse,
} from './types';

/** Thrown by {@link buildFreeRoomsUrl} when the lesson number is out of range. */
export class InvalidLessonError extends RangeError {
  constructor(lesson: number) {
    super(`Номер урока должен быть от 1 до 12, получено: ${lesson}`);
    this.name = 'InvalidLessonError';
  }
}

/** Thrown by {@link buildWeekUrl} when the week offset is out of range. */
export class InvalidWeekOffsetError extends RangeError {
  constructor(offset: number) {
    super(`Смещение недели должно быть от -2 до 2, получено: ${offset}`);
    this.name = 'InvalidWeekOffsetError';
  }
}

/** Thrown by {@link buildCalendarUrl} when the year/month are out of range. */
export class InvalidCalendarRangeError extends RangeError {
  constructor(message: string) {
    super(message);
    this.name = 'InvalidCalendarRangeError';
  }
}

const LESSON_MIN = 1;
const LESSON_MAX = 12;
const WEEK_OFFSET_MIN = -2;
const WEEK_OFFSET_MAX = 2;
const CALENDAR_YEAR_MIN = 2020;

function encodePathSegment(value: string): string {
  return encodeURIComponent(value);
}

/** URL for `GET /api/schools`. */
export function buildSchoolsUrl(): string {
  return '/api/schools';
}

/** URL for `GET /api/{schoolId}/{resource}` where resource is a list endpoint. */
export function buildListUrl(schoolId: string, resource: 'classes' | 'teachers' | 'rooms'): string {
  return `/api/${encodePathSegment(schoolId)}/${resource}`;
}

/**
 * URL for `GET /api/{schoolId}/schedule/{kind}/{name}`.
 *
 * `date` is passed through verbatim as `DD.MM.YYYY` — never derived from the
 * browser clock. Omit it to let the server use its own "today".
 */
export function buildDayUrl(
  schoolId: string,
  kind: ScheduleKind,
  name: string,
  date?: string,
): string {
  const base = `/api/${encodePathSegment(schoolId)}/schedule/${encodePathSegment(kind)}/${encodePathSegment(name)}`;
  return date ? `${base}?${new URLSearchParams({ date }).toString()}` : base;
}

/** URL for `GET /api/{schoolId}/schedule/{kind}/{name}/week?offset=`. */
export function buildWeekUrl(
  schoolId: string,
  kind: ScheduleKind,
  name: string,
  offset = 0,
): string {
  if (!Number.isInteger(offset) || offset < WEEK_OFFSET_MIN || offset > WEEK_OFFSET_MAX) {
    throw new InvalidWeekOffsetError(offset);
  }
  const base = `/api/${encodePathSegment(schoolId)}/schedule/${encodePathSegment(kind)}/${encodePathSegment(name)}/week`;
  return `${base}?${new URLSearchParams({ offset: String(offset) }).toString()}`;
}

/** URL for `GET /api/{schoolId}/schedule/{kind}/{name}/now?date=`. */
export function buildNowUrl(
  schoolId: string,
  kind: ScheduleKind,
  name: string,
  date?: string,
): string {
  const base = `/api/${encodePathSegment(schoolId)}/schedule/${encodePathSegment(kind)}/${encodePathSegment(name)}/now`;
  return date ? `${base}?${new URLSearchParams({ date }).toString()}` : base;
}

/** URL for `GET /api/{schoolId}/search?q=`. */
export function buildSearchUrl(schoolId: string, q: string): string {
  return `/api/${encodePathSegment(schoolId)}/search?${new URLSearchParams({ q }).toString()}`;
}

/**
 * URL for `GET /api/{schoolId}/schedule/{kind}/{name}/calendar?year=&month=`.
 *
 * `year` must be >= 2020 and `month` 1..12 — the server rejects anything else
 * with 422, so the builder fails fast with {@link InvalidCalendarRangeError}.
 */
export function buildCalendarUrl(
  schoolId: string,
  kind: ScheduleKind,
  name: string,
  year: number,
  month: number,
): string {
  if (!Number.isInteger(year) || year < CALENDAR_YEAR_MIN) {
    throw new InvalidCalendarRangeError(`Год должен быть не меньше 2020, получено: ${year}`);
  }
  if (!Number.isInteger(month) || month < 1 || month > 12) {
    throw new InvalidCalendarRangeError(`Месяц должен быть от 1 до 12, получено: ${month}`);
  }
  const base = `/api/${encodePathSegment(schoolId)}/schedule/${encodePathSegment(kind)}/${encodePathSegment(name)}/calendar`;
  return `${base}?${new URLSearchParams({ year: String(year), month: String(month) }).toString()}`;
}

/**
 * URL for `GET /api/{schoolId}/free-rooms?date=&lesson=`.
 *
 * `lesson` must be 1..12 (server-enforced); `date` is optional `DD.MM.YYYY`.
 */
export function buildFreeRoomsUrl(schoolId: string, lesson: number, date?: string): string {
  if (!Number.isInteger(lesson) || lesson < LESSON_MIN || lesson > LESSON_MAX) {
    throw new InvalidLessonError(lesson);
  }
  const params = new URLSearchParams({ lesson: String(lesson) });
  if (date) {
    params.set('date', date);
  }
  return `/api/${encodePathSegment(schoolId)}/free-rooms?${params.toString()}`;
}

/** Minimal fetch signature so tests can inject a mock without real network. */
export type FetchLike = typeof fetch;

async function getJson<T>(url: string, fetchImpl: FetchLike): Promise<T> {
  const response = await fetchImpl(url, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    // Attempt to surface the server's `detail`; fall back to the status text.
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body?.detail === 'string' && body.detail) {
        detail = body.detail;
      }
    } catch {
      // Non-JSON error body — keep statusText.
    }
    throw new ApiError(response.status, detail || `HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

/** Typed client for the public schedule API. */
export interface ScheduleApiClient {
  getSchools(): Promise<SchoolsResponse>;
  getClasses(schoolId: string): Promise<ClassesResponse>;
  getTeachers(schoolId: string): Promise<TeachersResponse>;
  getRooms(schoolId: string): Promise<RoomsResponse>;
  getDay(schoolId: string, kind: ScheduleKind, name: string, date?: string): Promise<DaySchedule>;
  getNow(schoolId: string, kind: ScheduleKind, name: string, date?: string): Promise<NowResponse>;
  getWeek(
    schoolId: string,
    kind: ScheduleKind,
    name: string,
    offset?: number,
  ): Promise<WeekScheduleResponse>;
  getCalendar(
    schoolId: string,
    kind: ScheduleKind,
    name: string,
    year: number,
    month: number,
  ): Promise<CalendarResponse>;
  search(schoolId: string, q: string): Promise<SearchResponse>;
  getFreeRooms(schoolId: string, lesson: number, date?: string): Promise<FreeRoomsResponse>;
}

/**
 * Create a client. `fetchImpl` defaults to the global `fetch`; inject a mock in
 * tests. `baseUrl` defaults to `''` (same-origin, paths start with `/api`).
 */
export function createApiClient(fetchImpl: FetchLike = fetch, baseUrl = ''): ScheduleApiClient {
  const withBase = (path: string) => `${baseUrl}${path}`;
  return {
    getSchools: () => getJson<SchoolsResponse>(withBase(buildSchoolsUrl()), fetchImpl),
    getClasses: (schoolId) =>
      getJson<ClassesResponse>(withBase(buildListUrl(schoolId, 'classes')), fetchImpl),
    getTeachers: (schoolId) =>
      getJson<TeachersResponse>(withBase(buildListUrl(schoolId, 'teachers')), fetchImpl),
    getRooms: (schoolId) =>
      getJson<RoomsResponse>(withBase(buildListUrl(schoolId, 'rooms')), fetchImpl),
    getDay: (schoolId, kind, name, date) =>
      getJson<DaySchedule>(withBase(buildDayUrl(schoolId, kind, name, date)), fetchImpl),
    getNow: (schoolId, kind, name, date) =>
      getJson<NowResponse>(withBase(buildNowUrl(schoolId, kind, name, date)), fetchImpl),
    getWeek: (schoolId, kind, name, offset = 0) =>
      getJson<WeekScheduleResponse>(
        withBase(buildWeekUrl(schoolId, kind, name, offset)),
        fetchImpl,
      ),
    getCalendar: (schoolId, kind, name, year, month) =>
      getJson<CalendarResponse>(
        withBase(buildCalendarUrl(schoolId, kind, name, year, month)),
        fetchImpl,
      ),
    search: (schoolId, q) =>
      getJson<SearchResponse>(withBase(buildSearchUrl(schoolId, q)), fetchImpl),
    getFreeRooms: (schoolId, lesson, date) =>
      getJson<FreeRoomsResponse>(withBase(buildFreeRoomsUrl(schoolId, lesson, date)), fetchImpl),
  };
}

/** Default same-origin client. */
export const api: ScheduleApiClient = createApiClient();
