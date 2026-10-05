import { describe, it, expect, beforeEach } from 'vitest';
import { createSelectionStore } from './selection.svelte';
import { readJson, writeJson, removeKey, STORAGE_PREFIX } from './persisted';

const ENTITY_KEY = 'selected_entity';

beforeEach(() => {
  localStorage.clear();
});

describe('selection store', () => {
  it('starts empty when nothing is persisted', () => {
    const store = createSelectionStore(localStorage);
    expect(store.current).toEqual({ schoolId: null, kind: 'class', name: null });
    expect(store.isComplete).toBe(false);
  });

  it('persists the school and entity to localStorage (round-trip)', () => {
    const first = createSelectionStore(localStorage);
    first.selectSchool('gym1');
    first.selectEntity('class', '5А');

    // A fresh instance rehydrates the same selection from localStorage.
    const second = createSelectionStore(localStorage);
    expect(second.current).toEqual({ schoolId: 'gym1', kind: 'class', name: '5А' });
    expect(second.isComplete).toBe(true);
  });

  it('clears the entity when the school changes', () => {
    const store = createSelectionStore(localStorage);
    store.selectSchool('gym1');
    store.selectEntity('teacher', 'Иванов');
    store.selectSchool('gym2');

    expect(store.current).toEqual({ schoolId: 'gym2', kind: 'teacher', name: null });
    expect(store.isComplete).toBe(false);
  });

  it('supports teacher/room kinds', () => {
    const store = createSelectionStore(localStorage);
    store.selectSchool('gym1');
    store.selectEntity('room', '101');
    expect(store.kind).toBe('room');
    expect(store.name).toBe('101');
  });

  it('selectKind switches kind and clears the name, preserving the school', () => {
    const store = createSelectionStore(localStorage);
    store.selectSchool('gym1');
    store.selectEntity('class', '5А');

    store.selectKind('teacher');

    expect(store.current).toEqual({ schoolId: 'gym1', kind: 'teacher', name: null });
    expect(store.isComplete).toBe(false);
  });

  it('clears state and persisted data', () => {
    const store = createSelectionStore(localStorage);
    store.selectSchool('gym1');
    store.selectEntity('class', '5А');
    store.clear();

    expect(store.current).toEqual({ schoolId: null, kind: 'class', name: null });
    expect(localStorage.getItem(STORAGE_PREFIX + ENTITY_KEY)).toBeNull();
  });

  it('ignores corrupt persisted JSON', () => {
    localStorage.setItem(STORAGE_PREFIX + ENTITY_KEY, '{not json');
    const store = createSelectionStore(localStorage);
    expect(store.current).toEqual({ schoolId: null, kind: 'class', name: null });
  });

  it('sanitizes unknown persisted kinds/values', () => {
    localStorage.setItem(
      STORAGE_PREFIX + ENTITY_KEY,
      JSON.stringify({ schoolId: 42, kind: 'bogus', name: null }),
    );
    const store = createSelectionStore(localStorage);
    expect(store.current).toEqual({ schoolId: null, kind: 'class', name: null });
  });

  it('rejects empty-string school/name and non-string values', () => {
    localStorage.setItem(
      STORAGE_PREFIX + ENTITY_KEY,
      JSON.stringify({ schoolId: '', kind: 'room', name: 7 }),
    );
    const store = createSelectionStore(localStorage);
    // An empty school is "not selected"; a non-string name falls back to null.
    expect(store.current).toEqual({ schoolId: null, kind: 'room', name: null });
    expect(store.isComplete).toBe(false);
  });

  it('keeps a valid persisted school even when the kind is unknown', () => {
    localStorage.setItem(
      STORAGE_PREFIX + ENTITY_KEY,
      JSON.stringify({ schoolId: 'gym1', kind: 'nope', name: '5А' }),
    );
    const store = createSelectionStore(localStorage);
    expect(store.current).toEqual({ schoolId: 'gym1', kind: 'class', name: '5А' });
    // Sanitization is per-field: the valid school survives the bad kind.
    expect(store.isComplete).toBe(true);
  });

  it('falls back to defaults for non-object persisted values', () => {
    for (const raw of ['null', '"gym1"', '42', '[]']) {
      localStorage.setItem(STORAGE_PREFIX + ENTITY_KEY, raw);
      const store = createSelectionStore(localStorage);
      expect(store.current).toEqual({ schoolId: null, kind: 'class', name: null });
    }
  });

  it('works without storage (returns defaults, does not throw)', () => {
    const store = createSelectionStore(null);
    store.selectSchool('gym1');
    store.selectEntity('class', '5А');
    expect(store.current).toEqual({ schoolId: 'gym1', kind: 'class', name: '5А' });
  });
});

describe('persisted helpers', () => {
  it('round-trips JSON values', () => {
    writeJson('thing', { a: 1 }, localStorage);
    expect(readJson('thing', null, localStorage)).toEqual({ a: 1 });
  });

  it('returns the fallback for missing or corrupt values', () => {
    expect(readJson('missing', 'fallback', localStorage)).toBe('fallback');
    localStorage.setItem(STORAGE_PREFIX + 'bad', 'oops');
    expect(readJson('bad', 'fallback', localStorage)).toBe('fallback');
  });

  it('removes keys and tolerates a null storage', () => {
    writeJson('thing', 1, localStorage);
    removeKey('thing', localStorage);
    expect(readJson('thing', null, localStorage)).toBeNull();
    expect(() => writeJson('x', 1, null)).not.toThrow();
    expect(() => removeKey('x', null)).not.toThrow();
  });
});
