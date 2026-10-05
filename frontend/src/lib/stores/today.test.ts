import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { createTodayStore } from './today.svelte';
import { STORAGE_PREFIX } from './persisted';
import type { ScheduleApiClient } from '../api/client';
import type { SchoolsResponse } from '../api/types';

function fakeClient(response: Partial<SchoolsResponse>): ScheduleApiClient {
  return {
    getSchools: vi.fn().mockResolvedValue({ today: '', schools: [], ...response }),
  } as unknown as ScheduleApiClient;
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('server today store', () => {
  it('adopts the server-provided today, not the browser clock', () => {
    // Browser clock says 2030-01-01; the server says 05.10.2026.
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2030-01-01T12:00:00Z'));

    const store = createTodayStore(fakeClient({ today: '05.10.2026' }), null);
    store.adopt('05.10.2026');

    expect(store.today).toBe('05.10.2026');
    expect(store.tomorrow).toBe('06.10.2026');
    expect(store.yesterday).toBe('04.10.2026');
    // Explicitly assert the browser clock is a different date/year.
    expect(new Date().getFullYear()).toBe(2030);
    expect(store.today).not.toContain('2030');
  });

  it('loads today from /api/schools', async () => {
    const client = fakeClient({ today: '07.11.2026' });
    const store = createTodayStore(client, null);
    expect(store.isLoaded).toBe(false);

    await store.load();

    expect(client.getSchools).toHaveBeenCalledTimes(1);
    expect(store.today).toBe('07.11.2026');
    expect(store.isLoaded).toBe(true);
  });

  it('persists the server today and rehydrates it in a new instance', async () => {
    const first = createTodayStore(fakeClient({ today: '05.10.2026' }), localStorage);
    await first.load();

    const second = createTodayStore(fakeClient({ today: '01.01.2031' }), localStorage);
    // Before load, the cached server value is shown (still not the browser clock).
    expect(second.today).toBe('05.10.2026');

    await second.load();
    expect(second.today).toBe('01.01.2031');
  });

  it('ignores an empty adopt value', () => {
    const store = createTodayStore(fakeClient({}), null);
    store.adopt('');
    expect(store.today).toBe('');
    expect(store.isLoaded).toBe(false);
  });

  it('only rejects an empty adopt; a non-empty value is adopted as-is', () => {
    const store = createTodayStore(fakeClient({}), null);
    store.adopt('not-a-date');
    // `today` is the server's opaque DD.MM.YYYY string; adopt guards only against
    // emptiness, so a caller passing junk gets it echoed back (and `tomorrow`/
    // `yesterday` become null because `addDays` cannot parse it).
    expect(store.today).toBe('not-a-date');
    expect(store.tomorrow).toBeNull();
    expect(store.yesterday).toBeNull();
    expect(store.isLoaded).toBe(true);
  });

  it('seeds today verbatim from the cached server value', () => {
    localStorage.setItem(STORAGE_PREFIX + 'server_today', JSON.stringify('07.11.2026'));
    const store = createTodayStore(fakeClient({}), localStorage);
    // The cache is trusted for the initial paint; the next load replaces it.
    expect(store.today).toBe('07.11.2026');
    expect(store.tomorrow).toBe('08.11.2026');
    expect(store.isLoaded).toBe(true);
  });
});
