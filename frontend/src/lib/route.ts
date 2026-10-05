// frontend/src/lib/route.ts
//
// Pure, framework-free parsing/building of the public site's routes.
//
// Share-link scheme (spec §7 «Фронтенд»), produced verbatim by
// `core/background_updater.py::build_class_share_url` (W16) and consumed here by
// {@link parseRoute}:
//
//   /s/{school}/{kind}/{name}?date=DD.MM.YYYY
//
// `{kind}` ∈ {class, teacher, room}; `{name}` is URL-encoded (Cyrillic, spaces,
// `№`, …) so it round-trips with W16's `quote(class_name, safe='')`.
//
// No DOM access lives here — `parsePath`/`buildSharePath` take plain strings and
// are unit-testable. The browser adapter is in `lib/platform.ts` and the
// reactive store in `lib/stores/route.svelte.ts`.

import { parseRuDate } from './dates';
import type { ScheduleKind } from './api/types';

/** The three in-app screens. */
export type View = 'home' | 'schedule' | 'tools';

/**
 * Parsed route. `schedule` carries the selection encoded in a share link (and
 * the optional pinned date); a bare `schedule` (school/name null) is the nav-tab
 * view with no entity chosen yet. The other views carry only their `view`.
 */
export type Route =
  | { view: 'home' }
  | { view: 'tools' }
  | {
      view: 'schedule';
      /** Linked school id, or null for the bare nav-tab view. */
      school: string | null;
      kind: ScheduleKind;
      /** Decoded entity name as produced by W16's `quote(class_name)`, or null. */
      name: string | null;
      /** `DD.MM.YYYY` when the link pinned a date, else `null`. */
      date: string | null;
    };

/** The Home screen — the fallback for unknown/absent/partial routes. */
export const HOME_ROUTE: Route = { view: 'home' };

/** The bare schedule view: no entity selected yet (nav tab, not a share link). */
export const BARE_SCHEDULE_ROUTE: Route = {
  view: 'schedule',
  school: null,
  kind: 'class',
  name: null,
  date: null,
};

const SCHEDULE_PREFIX = '/s/';

/** All view values as a runtime list for validation. */
export const VIEWS: readonly View[] = ['home', 'schedule', 'tools'] as const;

/** True for the three valid view names. */
export function isView(value: string): value is View {
  return (VIEWS as readonly string[]).includes(value);
}

/** True for the three valid schedule kinds. */
export function isScheduleKind(value: string): value is ScheduleKind {
  return value === 'class' || value === 'teacher' || value === 'room';
}

/**
 * Decode a percent-encoded path segment, tolerating malformed input.
 *
 * `decodeURIComponent` throws on a lone `%`; a share link that was truncated by
 * a chat client should still open something, so we fall back to the raw value.
 */
function safeDecodeSegment(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/**
 * Parse a pathname + query string into a {@link Route}.
 *
 * Returns {@link HOME_ROUTE} for anything that is not a well-formed share link
 * (unknown view, missing segment, bad kind, absent school/name) so the app never
 * lands on a blank screen. A schedule link without `?date=` is valid and yields
 * `date: null`; the caller then uses the server's "today".
 */
export function parsePath(pathname: string, search = ''): Route {
  const path = pathname || '/';

  // Query on the path argument (`/s/a/b/c?date=…`) is tolerated too.
  let pathPart = path;
  let searchPart = search;
  const queryIndex = pathPart.indexOf('?');
  if (queryIndex !== -1) {
    searchPart = pathPart.slice(queryIndex + 1) + (search ? `&${search.replace(/^\?/, '')}` : '');
    pathPart = pathPart.slice(0, queryIndex);
  }

  if (!pathPart.startsWith(SCHEDULE_PREFIX)) {
    // Named in-app views; everything else is Home.
    const segment = pathPart.replace(/^\/+|\/+$/g, '');
    if (segment === 'tools') {
      return { view: 'tools' };
    }
    if (segment === 'schedule') {
      return { ...BARE_SCHEDULE_ROUTE };
    }
    return HOME_ROUTE;
  }

  const rest = pathPart.slice(SCHEDULE_PREFIX.length);
  const segments = rest.split('/');
  if (segments.length !== 3) {
    return HOME_ROUTE;
  }
  const [rawSchool, rawKind, rawName] = segments;
  const school = safeDecodeSegment(rawSchool);
  const name = safeDecodeSegment(rawName);
  if (!school || !name || !isScheduleKind(rawKind)) {
    return HOME_ROUTE;
  }

  const params = new URLSearchParams(searchPart.startsWith('?') ? searchPart.slice(1) : searchPart);
  const rawDate = params.get('date');
  const date = rawDate && parseRuDate(rawDate) ? rawDate : null;

  return { view: 'schedule', school, kind: rawKind, name, date };
}

/** Parse a `Location`-shape (`{ pathname, search }`) or full URL string. */
export function parseLocation(location: { pathname: string; search?: string } | string): Route {
  if (typeof location === 'string') {
    // Accept an absolute URL or a bare path; `URL` needs a base for the latter.
    try {
      const url = new URL(location, 'http://localhost');
      return parsePath(url.pathname, url.search);
    } catch {
      return parsePath(location);
    }
  }
  return parsePath(location.pathname, location.search ?? '');
}

/**
 * Build the share path for a class/teacher/room — byte-for-byte the same scheme
 * as W16's `build_class_share_url` (`quote(value, safe='')` ==
 * `encodeURIComponent(value)`).
 *
 * `date` is optional `DD.MM.YYYY`; omitted when null (server then uses its
 * own "today"). `school`/`name` are encoded, `kind` is a fixed safe token.
 */
export function buildSharePath(
  school: string,
  kind: ScheduleKind,
  name: string,
  date?: string | null,
): string {
  const base = `${SCHEDULE_PREFIX}${encodeURIComponent(school)}/${kind}/${encodeURIComponent(name)}`;
  return date ? `${base}?date=${encodeURIComponent(date)}` : base;
}

/**
 * Build the in-app path for a view: `/` for home, `/tools` for tools, `/schedule`
 * for the bare schedule view, and a share path for a scheduled entity.
 *
 * This keeps the address bar in sync with `pushState` navigation.
 */
export function buildViewPath(route: Route): string {
  if (route.view === 'schedule') {
    if (route.school && route.name) {
      return buildSharePath(route.school, route.kind, route.name, route.date);
    }
    return '/schedule';
  }
  return route.view === 'tools' ? '/tools' : '/';
}
