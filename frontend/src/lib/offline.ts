// frontend/src/lib/offline.ts
//
// Offline detection for the schedule screen (W23).
//
// Two independent signals feed the offline indicator:
//
//   * `navigator.onLine` + `online`/`offline` events — is the device connected;
//   * the SW's `X-SW-From-Cache` marker on API responses — were the shown
//     schedule bytes served from the TTL cache (i.e. possibly stale).
//
// The module is DOM-touching but every dependency is injectable, so the
// decision logic ({@link offlineState}) is a pure function and easy to test.

/** Pure inputs the indicator renders from. */
export interface OfflineInputs {
  /** `navigator.onLine` (false = the browser believes it is offline). */
  online: boolean;
  /** The SW served the last schedule response from its TTL cache. */
  fromCache: boolean;
  /** The user is viewing a pinned (share-link) date, which may be old. */
  pinned?: boolean;
}

/** What the offline indicator should show; `null` = show nothing. */
export interface OfflineState {
  tone: 'offline' | 'cached';
  title: string;
  detail: string;
}

/**
 * Decide the offline indicator from {@link OfflineInputs}. Pure.
 *
 * Precedence: hard offline beats "cached data" — the message that matters most
 * to the user is that the network is gone.
 */
export function offlineState(inputs: OfflineInputs): OfflineState | null {
  if (!inputs.online) {
    return {
      tone: 'offline',
      title: 'Нет подключения к сети',
      detail: 'Показаны последние загруженные данные.',
    };
  }
  if (inputs.fromCache) {
    return {
      tone: 'cached',
      title: 'Данные из кэша',
      detail: 'Расписание может быть не самым свежим.',
    };
  }
  return null;
}

/** Read the SW cache marker the `fetch` handler adds to cached responses. */
export const FROM_CACHE_HEADER = 'X-SW-From-Cache';

/**
 * Inspect an API `Response` for the SW "from cache" marker. Safe on `null` and
 * on responses without `headers` (e.g. a test double).
 */
export function isFromCache(response: Response | null | undefined): boolean {
  return Boolean(response?.headers?.get?.(FROM_CACHE_HEADER) === '1');
}

/** Minimal `window`/`navigator` surface for connectivity listening. */
export interface ConnectivityEnv {
  online: boolean;
  addEventListener(type: 'online' | 'offline', listener: () => void): void;
  removeEventListener(type: 'online' | 'offline', listener: () => void): void;
}

/** Build the real connectivity environment from the global `window`. */
export function connectivityEnv(win: Window = window): ConnectivityEnv {
  const nav = win.navigator;
  return {
    get online() {
      return nav.onLine;
    },
    addEventListener(type, listener) {
      win.addEventListener(type, listener);
    },
    removeEventListener(type, listener) {
      win.removeEventListener(type, listener);
    },
  };
}

/**
 * Subscribe to connectivity changes. Returns an unsubscribe function. The
 * listener fires immediately with the current state so the caller does not have
 * to prime it separately.
 */
export function watchConnectivity(
  env: ConnectivityEnv,
  listener: (online: boolean) => void,
): () => void {
  const notify = () => listener(env.online);
  env.addEventListener('online', notify);
  env.addEventListener('offline', notify);
  notify();
  return () => {
    env.removeEventListener('online', notify);
    env.removeEventListener('offline', notify);
  };
}

/** Message types the service worker posts to open pages. */
export type ServiceWorkerMessage = 'SCHEDULE_FROM_CACHE' | 'SCHEDULE_OFFLINE';

/** Minimal `ServiceWorkerContainer` surface for message listening. */
export interface MessageableServiceWorkerContainer {
  addEventListener?(type: 'message', listener: (event: MessageEvent) => void): void;
  removeEventListener?(type: 'message', listener: (event: MessageEvent) => void): void;
}

/**
 * True when a `MessageEvent.data` is one of the SW offline-cache signals.
 * Pure; tolerates arbitrary/undefined payloads.
 */
export function isServiceWorkerOfflineMessage(data: unknown): data is { type: ServiceWorkerMessage } {
  if (typeof data !== 'object' || data === null) {
    return false;
  }
  const type = (data as { type?: unknown }).type;
  return type === 'SCHEDULE_FROM_CACHE' || type === 'SCHEDULE_OFFLINE';
}

/**
 * Listen for the SW's `SCHEDULE_FROM_CACHE`/`SCHEDULE_OFFLINE` messages and
 * report whether the currently shown schedule came from the TTL cache. Returns
 * an unsubscribe function (a no-op when the environment cannot listen).
 */
export function watchServiceWorkerCache(
  container: MessageableServiceWorkerContainer | undefined,
  listener: (fromCache: boolean) => void,
): () => void {
  if (!container?.addEventListener) {
    return () => {};
  }
  const handler = (event: MessageEvent) => {
    if (isServiceWorkerOfflineMessage(event.data)) {
      listener(event.data.type === 'SCHEDULE_FROM_CACHE');
    }
  };
  container.addEventListener('message', handler);
  return () => container.removeEventListener?.('message', handler);
}
