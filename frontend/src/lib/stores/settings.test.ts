import { describe, it, expect, vi } from 'vitest';
import {
  DEFAULT_SETTINGS,
  createSettingsStore,
  type ThemeAttributeTarget,
} from './settings.svelte';
import type { StorageLike } from './persisted';

/** Minimal in-memory StorageLike so the store is tested in isolation. */
function memoryStorage(initial: Record<string, string> = {}): StorageLike {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (key) => map.get(key) ?? null,
    setItem: (key, value) => {
      map.set(key, value);
    },
    removeItem: (key) => {
      map.delete(key);
    },
  };
}

describe('settings store', () => {
  it('starts from the defaults when nothing is persisted', () => {
    const store = createSettingsStore(null);
    expect(store.current).toEqual(DEFAULT_SETTINGS);
    expect(store.skin).toBe('classic');
    expect(store.accent).toBe('blue');
    expect(store.fontSize).toBe('normal');
    expect(store.defaultKind).toBe('class');
    expect(store.strikeoutFreeLsn).toBeNull();
    expect(store.showLessonTime).toBe(true);
  });

  it('persists each change under the namespaced key', () => {
    const storage = memoryStorage();
    const store = createSettingsStore(storage);

    store.setSkin('dark');
    store.setAccent('purple');
    store.setFontSize('large');
    store.setDefaultKind('teacher');
    store.setStrikeoutFreeLsn(false);
    store.setShowLessonTime(false);

    expect(store.skin).toBe('dark');
    expect(store.accent).toBe('purple');
    expect(store.fontSize).toBe('large');
    expect(store.defaultKind).toBe('teacher');
    expect(store.strikeoutFreeLsn).toBe(false);
    expect(store.showLessonTime).toBe(false);

    const raw = storage.getItem('raspisanie:settings');
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw as string)).toMatchObject({
      skin: 'dark',
      accent: 'purple',
      fontSize: 'large',
      defaultKind: 'teacher',
      strikeoutFreeLsn: false,
      showLessonTime: false,
    });
  });

  it('re-reads persisted values on a new store', () => {
    const storage = memoryStorage();
    createSettingsStore(storage).setSkin('contrast');
    const reloaded = createSettingsStore(storage);
    expect(reloaded.skin).toBe('contrast');
  });

  it('round-trips the «Молодёжный» (youth) skin through storage and apply()', () => {
    const storage = memoryStorage();
    const store = createSettingsStore(storage);
    store.setSkin('youth');

    expect(store.skin).toBe('youth');
    expect(JSON.parse(storage.getItem('raspisanie:settings') as string)).toMatchObject({
      skin: 'youth',
    });

    const reloaded = createSettingsStore(storage);
    expect(reloaded.skin).toBe('youth');

    const target: ThemeAttributeTarget = { setAttribute: vi.fn() };
    reloaded.apply(target);
    expect(target.setAttribute).toHaveBeenCalledWith('data-skin', 'youth');
  });

  it('sanitizes corrupt / hand-edited values back to safe defaults', () => {
    const storage = memoryStorage({
      'raspisanie:settings': JSON.stringify({
        skin: 'neon',
        accent: 42,
        fontSize: null,
        defaultKind: 'room',
        strikeoutFreeLsn: 'yes',
        showLessonTime: 'no',
      }),
    });
    const store = createSettingsStore(storage);
    expect(store.current).toEqual(DEFAULT_SETTINGS);
  });

  it('applies skin/accent/font as data attributes on the target', () => {
    const store = createSettingsStore(null);
    store.setSkin('minimal');
    store.setAccent('green');
    store.setFontSize('large');

    const target: ThemeAttributeTarget = { setAttribute: vi.fn() };
    store.apply(target);

    expect(target.setAttribute).toHaveBeenCalledWith('data-skin', 'minimal');
    expect(target.setAttribute).toHaveBeenCalledWith('data-accent', 'green');
    expect(target.setAttribute).toHaveBeenCalledWith('data-font', 'large');
  });

  it('resets to the defaults and drops the persisted key', () => {
    const storage = memoryStorage();
    const store = createSettingsStore(storage);
    store.setSkin('dark');
    store.setAccent('green');

    store.reset();

    expect(store.current).toEqual(DEFAULT_SETTINGS);
    expect(storage.getItem('raspisanie:settings')).toBeNull();
  });
});
