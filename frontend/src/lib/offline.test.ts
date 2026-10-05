import { describe, it, expect, vi } from 'vitest';
import {
  FROM_CACHE_HEADER,
  isFromCache,
  isServiceWorkerOfflineMessage,
  offlineState,
  watchConnectivity,
  watchServiceWorkerCache,
  type ConnectivityEnv,
} from './offline';

describe('offlineState', () => {
  it('prioritises hard offline over cached data', () => {
    expect(offlineState({ online: false, fromCache: true })).toEqual({
      tone: 'offline',
      title: 'Нет подключения к сети',
      detail: 'Показаны последние загруженные данные.',
    });
  });

  it('reports cached data when online but the SW served from TTL', () => {
    expect(offlineState({ online: true, fromCache: true })).toEqual({
      tone: 'cached',
      title: 'Данные из кэша',
      detail: 'Расписание может быть не самым свежим.',
    });
  });

  it('shows nothing when online and fresh', () => {
    expect(offlineState({ online: true, fromCache: false })).toBeNull();
  });
});

describe('isFromCache', () => {
  it('detects the SW marker header', () => {
    const response = new Response('{}', { headers: { [FROM_CACHE_HEADER]: '1' } });
    expect(isFromCache(response)).toBe(true);
    expect(isFromCache(new Response('{}'))).toBe(false);
  });

  it('is false for null/undefined', () => {
    expect(isFromCache(null)).toBe(false);
    expect(isFromCache(undefined)).toBe(false);
  });
});

describe('watchConnectivity', () => {
  function makeEnv(initial: boolean) {
    let online = initial;
    const listeners = { online: new Set<() => void>(), offline: new Set<() => void>() };
    const env: ConnectivityEnv = {
      get online() {
        return online;
      },
      addEventListener(type, listener) {
        listeners[type].add(listener);
      },
      removeEventListener(type, listener) {
        listeners[type].delete(listener);
      },
    };
    return {
      env,
      set(next: boolean) {
        online = next;
        listeners[next ? 'online' : 'offline'].forEach((listener) => listener());
      },
      listenerCount: () => listeners.online.size + listeners.offline.size,
    };
  }

  it('fires immediately with the current state and on changes', () => {
    const { env, set } = makeEnv(true);
    const listener = vi.fn();

    const unsubscribe = watchConnectivity(env, listener);
    expect(listener).toHaveBeenCalledWith(true);

    set(false);
    expect(listener).toHaveBeenLastCalledWith(false);
    unsubscribe();
  });

  it('unsubscribes both listeners', () => {
    const { env, listenerCount } = makeEnv(true);
    const unsubscribe = watchConnectivity(env, vi.fn());
    unsubscribe();
    expect(listenerCount()).toBe(0);
  });
});

describe('isServiceWorkerOfflineMessage', () => {
  it('accepts the two known message types', () => {
    expect(isServiceWorkerOfflineMessage({ type: 'SCHEDULE_FROM_CACHE' })).toBe(true);
    expect(isServiceWorkerOfflineMessage({ type: 'SCHEDULE_OFFLINE' })).toBe(true);
  });

  it('rejects arbitrary payloads', () => {
    expect(isServiceWorkerOfflineMessage(undefined)).toBe(false);
    expect(isServiceWorkerOfflineMessage(null)).toBe(false);
    expect(isServiceWorkerOfflineMessage('SCHEDULE_OFFLINE')).toBe(false);
    expect(isServiceWorkerOfflineMessage({ type: 'OTHER' })).toBe(false);
  });
});

describe('watchServiceWorkerCache', () => {
  it('maps SW messages to a fromCache boolean', () => {
    let handler: ((event: MessageEvent) => void) | undefined;
    const container = {
      addEventListener: (_type: 'message', listener: (event: MessageEvent) => void) => {
        handler = listener;
      },
      removeEventListener: vi.fn(),
    };
    const listener = vi.fn();

    const unsubscribe = watchServiceWorkerCache(container, listener);

    handler?.({ data: { type: 'SCHEDULE_FROM_CACHE' } } as MessageEvent);
    expect(listener).toHaveBeenLastCalledWith(true);

    handler?.({ data: { type: 'SCHEDULE_OFFLINE' } } as MessageEvent);
    expect(listener).toHaveBeenLastCalledWith(false);

    handler?.({ data: { type: 'UNRELATED' } } as MessageEvent);
    expect(listener).toHaveBeenCalledTimes(2);

    unsubscribe();
    expect(container.removeEventListener).toHaveBeenCalled();
  });

  it('is a safe no-op without a container', () => {
    expect(() => watchServiceWorkerCache(undefined, vi.fn())()).not.toThrow();
  });
});
