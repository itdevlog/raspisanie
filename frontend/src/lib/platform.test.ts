import { describe, it, expect, vi } from 'vitest';
import { browserEnv } from './platform';

/**
 * `browserEnv` is the only place the router touches `window`/`history`, so its
 * adapter contract is worth pinning directly: the router relies on `origin` and
 * on `addPopStateListener` returning a working unsubscribe.
 */
function fakeWindow(origin = 'https://rasp.example.ru') {
  const location = { pathname: '/s/gym1/class/5%D0%90', search: '?date=05.10.2026', origin };
  const history = { pushState: vi.fn(), replaceState: vi.fn() };
  const addEventListener = vi.fn();
  const removeEventListener = vi.fn();
  const win = {
    location,
    history,
    addEventListener,
    removeEventListener,
  } as unknown as Window;
  return { win, location, history, addEventListener, removeEventListener };
}

describe('browserEnv', () => {
  it('exposes the injected window location and history', () => {
    const { win, location, history } = fakeWindow();
    const env = browserEnv(win);

    expect(env.location).toBe(location);
    expect(env.history).toBe(history);
  });

  it('derives origin from location.origin', () => {
    expect(browserEnv(fakeWindow('https://other.example').win).origin).toBe(
      'https://other.example',
    );
    // A file/relative context reports an empty origin and must be passed through.
    expect(browserEnv(fakeWindow('').win).origin).toBe('');
  });

  it('subscribes to popstate and returns an unsubscribe that detaches the same listener', () => {
    const { win, addEventListener, removeEventListener } = fakeWindow();
    const env = browserEnv(win);
    const listener = vi.fn();

    const off = env.addPopStateListener(listener);

    expect(addEventListener).toHaveBeenCalledWith('popstate', listener);
    expect(removeEventListener).not.toHaveBeenCalled();

    off();

    const [, registered] = addEventListener.mock.calls[0];
    const [, removed] = removeEventListener.mock.calls[0];
    expect(removeEventListener).toHaveBeenCalledWith('popstate', listener);
    // The exact same function reference must be removed, or the listener leaks.
    expect(removed).toBe(registered);
  });
});
