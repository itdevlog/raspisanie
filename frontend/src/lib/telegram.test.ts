import { describe, it, expect, vi } from 'vitest';
import {
  applyTelegramTheme,
  buildStartPayload,
  buildTelegramDeepLink,
  decodeStartSegment,
  encodeStartSegment,
  initTelegramBackButton,
  initTelegramTheme,
  initTelegramWebApp,
  isTelegramWebApp,
  parseStartPayload,
  resolveTelegramTheme,
  startPayloadForRoute,
  telegramEnv,
  type TelegramEnv,
  type TelegramWebAppLike,
} from './telegram';
import { HOME_ROUTE, BARE_SCHEDULE_ROUTE, type Route } from './route';

/** A fake `window.Telegram.WebApp`; every field optional for partial SDKs. */
function makeWebApp(overrides: Partial<TelegramWebAppLike> = {}): TelegramWebAppLike {
  return { initData: 'query_id=abc&user=1', ...overrides };
}

describe('isTelegramWebApp', () => {
  it('is true when the SDK and initData are both present', () => {
    expect(isTelegramWebApp({ webApp: makeWebApp() })).toBe(true);
  });

  it('is false without the SDK (regular browser)', () => {
    expect(isTelegramWebApp({})).toBe(false);
    expect(isTelegramWebApp({ webApp: undefined })).toBe(false);
  });

  it('is false when the WebApp object exists but initData is empty', () => {
    expect(isTelegramWebApp({ webApp: { initData: '' } })).toBe(false);
    expect(isTelegramWebApp({ webApp: { colorScheme: 'dark' } })).toBe(false);
  });
});

describe('telegramEnv', () => {
  it('reads window.Telegram.WebApp when present', () => {
    const webApp = makeWebApp();
    const win = { Telegram: { WebApp: webApp } } as unknown as Window;
    expect(telegramEnv(win).webApp).toBe(webApp);
  });

  it('returns an undefined webApp in a plain browser', () => {
    expect(telegramEnv({} as Window).webApp).toBeUndefined();
  });
});

describe('resolveTelegramTheme / applyTelegramTheme', () => {
  it('maps themeParams onto CSS variables', () => {
    const theme = resolveTelegramTheme({
      colorScheme: 'dark',
      themeParams: { bg_color: '#101010', text_color: '#eeeeee', link_color: '#33aaff' },
    });
    expect(theme.colorScheme).toBe('dark');
    expect(theme['--tg-bg']).toBe('#101010');
    expect(theme['--tg-text']).toBe('#eeeeee');
    expect(theme['--tg-link']).toBe('#33aaff');
    // Missing params fall back to sane defaults rather than `undefined`.
    expect(theme['--tg-hint']).toBeTruthy();
  });

  it('defaults to light and writes only colour properties', () => {
    const style = { setProperty: vi.fn() };
    applyTelegramTheme(resolveTelegramTheme({ themeParams: {} }), { style });
    const names = style.setProperty.mock.calls.map((call) => call[0]);
    expect(names).toContain('--tg-bg');
    expect(names).not.toContain('colorScheme');
  });
});

describe('initTelegramTheme / initTelegramWebApp', () => {
  it('applies the theme and subscribes to themeChanged when the SDK is present', () => {
    const onEvent = vi.fn();
    const offEvent = vi.fn();
    const expand = vi.fn();
    const ready = vi.fn();
    const env: TelegramEnv = {
      webApp: makeWebApp({
        onEvent,
        offEvent,
        expand,
        ready,
        themeParams: { bg_color: '#000000' },
      }),
    };
    const style = { setProperty: vi.fn() };

    const unsubscribe = initTelegramWebApp(env, { style });

    expect(expand).toHaveBeenCalled();
    expect(ready).toHaveBeenCalled();
    expect(style.setProperty).toHaveBeenCalledWith('--tg-bg', '#000000');
    expect(onEvent).toHaveBeenCalledWith('themeChanged', expect.any(Function));

    unsubscribe();
    expect(offEvent).toHaveBeenCalledWith('themeChanged', expect.any(Function));
  });

  it('is a no-op without the SDK', () => {
    const style = { setProperty: vi.fn() };
    const unsubscribe = initTelegramWebApp({}, { style });
    expect(style.setProperty).not.toHaveBeenCalled();
    expect(() => unsubscribe()).not.toThrow();
  });

  it('initTelegramTheme ignores a partial SDK without throwing', () => {
    const style = { setProperty: vi.fn() };
    expect(() => initTelegramTheme({ webApp: { initData: 'x' } }, { style })).not.toThrow();
    expect(style.setProperty).toHaveBeenCalled();
  });
});

