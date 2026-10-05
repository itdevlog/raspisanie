// frontend/src/lib/share.ts
//
// Share-link building/copying for the schedule screen. The URL scheme is the
// single source of truth shared with the W16 push notification builder
// (`core/background_updater.py::build_class_share_url`): the produced path is
// `/s/{school}/{kind}/{name}?date=DD.MM.YYYY` with Python-equivalent
// percent-encoding on school/name (`quoteLikePython`) and `DD.MM.YYYY` for the
// date.
//
// This module is DOM-touching (clipboard/`navigator.share`) but every effect is
// injectable, so it is unit-testable without a real browser.

import { buildSharePath } from './route';
import type { ScheduleKind } from './api/types';

/** Minimal `navigator` surface used by {@link shareSchedule}. */
export interface ShareNavigator {
  share?: (data: ShareData) => Promise<void>;
  clipboard?: { writeText(text: string): Promise<void> };
}

/** Minimal `window` surface (only `location.origin` is read). */
export interface ShareWindow {
  location: { origin: string };
}

/** Result of a share attempt; `method` records which path won. */
export type ShareMethod = 'share' | 'clipboard';

export interface ShareResult {
  ok: boolean;
  method: ShareMethod | null;
  url: string;
  /** Error message when neither `navigator.share` nor the clipboard worked. */
  error?: string;
}

/**
 * Absolute share URL for an entity's schedule.
 *
 * `origin` is prefixed verbatim (e.g. `https://rasp.example.ru`); an empty origin
 * yields a root-relative URL. `basePath` prefixes the app if it is ever mounted
 * under a sub-path (default `''`).
 */
export function buildShareUrl(
  origin: string,
  school: string,
  kind: ScheduleKind,
  name: string,
  date?: string | null,
  basePath = '',
): string {
  const base = origin.replace(/\/+$/, '');
  const prefix = basePath.replace(/\/+$/, '');
  return `${base}${prefix}${buildSharePath(school, kind, name, date)}`;
}

/**
 * Share the entity's schedule.
 *
 * Tries `navigator.share` first (mobile/Telegram), then the clipboard
 * (`navigator.clipboard.writeText`), and reports which method succeeded. Never
 * throws — failures come back as `{ ok: false, error }` so a UI can show a
 * notice without crashing. An aborted native share (`AbortError`) is treated as
 * a no-op success-free cancellation rather than a clipboard retry.
 */
export async function shareSchedule(
  url: string,
  options: { title?: string; text?: string } = {},
  navigatorLike: ShareNavigator | null = typeof navigator === 'undefined' ? null : navigator,
): Promise<ShareResult> {
  const nav = navigatorLike;
  const payload = { title: options.title ?? 'Расписание', text: options.text, url };

  if (nav?.share) {
    try {
      await nav.share(payload);
      return { ok: true, method: 'share', url };
    } catch (err) {
      // User dismissed the native sheet: not an error, do not spam the clipboard.
      if (isAbortError(err)) {
        return { ok: true, method: null, url };
      }
      // Otherwise fall through to the clipboard.
    }
  }

  if (nav?.clipboard?.writeText) {
    try {
      await nav.clipboard.writeText(url);
      return { ok: true, method: 'clipboard', url };
    } catch (err) {
      return {
        ok: false,
        method: null,
        url,
        error: err instanceof Error ? err.message : 'Не удалось скопировать ссылку',
      };
    }
  }

  return { ok: false, method: null, url, error: 'Копирование ссылки недоступно' };
}

function isAbortError(err: unknown): boolean {
  return (
    typeof err === 'object' &&
    err !== null &&
    'name' in err &&
    (err as { name?: unknown }).name === 'AbortError'
  );
}

/** Convenience: build the URL from a window/navigator pair and share it. */
export function shareScheduleFor(
  win: ShareWindow,
  nav: ShareNavigator | null,
  school: string,
  kind: ScheduleKind,
  name: string,
  date?: string | null,
): Promise<ShareResult> {
  const url = buildShareUrl(win.location.origin, school, kind, name, date);
  return shareSchedule(url, { title: 'Расписание', text: name }, nav);
}
