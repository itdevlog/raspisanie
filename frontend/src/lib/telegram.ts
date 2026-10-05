// frontend/src/lib/telegram.ts
//
// Telegram WebApp (Mini App) integration for the public schedule PWA (W24).
//
// The public site is a normal web app first: it must render and work in a
// regular browser **without** the Telegram WebApp SDK. When it happens to run
// inside Telegram (the SDK injects `window.Telegram.WebApp`), we additionally
// adopt the client's theme and wire the Telegram BackButton to the app router.
//
// Everything that touches the SDK goes through the injectable {@link TelegramEnv}
// adapter (mirroring `lib/platform.ts` / `lib/push.ts`), so the module is
// unit-testable and never reaches for the real `window.Telegram` in tests.
//
// No secrets live here: this only reads public UI/theme data from the WebApp
// object. `initData` is used solely as a presence signal, never sent anywhere.

import type { Route } from './route';
import type { ScheduleKind } from './api/types';

/**
 * The `start` payload carried by the «Открыть в Telegram» deep link.
 *
 * Telegram only lets `/start` accept `A-Za-z0-9_-` and caps it at 64 bytes, so
 * we cannot put a URL-encoded Cyrillic name in it. Instead the payload is a
 * compact, URL-safe descriptor of the W16/W22 share target:
 *
 *   `s__<school>__<kind>__<name>`            (base64url tokens, `__`-joined)
 *   `s__<school>__<kind>__<name>__d__DD-MM-YYYY`  (optional pinned date)
 *
 * School and name are encoded with {@link encodeStartSegment} (base64url of the
 * UTF-8 bytes, `=` padding stripped) and joined with `__`; `kind` is a single
 * letter (`c`/`t`/`r`). The date is `DD.MM.YYYY` → `DD-MM-YYYY` (ASCII, its `-`
 * cannot collide with the `__`-joined base64url tokens). The whole payload is
 * validated to fit Telegram's 64-byte limit.
 *
 * Decoding lives server-side (the bot's `/start` handler); the format is kept
 * here as the single source of truth and documented for that handler.
 */
export interface TelegramShareTarget {
  school: string;
  kind: ScheduleKind;
  name: string;
  /** `DD.MM.YYYY`, or null/absent when the link does not pin a date. */
  date?: string | null;
}

/** Telegram's limit for the `?start=` payload. */
export const TELEGRAM_START_MAX_BYTES = 64;

const KIND_TOKENS: Record<ScheduleKind, string> = {
  class: 'c',
  teacher: 't',
  room: 'r',
};

const TOKEN_TO_KIND: Record<string, ScheduleKind> = {
  c: 'class',
  t: 'teacher',
  r: 'room',
};

