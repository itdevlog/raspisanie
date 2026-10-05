// frontend/src/lib/stores/route.svelte.ts
//
// Reactive client-side router (History API). The app URL mirrors the share
// scheme from W16, so a deep link opens the right screen and back/forward work.
//
// The store is a factory (not a module singleton) so tests inject a fake
// {@link BrowserEnv} instead of touching jsdom history. `$state` gives components
// a reactive `route` while keeping the store a plain, directly testable module.

import {
  BARE_SCHEDULE_ROUTE,
  HOME_ROUTE,
  buildViewPath,
  parseLocation,
  type Route,
} from '../route';
import { browserEnv, type BrowserEnv } from '../platform';

/** Router surface used by the app shell and screens. */
export interface RouteStore {
  /** Current parsed route (reactive inside effects/templates). */
  readonly route: Route;
  /** True once {@link start} has parsed the initial location. */
  readonly started: boolean;
  /**
   * Programmatic navigation. Pushes a history entry by default; pass
   * `{ replace: true }` to replace the current one (e.g. redirects).
   */
  navigate(route: Route, options?: { replace?: boolean }): void;
  /**
   * Nav-tab helper: switch to a view. The schedule tab opens the bare view
   * (callers with a chosen entity use {@link navigate} with a share route).
   */
  goTo(view: Route['view']): void;
  /** Parse `env.location` and subscribe to `popstate`. Returns an unsubscribe. */
  start(env?: BrowserEnv): () => void;
}

/**
 * Create a reactive route store bound to a browser environment.
 *
 * `envOverride` is used by tests; when omitted the real `window` is read lazily
 * on {@link RouteStore.start} (so importing the store in a non-DOM context is
 * harmless).
 */
export function createRouteStore(envOverride?: BrowserEnv): RouteStore {
  let env: BrowserEnv | null = envOverride ?? null;
  let route = $state<Route>(HOME_ROUTE);
  let started = $state(false);

  function currentEnv(): BrowserEnv {
    env ??= browserEnv();
    return env;
  }

  function navigate(next: Route, options: { replace?: boolean } = {}): void {
    const target = currentEnv();
    const url = buildViewPath(next);
    if (options.replace) {
      target.history.replaceState({}, '', url);
    } else {
      target.history.pushState({}, '', url);
    }
    route = next;
  }

  function goTo(view: Route['view']): void {
    // Selecting an already-active tab is a no-op (keeps the current URL/selection).
    if (view === route.view) {
      return;
    }
    if (view === 'schedule') {
      navigate({ ...BARE_SCHEDULE_ROUTE });
      return;
    }
    navigate({ view });
  }

  function start(override?: BrowserEnv): () => void {
    if (override) {
      env = override;
    }
    const target = currentEnv();
    // Adopt the entry URL as parsed; deep links open the right screen.
    route = parseLocation(target.location);
    started = true;
    const onPop = () => {
      route = parseLocation(target.location);
    };
    return target.addPopStateListener(onPop);
  }

  return {
    get route() {
      return route;
    },
    get started() {
      return started;
    },
    navigate,
    goTo,
    start,
  };
}

export type { Route };

/** App-level singleton bound lazily to the real `window` on `start()`. */
export const route: RouteStore = createRouteStore();
