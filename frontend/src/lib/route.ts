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

/** The in-app screens. */
export type View = 'home' | 'schedule' | 'tools' | 'list' | 'settings';

/**
 * Parsed route. `schedule` carries the selection encoded in a share link (and
 * the optional pinned date); a bare `schedule` (school/name null) is the nav-tab
 * view with no entity chosen yet. `list` is the per-kind name list, `settings`
 * the preferences screen. The other views carry only their `view`.
 */
export type Route =
  | { view: 'home' }
  | { view: 'tools' }
  | { view: 'settings' }
  | { view: 'list'; kind: ScheduleKind }
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
export const VIEWS: readonly View[] = ['home', 'schedule', 'tools', 'list', 'settings'] as const;

/** True for the valid view names. */
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
    if (segment === 'settings') {
      return { view: 'settings' };
    }
    if (segment === 'schedule') {
      return { ...BARE_SCHEDULE_ROUTE };
    }
    if (segment.startsWith('list/')) {
      const kind = segment.slice('list/'.length);
      if (isScheduleKind(kind)) {
        return { view: 'list', kind };
      }
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
 * Percent-encode one path segment exactly like Python's
 * `urllib.parse.quote(s, safe='')`.
 *
 * `encodeURIComponent` is close but leaves `! ' ( ) *` literal, whereas
 * Python's `quote` (whose unreserved set is `A-Za-z0-9_.-~`) encodes them as
 * `%21 %27 %28 %29 %2A`. Everything else matches: `encodeURIComponent` already
 * encodes the same set and also leaves `~` literal. We post-encode only those
 * five extra characters so the frontend link is byte-identical to the string
 * produced by `core/background_updater.py::build_class_share_url`.
 */
const PYTHON_EXTRA_UNRESERVED = /[!'()*]/g;

/** Unicode code point → `%XX`/`%XXXX` (uppercase hex), matching Python's `quote`. */
function pythonPercentEscape(ch: string): string {
  return Array.from(ch)
    .map((c) => `%${c.codePointAt(0)!.toString(16).toUpperCase().padStart(2, '0')}`)
    .join('');
}

/** Encode a path segment byte-for-byte identically to `urllib.parse.quote(s, safe='')`. */
export function quoteLikePython(value: string): string {
  return encodeURIComponent(value).replace(PYTHON_EXTRA_UNRESERVED, pythonPercentEscape);
}

/**
 * Build the share path for a class/teacher/room — byte-for-byte the same scheme
 * as W16's `build_class_share_url`, which uses `quote(value, safe='')` for the
 * school and name segments and `date.strftime('%d.%m.%Y')` (DD.MM.YYYY) for the
 * date.
 *
 * `date` is optional `DD.MM.YYYY`; omitted when null (server then uses its
 * own "today"). `school`/`name` are encoded with {@link quoteLikePython},
 * `kind` is a fixed safe token.
 */
export function buildSharePath(
  school: string,
  kind: ScheduleKind,
  name: string,
  date?: string | null,
): string {
  const base = `${SCHEDULE_PREFIX}${quoteLikePython(school)}/${kind}/${quoteLikePython(name)}`;
  return date ? `${base}?date=${encodeURIComponent(date)}` : base;
}

/**
 * Build the in-app path for a view: `/` for home, `/tools` for tools,
 * `/settings` for settings, `/list/{kind}` for a per-kind list, `/schedule`
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
  if (route.view === 'tools') {
    return '/tools';
  }
  if (route.view === 'settings') {
    return '/settings';
  }
  if (route.view === 'list') {
    return `/list/${route.kind}`;
  }
  return '/';
}
