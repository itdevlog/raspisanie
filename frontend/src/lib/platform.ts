// frontend/src/lib/platform.ts
//
// Tiny injectable browser adapter for routing. The router store depends on this
// interface (not on `window`/`history` directly), so tests can drive navigation
// with a fake and jsdom quirks stay out of the router logic.

/** Subset of `history` the router uses. */
export interface HistoryLike {
  pushState(state: unknown, title: string, url: string): void;
  replaceState(state: unknown, title: string, url: string): void;
}

/** Subset of `location` the router reads. */
export interface LocationLike {
  pathname: string;
  search: string;
}

/** Minimal `window`/`document` surface for the router. */
export interface BrowserEnv {
  location: LocationLike;
  history: HistoryLike;
  /** Must return an unsubscribe function. */
  addPopStateListener(listener: () => void): () => void;
  /** Absolute origin, e.g. `https://rasp.example.ru`; `''` on a file/relative context. */
  origin: string;
}

/** Build the real environment from the global `window`. */
export function browserEnv(win: Window = window): BrowserEnv {
  return {
    location: win.location,
    history: win.history,
    origin: win.location.origin,
    addPopStateListener(listener) {
      win.addEventListener('popstate', listener);
      return () => win.removeEventListener('popstate', listener);
    },
  };
}
