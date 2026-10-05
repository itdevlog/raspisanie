// frontend/src/lib/stores/today.svelte.ts
//
// Server-authoritative "today". The browser clock is NEVER used: the edge/origin
// server is the single source of truth (it owns the school timezone), so `today`
// comes from `GET /api/schools`'s `today` field.

import { api as defaultApi, type ScheduleApiClient } from '../api/client';
import { readJson, type StorageLike, writeJson } from './persisted';
import { serverDateRef, type ServerDateRef } from '../dates';

const TODAY_KEY = 'server_today';

/**
 * Reactive server-today store.
 *
 * Factory so tests can inject an isolated storage and a fake client. The app
 * uses the default {@link serverToday} instance.
 */
export function createTodayStore(
  client: ScheduleApiClient = defaultApi,
  storage?: StorageLike | null,
) {
  // Seed from cache so a reload shows a plausible date before the network call
  // completes; it is always replaced by the freshly fetched server value.
  let state = $state<ServerDateRef>(serverDateRef(readJson<string>(TODAY_KEY, '', storage)));

  /**
   * Adopt a server-provided date without a network call (e.g. today already
   * fetched by a school-list store). Ignores empty/invalid values.
   */
  function adopt(today: string): void {
    const next = serverDateRef(today);
    if (!next.today) {
      return;
    }
    state = next;
    writeJson(TODAY_KEY, today, storage);
  }

  return {
    /** Full date reference derived from the server's today. */
    get ref(): ServerDateRef {
      return state;
    },
    /** Server today as `DD.MM.YYYY`, or `''` before the first successful load. */
    get today(): string {
      return state.today;
    },
    get tomorrow(): string | null {
      return state.tomorrow;
    },
    get yesterday(): string | null {
      return state.yesterday;
    },
    /** True once a server value is known (cached or freshly fetched). */
    get isLoaded(): boolean {
      return state.today !== '';
    },
    /**
     * Fetch `/api/schools` and adopt the server's `today`. Returns the schools
     * response so callers can use the school list in the same round-trip.
     */
    async load(): Promise<void> {
      const response = await client.getSchools();
      adopt(response.today);
    },
    /**
     * Adopt a server-provided date without a network call.
     */
    adopt,
  };
}

export type TodayStore = ReturnType<typeof createTodayStore>;

/** App-level singleton. */
export const serverToday: TodayStore = createTodayStore();
