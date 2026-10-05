// frontend/src/lib/sw-register.ts
//
// Service-worker registration (W23). Kept tiny and injectable so the guard
// ("browsers without SW support must not throw") is unit-testable without a
// real service worker.
//
// The SW is served from `/service-worker.js` (Vite copies `frontend/public/`
// verbatim into `frontend/dist/`). Scope is the root because the file lives at
// the root of the served directory.

/** Minimum `navigator.serviceWorker` surface used here. */
export interface RegisterableServiceWorkerContainer {
  register(scriptURL: string, options?: { scope?: string }): Promise<unknown>;
}

/**
 * Register the PWA service worker. Returns the registration promise, or `null`
 * when the environment has no service-worker support (`navigator` absent or
 * `serviceWorker` undefined) — callers can safely `await`/ignore the result.
 *
 * A registration failure (e.g. insecure context, HTTP) is propagated; callers
 * that treat the SW as best-effort should `.catch()` it.
 */
export function registerServiceWorker(
  scriptUrl = '/service-worker.js',
  container: RegisterableServiceWorkerContainer | undefined = globalThis.navigator
    ?.serviceWorker,
): Promise<unknown> | null {
  if (!container || typeof container.register !== 'function') {
    return null;
  }
  return container.register(scriptUrl, { scope: '/' });
}

/** True when the current environment can register a service worker. */
export function supportsServiceWorker(
  container: RegisterableServiceWorkerContainer | undefined = globalThis.navigator
    ?.serviceWorker,
): boolean {
  return Boolean(container && typeof container.register === 'function');
}
