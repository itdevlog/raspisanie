import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  buildSchoolsUrl,
  buildListUrl,
  buildDayUrl,
  buildNowUrl,
  buildWeekUrl,
  buildCalendarUrl,
  buildSearchUrl,
  buildFreeRoomsUrl,
  createApiClient,
  InvalidCalendarRangeError,
  InvalidLessonError,
  InvalidWeekOffsetError,
  type FetchLike,
} from './client';
import { ApiError } from './types';

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

describe('URL building', () => {
  it('builds the schools URL', () => {
    expect(buildSchoolsUrl()).toBe('/api/schools');
  });

  it('builds list URLs for each resource', () => {
    expect(buildListUrl('gym1', 'classes')).toBe('/api/gym1/classes');
    expect(buildListUrl('gym1', 'teachers')).toBe('/api/gym1/teachers');
    expect(buildListUrl('gym1', 'rooms')).toBe('/api/gym1/rooms');
  });

  it('builds a day URL with and without a date', () => {
    expect(buildDayUrl('gym1', 'class', '5А')).toBe('/api/gym1/schedule/class/5%D0%90');
    expect(buildDayUrl('gym1', 'teacher', 'Иванов')).toBe(
      '/api/gym1/schedule/teacher/%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2',
    );
    expect(buildDayUrl('gym1', 'room', '101', '05.10.2026')).toBe(
      '/api/gym1/schedule/room/101?date=05.10.2026',
    );
  });

  it('builds a now URL with and without a date', () => {
    expect(buildNowUrl('gym1', 'class', '5А')).toBe('/api/gym1/schedule/class/5%D0%90/now');
    expect(buildNowUrl('gym1', 'class', '5А', '05.10.2026')).toBe(
      '/api/gym1/schedule/class/5%D0%90/now?date=05.10.2026',
    );
    expect(buildNowUrl('gym1', 'teacher', 'Иванов', '')).toBe(
      '/api/gym1/schedule/teacher/%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2/now',
    );
  });

  it('builds a week URL with a validated offset', () => {
    expect(buildWeekUrl('gym1', 'class', '5А', 0)).toBe(
      '/api/gym1/schedule/class/5%D0%90/week?offset=0',
    );
    expect(buildWeekUrl('gym1', 'class', '5А', -2)).toContain('offset=-2');
    expect(buildWeekUrl('gym1', 'class', '5А', 2)).toContain('offset=2');
    expect(() => buildWeekUrl('gym1', 'class', '5А', 3)).toThrow(InvalidWeekOffsetError);
    expect(() => buildWeekUrl('gym1', 'class', '5А', -3)).toThrow(InvalidWeekOffsetError);
  });

  it('builds a calendar URL with a validated year and month', () => {
    expect(buildCalendarUrl('gym1', 'class', '5А', 2026, 10)).toBe(
      '/api/gym1/schedule/class/5%D0%90/calendar?year=2026&month=10',
    );
    expect(buildCalendarUrl('gym1', 'teacher', 'Иванов', 2026, 1)).toContain(
      '/schedule/teacher/%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2/calendar?year=2026&month=1',
    );
    expect(() => buildCalendarUrl('gym1', 'class', '5А', 2019, 10)).toThrow(
      InvalidCalendarRangeError,
    );
    expect(() => buildCalendarUrl('gym1', 'class', '5А', 2026, 0)).toThrow(
      InvalidCalendarRangeError,
    );
    expect(() => buildCalendarUrl('gym1', 'class', '5А', 2026, 13)).toThrow(
      InvalidCalendarRangeError,
    );
    expect(() => buildCalendarUrl('gym1', 'class', '5А', 2026.5, 10)).toThrow(
      InvalidCalendarRangeError,
    );
    expect(() => buildCalendarUrl('gym1', 'class', '5А', 2026, 1.5)).toThrow(
      InvalidCalendarRangeError,
    );
  });

  it('builds a search URL with an encoded query', () => {
    expect(buildSearchUrl('gym1', 'Иванов И.')).toBe(
      '/api/gym1/search?q=%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2+%D0%98.',
    );
  });

  it('builds a free-rooms URL and enforces the 1..12 lesson range', () => {
    expect(buildFreeRoomsUrl('gym1', 1)).toBe('/api/gym1/free-rooms?lesson=1');
    expect(buildFreeRoomsUrl('gym1', 12, '05.10.2026')).toBe(
      '/api/gym1/free-rooms?lesson=12&date=05.10.2026',
    );
    expect(() => buildFreeRoomsUrl('gym1', 0)).toThrow(InvalidLessonError);
    expect(() => buildFreeRoomsUrl('gym1', 13)).toThrow(InvalidLessonError);
  });

  it('encodes school ids in every URL', () => {
    expect(buildListUrl('a/b', 'classes')).toBe('/api/a%2Fb/classes');
    expect(buildSearchUrl('a b', 'x')).toContain('/api/a%20b/search');
  });

  it('omits the date query when the date is empty or absent', () => {
    expect(buildDayUrl('gym1', 'class', '5А', '')).toBe('/api/gym1/schedule/class/5%D0%90');
    expect(buildFreeRoomsUrl('gym1', 3, '')).toBe('/api/gym1/free-rooms?lesson=3');
  });

  it('rejects a non-integer week offset', () => {
    expect(() => buildWeekUrl('gym1', 'class', '5А', 1.5)).toThrow(InvalidWeekOffsetError);
    expect(() => buildWeekUrl('gym1', 'class', '5А', NaN)).toThrow(InvalidWeekOffsetError);
  });

  it('rejects out-of-range and non-integer lesson numbers', () => {
    expect(() => buildFreeRoomsUrl('gym1', -1)).toThrow(InvalidLessonError);
    expect(() => buildFreeRoomsUrl('gym1', 1.5)).toThrow(InvalidLessonError);
  });

  it('names the offending value in the range-error messages', () => {
    // A truncated UI control that silently sent 0/13 must be diagnosable.
    expect(() => buildFreeRoomsUrl('gym1', 13)).toThrow('13');
    expect(() => buildWeekUrl('gym1', 'class', '5А', 5)).toThrow('-2 до 2');
  });
});