/** Encode one payload segment as base64url (`=` stripped), UTF-8 safe. */
export function encodeStartSegment(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = '';
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Decode a base64url segment produced by {@link encodeStartSegment}; tolerant of junk. */
export function decodeStartSegment(value: string): string {
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padding = '='.repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(normalized + padding);
  const bytes = Uint8Array.from(binary, (ch) => ch.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

/** `DD.MM.YYYY` → `DD-MM-YYYY` (ASCII); anything else is dropped. */
function encodeStartDate(date: string | null | undefined): string | null {
  if (!date) {
    return null;
  }
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(date);
  return match ? `${match[1]}-${match[2]}-${match[3]}` : null;
}

/** `DD-MM-YYYY` → `DD.MM.YYYY`; returns null when not a date token. */
function decodeStartDate(token: string | undefined): string | null {
  if (!token) {
    return null;
  }
  const match = /^(\d{2})-(\d{2})-(\d{4})$/.exec(token);
  return match ? `${match[1]}.${match[2]}.${match[3]}` : null;
}

/**
 * Build the URL-safe `/start` payload for a share target.
 *
 * Returns null when the target has no school (nothing to open) or the encoded
 * payload would exceed Telegram's 64-byte limit — callers then hide/disable the
 * control. `target.kind` defaults to `class` (the MVP kind) when absent.
 */
export function buildStartPayload(target: TelegramShareTarget): string | null {
  if (!target.school || !target.name) {
    return null;
  }
  const parts = [
    's',
    encodeStartSegment(target.school),
    KIND_TOKENS[target.kind],
    encodeStartSegment(target.name),
  ];
  const date = encodeStartDate(target.date);
  if (date) {
    parts.push('d', date);
  }
  const payload = parts.join('__');
  if (new TextEncoder().encode(payload).length > TELEGRAM_START_MAX_BYTES) {
    return null;
  }
  return payload;
}

/** Parse a `/start` payload produced by {@link buildStartPayload}; null when malformed. */
export function parseStartPayload(payload: string): TelegramShareTarget | null {
  const parts = payload.split('__');
  if (parts.shift() !== 's' || parts.length < 3) {
    return null;
  }
  const [schoolToken, kindToken, nameToken] = parts;
  const kind = TOKEN_TO_KIND[kindToken];
  if (!kind) {
    return null;
  }
  try {
    const school = decodeStartSegment(schoolToken);
    const name = decodeStartSegment(nameToken);
    if (!school || !name) {
      return null;
    }
    const dateIndex = parts.indexOf('d', 3);
    const date = dateIndex !== -1 ? decodeStartDate(parts[dateIndex + 1]) : null;
    return { school, kind, name, date };
  } catch {
    return null;
  }
}

/** The `start` payload for a route, or null when the route has no share target. */
export function startPayloadForRoute(route: Route): string | null {
  if (route.view !== 'schedule' || !route.school || !route.name) {
    return null;
  }
  return buildStartPayload({
    school: route.school,
    kind: route.kind,
    name: route.name,
    date: route.date,
  });
}

/**
 * Deep link that opens the bot and hands it the share target.
 *
 * Returns null when no bot username is configured (`VITE_TELEGRAM_BOT` unset),
 * so callers hide/disable the control rather than link to a broken URL. The
 * leading `@` is tolerated and stripped; a bare username (no `t.me/`, no URL) is
 * expected.
 */
export function buildTelegramDeepLink(
  botUsername: string | undefined | null,
  payload: string,
): string | null {
  const bot = (botUsername ?? '').trim().replace(/^@/, '');
  if (!bot || !payload) {
    return null;
  }
  return `https://t.me/${bot}?start=${encodeURIComponent(payload)}`;
}

// --- Telegram WebApp SDK adapter -------------------------------------------------

/** Telegram `themeParams` (hex colours, e.g. `#1c1c1e`). */
export interface TelegramThemeParams {
  bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  secondary_bg_color?: string;
}

/**
 * Minimal, injectable surface of `window.Telegram.WebApp` that this app uses.
 * All members are optional so a partial/hostile SDK cannot crash the page.
 */
export interface TelegramWebAppLike {
  /** Present only inside a real Telegram Mini App. */
  initData?: string;
  /** `'light' | 'dark'` (kept loose for forward compatibility). */
  colorScheme?: string;
  themeParams?: TelegramThemeParams;
  /** Apply a theme change callback; SDK flags live under `eventData`. */
  onEvent?: (event: string, handler: () => void) => void;
  offEvent?: (event: string, handler: () => void) => void;
  /** Expand the Mini App to full height. */
  expand?: () => void;
  /** Signal that the app is ready to be shown. */
  ready?: () => void;
  BackButton?: TelegramBackButtonLike;
}

/** Minimal `BackButton` surface. */
export interface TelegramBackButtonLike {
  isVisible?: boolean;
  show?: () => void;
  hide?: () => void;
  onClick?: (handler: () => void) => void;
  offClick?: (handler: () => void) => void;
}

/** Injectable Telegram environment: the WebApp object (or undefined outside Telegram). */
export interface TelegramEnv {
  webApp?: TelegramWebAppLike;
}

/** Production environment: reads `window.Telegram.WebApp` lazily and defensively. */
export function telegramEnv(win: Window = window): TelegramEnv {
  return {
    webApp: (win as unknown as { Telegram?: { WebApp?: TelegramWebAppLike } }).Telegram?.WebApp,
  };
}

/**
 * Is this page running inside a Telegram Mini App?
 *
 * Both the `WebApp` object and a non-empty `initData` string must be present:
 * the SDK script exposes `WebApp` even when opened from a plain browser (an
 * anonymous context), and only `initData` marks an authenticated Telegram host.
 * Never throws.
 */
export function isTelegramWebApp(env: TelegramEnv): boolean {
  return Boolean(
    env.webApp && typeof env.webApp.initData === 'string' && env.webApp.initData.length > 0,
  );
}

/** CSS custom properties mapped from Telegram's `themeParams` (with fallbacks). */
export interface TelegramThemeCss {
  '--tg-bg': string;
  '--tg-text': string;
  '--tg-hint': string;
  '--tg-link': string;
  '--tg-button': string;
  '--tg-button-text': string;
  /** `'light'` or `'dark'`. */
  colorScheme: string;
}

/**
 * Resolve the Telegram theme into CSS variables. Falling back to Telegram's
 * documented defaults keeps the app readable even if `themeParams` is partial.
 */
export function resolveTelegramTheme(webApp: TelegramWebAppLike): TelegramThemeCss {
  const params = webApp.themeParams ?? {};
  const colorScheme = webApp.colorScheme === 'dark' ? 'dark' : 'light';
  const dark = colorScheme === 'dark';
  return {
    '--tg-bg': params.bg_color ?? (dark ? '#1c1c1e' : '#ffffff'),
    '--tg-text': params.text_color ?? (dark ? '#ffffff' : '#000000'),
    '--tg-hint': params.hint_color ?? (dark ? '#8e8e93' : '#999999'),
    '--tg-link': params.link_color ?? '#2481cc',
    '--tg-button': params.button_color ?? '#2481cc',
    '--tg-button-text': params.button_text_color ?? '#ffffff',
    colorScheme,
  };
}

/** Minimal element surface for applying theme variables. */
export interface ThemeTarget {
  style: { setProperty(name: string, value: string): void };
}

/** Apply resolved Telegram colours onto an element's inline style. */
export function applyTelegramTheme(theme: TelegramThemeCss, target: ThemeTarget): void {
  for (const [name, value] of Object.entries(theme)) {
    if (name === 'colorScheme') {
      continue;
    }
    target.style.setProperty(name, value);
  }
}

/**
 * Adopt the SDK theme once and keep it in sync with `themeChanged`.
 * Returns an unsubscribe function; a no-op without the SDK. Never throws.
 */
export function initTelegramTheme(env: TelegramEnv, target: ThemeTarget): () => void {
  if (!isTelegramWebApp(env) || !env.webApp) {
    return () => {};
  }
  const webApp = env.webApp;
  const apply = () => applyTelegramTheme(resolveTelegramTheme(webApp), target);
  apply();
  webApp.onEvent?.('themeChanged', apply);
  return () => webApp.offEvent?.('themeChanged', apply);
}

/**
 * Wire the Telegram BackButton to app navigation.
 *
 * The button is shown exactly when the current route is not Home; clicking it
 * returns to Home (via `router.goTo('home')`). Without the SDK this is a no-op
 * that returns an inert teardown, so a regular browser is unaffected.
 */
export function initTelegramBackButton(
  env: TelegramEnv,
  route: Route,
  goHome: () => void,
): () => void {
  if (!isTelegramWebApp(env) || !env.webApp?.BackButton) {
    return () => {};
  }
  const backButton = env.webApp.BackButton;
  const shouldShow = route.view !== 'home';
  if (shouldShow) {
    backButton.show?.();
  } else {
    backButton.hide?.();
  }
  const handler = () => goHome();
  backButton.onClick?.(handler);
  return () => {
    backButton.offClick?.(handler);
    // The BackButton belongs to the chat chrome, not this app: hide it on teardown.
    backButton.hide?.();
  };
}

/**
 * One-shot SDK boot: expand the Mini App, mark it ready and apply the theme.
 * No-op outside Telegram; never throws.
 */
export function initTelegramWebApp(env: TelegramEnv, target: ThemeTarget): () => void {
  if (!isTelegramWebApp(env) || !env.webApp) {
    return () => {};
  }
  env.webApp.expand?.();
  env.webApp.ready?.();
  return initTelegramTheme(env, target);
}