describe('initTelegramBackButton', () => {
  it('shows the button off Home and routes clicks to home', () => {
    const show = vi.fn();
    const hide = vi.fn();
    const onClick = vi.fn();
    const offClick = vi.fn();
    const env: TelegramEnv = {
      webApp: makeWebApp({ BackButton: { show, hide, onClick, offClick } }),
    };
    const goHome = vi.fn();

    const schedule: Route = {
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: null,
    };
    const unsubscribe = initTelegramBackButton(env, schedule, goHome);

    expect(show).toHaveBeenCalled();
    expect(hide).not.toHaveBeenCalled();

    const handler = onClick.mock.calls[0][0] as () => void;
    handler();
    expect(goHome).toHaveBeenCalled();

    unsubscribe();
    expect(offClick).toHaveBeenCalledWith(handler);
    expect(hide).toHaveBeenCalled();
  });

  it('hides the button on Home', () => {
    const show = vi.fn();
    const hide = vi.fn();
    const env: TelegramEnv = { webApp: makeWebApp({ BackButton: { show, hide } }) };
    initTelegramBackButton(env, HOME_ROUTE, vi.fn());
    expect(hide).toHaveBeenCalled();
    expect(show).not.toHaveBeenCalled();
  });

  it('is a no-op in a regular browser', () => {
    const goHome = vi.fn();
    const unsubscribe = initTelegramBackButton({}, BARE_SCHEDULE_ROUTE, goHome);
    expect(() => unsubscribe()).not.toThrow();
    expect(goHome).not.toHaveBeenCalled();
  });
});

describe('start payload', () => {
  it('round-trips school/kind/name/date through base64url', () => {
    const payload = buildStartPayload({
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: '07.09.2026',
    });
    expect(payload).toBeTruthy();
    expect(parseStartPayload(payload!)).toEqual({
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: '07.09.2026',
    });
  });

  it('keeps the payload URL-safe and within Telegram’s 64-byte limit', () => {
    const payload = buildStartPayload({ school: 'gym-1', kind: 'teacher', name: 'Иванов И.И.' })!;
    expect(payload).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(new TextEncoder().encode(payload).length).toBeLessThanOrEqual(64);
  });

  it('drops the date when absent', () => {
    const parsed = parseStartPayload(
      buildStartPayload({ school: 'gym1', kind: 'room', name: '101' })!,
    );
    expect(parsed?.date).toBeNull();
    expect(parsed?.kind).toBe('room');
  });

  it('returns null when there is no school or name', () => {
    expect(buildStartPayload({ school: '', kind: 'class', name: '5А' })).toBeNull();
    expect(buildStartPayload({ school: 'gym1', kind: 'class', name: '' })).toBeNull();
  });

  it('returns null when the encoded payload would exceed 64 bytes', () => {
    expect(buildStartPayload({ school: 'x'.repeat(100), kind: 'class', name: 'y' })).toBeNull();
  });

  it('parseStartPayload rejects malformed payloads', () => {
    expect(parseStartPayload('nope')).toBeNull();
    expect(parseStartPayload('s__only')).toBeNull();
    expect(parseStartPayload('x__AAAA__c__AAAA')).toBeNull();
  });

  it('startPayloadForRoute encodes a schedule route only', () => {
    const route: Route = {
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: '07.09.2026',
    };
    expect(parseStartPayload(startPayloadForRoute(route)!)).toMatchObject({
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: '07.09.2026',
    });
    expect(startPayloadForRoute(HOME_ROUTE)).toBeNull();
    expect(startPayloadForRoute(BARE_SCHEDULE_ROUTE)).toBeNull();
  });

  it('base64url encode/decode round-trips UTF-8', () => {
    const token = encodeStartSegment('Гимназия №1 «А»');
    expect(token).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(decodeStartSegment(token)).toBe('Гимназия №1 «А»');
  });
});

describe('buildTelegramDeepLink', () => {
  it('builds a t.me deep link with the start payload', () => {
    const payload = buildStartPayload({ school: 'gym1', kind: 'class', name: '5А' })!;
    const url = buildTelegramDeepLink('raspisanie_bot', payload);
    expect(url).toBe(`https://t.me/raspisanie_bot?start=${encodeURIComponent(payload)}`);
    expect(url).toContain('?start=');
  });

  it('tolerates a leading @', () => {
    expect(buildTelegramDeepLink('@raspisanie_bot', 's__AAAA')).toBe(
      'https://t.me/raspisanie_bot?start=s__AAAA',
    );
  });

  it('returns null when the bot username is unset (control hidden)', () => {
    expect(buildTelegramDeepLink('', 's__AAAA')).toBeNull();
    expect(buildTelegramDeepLink(undefined, 's__AAAA')).toBeNull();
    expect(buildTelegramDeepLink(null, 's__AAAA')).toBeNull();
    expect(buildTelegramDeepLink('   ', 's__AAAA')).toBeNull();
  });

  it('returns null without a payload', () => {
    expect(buildTelegramDeepLink('raspisanie_bot', '')).toBeNull();
  });
});
