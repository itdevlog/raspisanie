import { describe, it, expect, beforeEach } from 'vitest';
import { createFavoritesStore } from './favorites.svelte';
import { STORAGE_PREFIX } from './persisted';

const FAVORITES_KEY = 'favorites';

beforeEach(() => {
  localStorage.clear();
});

describe('favorites store', () => {
  it('starts empty when nothing is persisted', () => {
    const store = createFavoritesStore(localStorage);
    expect(store.all).toEqual([]);
    expect(store.has('gym1', 'class', '5А')).toBe(false);
  });

  it('adds a favorite and persists it across instances', () => {
    const first = createFavoritesStore(localStorage);
    first.add('gym1', 'class', '5А');

    const second = createFavoritesStore(localStorage);
    expect(second.all).toEqual([{ schoolId: 'gym1', kind: 'class', name: '5А' }]);
    expect(second.has('gym1', 'class', '5А')).toBe(true);
  });

  it('keeps class, teacher and room favorites side by side', () => {
    const store = createFavoritesStore(localStorage);
    store.add('gym1', 'class', '5А');
    store.add('gym1', 'teacher', 'Иванов И.И.');
    store.add('gym1', 'room', '101');

    expect(store.has('gym1', 'class', '5А')).toBe(true);
    expect(store.has('gym1', 'teacher', 'Иванов И.И.')).toBe(true);
    expect(store.has('gym1', 'room', '101')).toBe(true);
    // Same name in another kind is a distinct favorite.
    expect(store.has('gym1', 'teacher', '5А')).toBe(false);
  });

  it('is idempotent: adding the same entity twice does not duplicate it', () => {
    const store = createFavoritesStore(localStorage);
    store.add('gym1', 'class', '5А');
    store.add('gym1', 'class', '5А');
    expect(store.all).toHaveLength(1);
  });

  it('removes a favorite and drops it from storage', () => {
    const store = createFavoritesStore(localStorage);
    store.add('gym1', 'class', '5А');
    store.remove('gym1', 'class', '5А');

    expect(store.all).toEqual([]);
    expect(createFavoritesStore(localStorage).all).toEqual([]);
  });

  it('toggle flips the favorite and reports the resulting state', () => {
    const store = createFavoritesStore(localStorage);
    expect(store.toggle('gym1', 'room', '202')).toBe(true);
    expect(store.has('gym1', 'room', '202')).toBe(true);
    expect(store.toggle('gym1', 'room', '202')).toBe(false);
    expect(store.has('gym1', 'room', '202')).toBe(false);
  });

  it('lists favorites filtered by school and optionally by kind', () => {
    const store = createFavoritesStore(localStorage);
    store.add('gym1', 'class', '5А');
    store.add('gym1', 'teacher', 'Иванов');
    store.add('gym2', 'class', '6Б');

    expect(store.list('gym1')).toEqual([
      { schoolId: 'gym1', kind: 'class', name: '5А' },
      { schoolId: 'gym1', kind: 'teacher', name: 'Иванов' },
    ]);
    expect(store.list('gym1', 'class')).toEqual([{ schoolId: 'gym1', kind: 'class', name: '5А' }]);
    expect(store.list('gym2')).toEqual([{ schoolId: 'gym2', kind: 'class', name: '6Б' }]);
  });

  it('clears all favorites and persisted data', () => {
    const store = createFavoritesStore(localStorage);
    store.add('gym1', 'class', '5А');
    store.clear();

    expect(store.all).toEqual([]);
    expect(localStorage.getItem(STORAGE_PREFIX + FAVORITES_KEY)).toBeNull();
  });

  it('ignores corrupt persisted JSON', () => {
    localStorage.setItem(STORAGE_PREFIX + FAVORITES_KEY, '{not json');
    expect(createFavoritesStore(localStorage).all).toEqual([]);
  });

  it('sanitizes and dedupes persisted entries', () => {
    localStorage.setItem(
      STORAGE_PREFIX + FAVORITES_KEY,
      JSON.stringify([
        { schoolId: 'gym1', kind: 'class', name: '5А' },
        { schoolId: 'gym1', kind: 'class', name: '5А' },
        { schoolId: '', kind: 'class', name: '6Б' },
        { schoolId: 'gym1', kind: 'bogus', name: '7В' },
        { schoolId: 'gym1', kind: 'room', name: '' },
        { schoolId: 42, kind: 'room', name: '101' },
        { schoolId: 'gym1', kind: 'teacher', name: 'Иванов' },
        'nope',
      ]),
    );

    expect(createFavoritesStore(localStorage).all).toEqual([
      { schoolId: 'gym1', kind: 'class', name: '5А' },
      { schoolId: 'gym1', kind: 'teacher', name: 'Иванов' },
    ]);
  });

  it('falls back to an empty list for non-array persisted values', () => {
    for (const raw of ['null', '"gym1"', '42', '{}']) {
      localStorage.setItem(STORAGE_PREFIX + FAVORITES_KEY, raw);
      expect(createFavoritesStore(localStorage).all).toEqual([]);
    }
  });

  it('works without storage (returns defaults, does not throw)', () => {
    const store = createFavoritesStore(null);
    store.add('gym1', 'class', '5А');
    expect(store.has('gym1', 'class', '5А')).toBe(true);
  });
});
