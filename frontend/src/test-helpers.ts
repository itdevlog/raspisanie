// frontend/src/test-helpers.ts
//
// Shared fixtures/fakes for the W20 screen tests. Not a `*.test.ts` file, so
// Vitest does not collect it as a suite.

import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { vi } from 'vitest';
import type { ScheduleApiClient } from './lib/api/client';
import type { DaySchedule, School } from './lib/api/types';
import { createSelectionStore } from './lib/stores/selection.svelte';
import { createTodayStore } from './lib/stores/today.svelte';
import { createRouteStore, type RouteStore } from './lib/stores/route.svelte';
import type { BrowserEnv } from './lib/platform';

/** Build a day payload with sensible defaults; override any field. */
export function makeDay(overrides: Partial<DaySchedule> = {}): DaySchedule {
  return {
    date: '05.10.2026',
    day_name: 'Понедельник',
    kind: 'class',
    entity: '5А',
    lessons: [],
    vacation: false,
    weekend: false,
    no_period: false,
    ...overrides,
  };
}

/** Two schools, one loaded and one not. */
export const SAMPLE_SCHOOLS: School[] = [
  { id: 'gym1', name: 'Гимназия №1', loaded: true },
  { id: 'school2', name: 'Школа №2', loaded: false },
];

/**
 * Create a fully stubbed {@link ScheduleApiClient}. Every method is a `vi.fn`
 * resolving to an empty-shaped payload; override individual methods as needed.
 */
export function makeClient(overrides: Partial<ScheduleApiClient> = {}): ScheduleApiClient {
  const client: ScheduleApiClient = {
    getSchools: vi.fn().mockResolvedValue({ today: '05.10.2026', schools: SAMPLE_SCHOOLS }),
    getClasses: vi.fn().mockResolvedValue({ classes: ['5А', '6Б'] }),
    getTeachers: vi.fn().mockResolvedValue({ teachers: ['Иванов И.И.'] }),
    getRooms: vi.fn().mockResolvedValue({ rooms: ['101', '202'] }),
    getDay: vi.fn().mockResolvedValue(makeDay()),
    getWeek: vi.fn().mockResolvedValue({ days: [makeDay()] }),
    search: vi.fn().mockResolvedValue({ teachers: [], rooms: [] }),
    getFreeRooms: vi.fn().mockResolvedValue({ free_rooms: [] }),
    ...overrides,
  };
  return client;
}

/** A selection store backed by an isolated in-memory storage. */
export function makeSelection() {
  return createSelectionStore(null);
}

/** A today store backed by an isolated storage and a fake client. */
export function makeToday(today = '05.10.2026') {
  const client = makeClient({ getSchools: vi.fn().mockResolvedValue({ today, schools: [] }) });
  return createTodayStore(client, null);
}

/**
 * A fake {@link BrowserEnv} for router tests: push/replace update the location,
 * `back`/`forward` replay entries to a subscribed popstate listener.
 */
export function makeFakeEnv(initialPath = '/') {
  const stack: string[] = [initialPath];
  let index = 0;
  let listener: (() => void) | null = null;
  const location = { pathname: '/', search: '' };

  function sync(url: string) {
    const [path, search = ''] = url.split('?');
    location.pathname = path || '/';
    location.search = search ? `?${search}` : '';
  }
  sync(initialPath);

  const env: BrowserEnv = {
    location,
    origin: 'https://rasp.example.ru',
    history: {
      pushState(_state, _title, url) {
        stack.splice(index + 1);
        stack.push(url);
        index = stack.length - 1;
        sync(url);
      },
      replaceState(_state, _title, url) {
        stack[index] = url;
        sync(url);
      },
    },
    addPopStateListener(cb) {
      listener = cb;
      return () => {
        listener = null;
      };
    },
  };

  return {
    env,
    location,
    back() {
      if (index > 0) {
        index -= 1;
        sync(stack[index]);
        listener?.();
      }
    },
    forward() {
      if (index < stack.length - 1) {
        index += 1;
        sync(stack[index]);
        listener?.();
      }
    },
  };
}

/** A router store on top of a fake env, for component tests. */
export function makeRouter(
  env: BrowserEnv = makeFakeEnv().env,
): { router: RouteStore; env: BrowserEnv } {
  return { router: createRouteStore(env), env };
}

/**
 * Real cross-language oracle: run the actual Python producer
 * `core/background_updater.py::build_class_share_url` and return its output.
 *
 * The name/school are passed as base64 to avoid shell-quoting surprises, and the
 * repo root is derived from this file's location so the call works regardless of
 * the test's CWD. `date` is `DD.MM.YYYY` (the producer's API format). This is
 * deliberately a live call (not a mirrored constant) so the frontend builder is
 * checked against the producer, not a fake.
 */
export function pythonBuildClassShareUrl(
  base: string,
  school: string,
  name: string,
  date: string,
): string {
  const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
  const script = [
    'import base64, sys',
    'from datetime import datetime',
    'sys.path.insert(0, sys.argv[1])',
    'from core.background_updater import build_class_share_url',
    'b64 = lambda s: base64.b64decode(s).decode("utf-8")',
    'out = build_class_share_url(b64(sys.argv[2]), b64(sys.argv[3]), b64(sys.argv[4]),',
    '                            datetime.strptime(sys.argv[5], "%d.%m.%Y"))',
    'sys.stdout.write(out)',
  ].join('\n');
  const b64 = (s: string) => Buffer.from(s, 'utf-8').toString('base64');
  return execFileSync(
    'python3',
    ['-c', script, repoRoot, b64(base), b64(school), b64(name), date],
    { encoding: 'utf-8' },
  ).trim();
}
