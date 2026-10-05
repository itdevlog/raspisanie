// frontend/src/lib/dates.ts
//
// Date-string helpers for the `DD.MM.YYYY` format the API uses.
//
// These never read the browser clock: callers pass the server-provided date in
// explicitly. `Date` is only used as a calendar calculator built from explicit
// components, never `new Date()` / `Date.now()`.

const DD_MM_YYYY = /^(\d{2})\.(\d{2})\.(\d{4})$/;

/** Parse `DD.MM.YYYY` into `{ year, month, day }`, or `null` if invalid. */
export function parseRuDate(value: string): { year: number; month: number; day: number } | null {
  const match = DD_MM_YYYY.exec(value);
  if (!match) {
    return null;
  }
  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  // Validate using an explicit UTC calendar date (avoids TZ drift and clock reads).
  const probe = new Date(Date.UTC(year, month - 1, day));
  const valid =
    probe.getUTCFullYear() === year &&
    probe.getUTCMonth() === month - 1 &&
    probe.getUTCDate() === day;
  return valid ? { year, month, day } : null;
}

/** Format `{ year, month, day }` back to `DD.MM.YYYY`. */
export function formatRuDate(year: number, month: number, day: number): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(day)}.${pad(month)}.${pad(year)}`;
}

/**
 * Add (or subtract) whole days to a `DD.MM.YYYY` string using a plain UTC
 * calendar calculation. Returns `null` for invalid input.
 */
export function addDays(value: string, days: number): string | null {
  const parsed = parseRuDate(value);
  if (!parsed) {
    return null;
  }
  const probe = new Date(Date.UTC(parsed.year, parsed.month - 1, parsed.day));
  probe.setUTCDate(probe.getUTCDate() + days);
  return formatRuDate(probe.getUTCFullYear(), probe.getUTCMonth() + 1, probe.getUTCDate());
}

/** Server "today" `DD.MM.YYYY` plus tomorrow/yesterday derived from it. */
export interface ServerDateRef {
  today: string;
  tomorrow: string | null;
  yesterday: string | null;
}

/** Build a {@link ServerDateRef} from the server-provided today. */
export function serverDateRef(today: string): ServerDateRef {
  return {
    today,
    tomorrow: addDays(today, 1),
    yesterday: addDays(today, -1),
  };
}
