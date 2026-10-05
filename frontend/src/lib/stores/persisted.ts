// frontend/src/lib/stores/persisted.ts
//
// Small, testable helpers over `localStorage`. Kept framework-agnostic so the
// reactive stores in this folder stay thin and easy to unit-test.

/** Storage key prefix so all app keys are namespaced and easy to spot. */
export const STORAGE_PREFIX = 'raspisanie:';

/** Minimal subset of the Storage interface used here (injectable in tests). */
export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

function defaultStorage(): StorageLike | null {
  try {
    if (typeof localStorage === 'undefined') {
      return null;
    }
    // Probe: privacy modes can expose the object but throw on access.
    const probe = `${STORAGE_PREFIX}__probe__`;
    localStorage.setItem(probe, '1');
    localStorage.removeItem(probe);
    return localStorage;
  } catch {
    return null;
  }
}

/** Read and JSON.parse a value; returns `fallback` on missing/corrupt data. */
export function readJson<T>(key: string, fallback: T, storage?: StorageLike | null): T {
  const store = storage === undefined ? defaultStorage() : storage;
  if (!store) {
    return fallback;
  }
  try {
    const raw = store.getItem(STORAGE_PREFIX + key);
    if (raw === null) {
      return fallback;
    }
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

/** Serialize and write a value. Silently ignores storage failures (quota etc.). */
export function writeJson(key: string, value: unknown, storage?: StorageLike | null): void {
  const store = storage === undefined ? defaultStorage() : storage;
  if (!store) {
    return;
  }
  try {
    store.setItem(STORAGE_PREFIX + key, JSON.stringify(value));
  } catch {
    // Ignore write failures (quota exceeded, privacy mode).
  }
}

/** Remove a persisted value. */
export function removeKey(key: string, storage?: StorageLike | null): void {
  const store = storage === undefined ? defaultStorage() : storage;
  if (!store) {
    return;
  }
  try {
    store.removeItem(STORAGE_PREFIX + key);
  } catch {
    // Ignore.
  }
}
