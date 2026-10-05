// frontend/src/lib/stores/favorites.svelte.ts
//
// Favorite schedule entities (class / teacher / room) persisted to
// localStorage. This generalizes the W19 selection store: where `selection`
// remembers the *single* currently chosen entity, `favorites` remembers a set
// of entities per school and kind so the user can jump back to them.
//
// Svelte 5 runes (`$state`) give components reactive reads while keeping the
// store a plain, directly testable module. A factory (rather than a module
// singleton) lets tests inject an isolated {@link StorageLike}.

import { readJson, removeKey, type StorageLike, writeJson } from './persisted';
import type { ScheduleKind } from '../api/types';

const FAVORITES_KEY = 'favorites';

/** A saved entity: a named class/teacher/room within a school. */
export interface Favorite {
  schoolId: string;
  kind: ScheduleKind;
  name: string;
}

function isScheduleKind(value: unknown): value is ScheduleKind {
  return value === 'class' || value === 'teacher' || value === 'room';
}

function favoriteKey(favorite: Favorite): string {
  return `${favorite.schoolId}|${favorite.kind}|${favorite.name}`;
}

/**
 * Keep only well-formed entries, dropping duplicates while preserving order.
 * Anything malformed (wrong shape, empty strings, unknown kind) is ignored so a
 * corrupt/hand-edited localStorage value can never break the UI.
 */
function sanitizeFavorites(raw: unknown): Favorite[] {
  if (!Array.isArray(raw)) {
    return [];
  }
  const seen = new Set<string>();
  const result: Favorite[] = [];
  for (const entry of raw) {
    if (typeof entry !== 'object' || entry === null) {
      continue;
    }
    const obj = entry as Record<string, unknown>;
    if (
      typeof obj.schoolId !== 'string' ||
      !obj.schoolId ||
      !isScheduleKind(obj.kind) ||
      typeof obj.name !== 'string' ||
      !obj.name
    ) {
      continue;
    }
    const favorite: Favorite = { schoolId: obj.schoolId, kind: obj.kind, name: obj.name };
    const key = favoriteKey(favorite);
    if (!seen.has(key)) {
      seen.add(key);
      result.push(favorite);
    }
  }
  return result;
}

/**
 * Reactive favorites store.
 *
 * All mutations persist immediately; reads are reactive when used inside a
 * Svelte effect/template. The app uses the default {@link favorites} instance.
 */
export function createFavoritesStore(storage?: StorageLike | null) {
  let state = $state<Favorite[]>(sanitizeFavorites(readJson<unknown>(FAVORITES_KEY, [], storage)));

  function persist(next: Favorite[]): void {
    state = next;
    writeJson(FAVORITES_KEY, next, storage);
  }

  function hasFavorite(schoolId: string, kind: ScheduleKind, name: string): boolean {
    return state.some(
      (favorite) =>
        favorite.schoolId === schoolId && favorite.kind === kind && favorite.name === name,
    );
  }

  function addFavorite(schoolId: string, kind: ScheduleKind, name: string): void {
    if (hasFavorite(schoolId, kind, name)) {
      return;
    }
    persist([...state, { schoolId, kind, name }]);
  }

  function removeFavorite(schoolId: string, kind: ScheduleKind, name: string): void {
    const next = state.filter(
      (favorite) =>
        !(favorite.schoolId === schoolId && favorite.kind === kind && favorite.name === name),
    );
    if (next.length !== state.length) {
      persist(next);
    }
  }

  return {
    /** Every favorite, in insertion order (reactive). */
    get all(): Favorite[] {
      return state;
    },
    /** Favorites for one school, optionally narrowed to a single kind. */
    list(schoolId: string, kind?: ScheduleKind): Favorite[] {
      return state.filter(
        (favorite) =>
          favorite.schoolId === schoolId && (kind === undefined || favorite.kind === kind),
      );
    },
    /** Whether the given entity is already a favorite. */
    has: hasFavorite,
    /** Add a favorite; adding the same entity twice is a no-op. */
    add: addFavorite,
    /** Remove a favorite if present. */
    remove: removeFavorite,
    /** Flip the favorite; returns the resulting state (`true` = now saved). */
    toggle(schoolId: string, kind: ScheduleKind, name: string): boolean {
      if (hasFavorite(schoolId, kind, name)) {
        removeFavorite(schoolId, kind, name);
        return false;
      }
      addFavorite(schoolId, kind, name);
      return true;
    },
    /** Drop all favorites and persisted data. */
    clear(): void {
      state = [];
      removeKey(FAVORITES_KEY, storage);
    },
  };
}

export type FavoritesStore = ReturnType<typeof createFavoritesStore>;

/** App-level singleton persisted under the default `localStorage`. */
export const favorites: FavoritesStore = createFavoritesStore();