describe('client requests (mocked fetch)', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let client: ReturnType<typeof createApiClient>;

  beforeEach(() => {
    fetchMock = vi.fn();
    client = createApiClient(fetchMock as unknown as FetchLike);
  });

  it('GETs /api/schools and returns the typed payload', async () => {
    const payload = {
      today: '05.10.2026',
      schools: [{ id: 'gym1', name: 'Гимназия №1', loaded: true }],
    };
    fetchMock.mockResolvedValueOnce(jsonResponse(payload));

    await expect(client.getSchools()).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith('/api/schools', {
      headers: { Accept: 'application/json' },
    });
  });

  it('parses wrapped list responses', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ classes: ['5А', '6Б'] }))
      .mockResolvedValueOnce(jsonResponse({ teachers: ['Иванов'] }))
      .mockResolvedValueOnce(jsonResponse({ rooms: ['101'] }));

    await expect(client.getClasses('gym1')).resolves.toEqual({ classes: ['5А', '6Б'] });
    await expect(client.getTeachers('gym1')).resolves.toEqual({ teachers: ['Иванов'] });
    await expect(client.getRooms('gym1')).resolves.toEqual({ rooms: ['101'] });
  });

  it('parses a day payload', async () => {
    const day = {
      date: '05.10.2026',
      day_name: 'Понедельник',
      kind: 'class',
      entity: '5А',
      lessons: [
        {
          num: 1,
          start: '08:00',
          end: '08:45',
          items: [
            {
              subject: 'Математика',
              teacher: 'Иванов',
              room: '101',
              class_name: null,
              groups: null,
              is_method_hour: false,
            },
          ],
          has_exchange: true,
          is_cancelled: false,
        },
      ],
      vacation: false,
      weekend: false,
      no_period: false,
    };
    fetchMock.mockResolvedValueOnce(jsonResponse(day));

    await expect(client.getDay('gym1', 'class', '5А', '05.10.2026')).resolves.toEqual(day);
    expect(fetchMock).toHaveBeenCalledWith('/api/gym1/schedule/class/5%D0%90?date=05.10.2026', {
      headers: { Accept: 'application/json' },
    });
  });

  it('parses a week payload', async () => {
    const week = { days: [{ date: '05.10.2026', no_period: true }] };
    fetchMock.mockResolvedValueOnce(jsonResponse(week));
    await expect(client.getWeek('gym1', 'class', '5А', 0)).resolves.toEqual(week);
  });

  it('parses a month-calendar payload and requests year/month', async () => {
    const calendar = {
      days: [
        {
          date: '01.10.2026',
          day_name: 'Четверг',
          weekend: false,
          vacation: false,
          no_period: false,
          has_exchange: true,
          has_cancelled: false,
          lesson_count: 6,
        },
      ],
    };
    fetchMock.mockResolvedValueOnce(jsonResponse(calendar));

    await expect(client.getCalendar('gym1', 'class', '5А', 2026, 10)).resolves.toEqual(calendar);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/gym1/schedule/class/5%D0%90/calendar?year=2026&month=10',
      { headers: { Accept: 'application/json' } },
    );
  });

  it('parses a now payload and requests the date', async () => {
    const now = {
      server_time: '2026-10-05T10:00:00+03:00',
      current: {
        num: 2,
        time: '09:00-09:45',
        subject: 'Физика',
        room: '202',
        in_minutes: 20,
      },
      next: null,
    };
    fetchMock.mockResolvedValueOnce(jsonResponse(now));

    await expect(client.getNow('gym1', 'class', '5А', '05.10.2026')).resolves.toEqual(now);
    expect(fetchMock).toHaveBeenCalledWith('/api/gym1/schedule/class/5%D0%90/now?date=05.10.2026', {
      headers: { Accept: 'application/json' },
    });
  });

  it('parses search and free-rooms payloads', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ teachers: ['Иванов'], rooms: ['101'] }))
      .mockResolvedValueOnce(jsonResponse({ free_rooms: ['102', '103'] }));

    await expect(client.search('gym1', 'ив')).resolves.toEqual({
      teachers: ['Иванов'],
      rooms: ['101'],
    });
    await expect(client.getFreeRooms('gym1', 2, '05.10.2026')).resolves.toEqual({
      free_rooms: ['102', '103'],
    });
  });

  it('throws ApiError with the server detail on non-OK responses', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ detail: 'Класс не найден' }, { status: 404, statusText: 'Not Found' }),
    );
    await expect(client.getClasses('gym1')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: 'Класс не найден',
    });
  });

  it('falls back to the status code when the error body is not JSON', async () => {
    fetchMock.mockResolvedValueOnce(new Response('boom', { status: 500, statusText: 'Oops' }));
    const promise = client.getSchools();
    await expect(promise).rejects.toBeInstanceOf(ApiError);
    await expect(promise).rejects.toMatchObject({ status: 500 });
  });
});
