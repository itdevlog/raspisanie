import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  buildSchoolsUrl,
  buildListUrl,
  buildDayUrl,
  buildWeekUrl,
  buildSearchUrl,
  buildFreeRoomsUrl,
  createApiClient,
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

  it('builds a week URL with a validated offset', () => {
    expect(buildWeekUrl('gym1', 'class', '5А', 0)).toBe(
      '/api/gym1/schedule/class/5%D0%90/week?offset=0',
    );
    expect(buildWeekUrl('gym1', 'class', '5А', -2)).toContain('offset=-2');
    expect(buildWeekUrl('gym1', 'class', '5А', 2)).toContain('offset=2');
    expect(() => buildWeekUrl('gym1', 'class', '5А', 3)).toThrow(InvalidWeekOffsetError);
    expect(() => buildWeekUrl('gym1', 'class', '5А', -3)).toThrow(InvalidWeekOffsetError);
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
          items: [{ subject: 'Математика', teacher: 'Иванов', room: '101', class_name: null }],
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
