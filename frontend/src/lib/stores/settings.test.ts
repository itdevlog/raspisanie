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
    expect(store.theme).toBe('system');
    expect(store.accent).toBe('blue');
    expect(store.fontSize).toBe('normal');
    expect(store.defaultKind).toBe('class');
    expect(store.strikeoutFreeLsn).toBeNull();
    expect(store.showLessonTime).toBe(true);
    expect(store.scheduleView).toBe('cards');
    expect(store.pushQuietHours).toBe(true);
    expect(store.notificationsEnabled).toBeNull();
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
    store.setScheduleView('timeline');
    store.setPushQuietHours(false);
    store.setNotificationsEnabled(false);

    expect(store.skin).toBe('dark');
    expect(store.accent).toBe('purple');
    expect(store.fontSize).toBe('large');
    expect(store.defaultKind).toBe('teacher');
    expect(store.strikeoutFreeLsn).toBe(false);
    expect(store.showLessonTime).toBe(false);
    expect(store.scheduleView).toBe('timeline');
    expect(store.pushQuietHours).toBe(false);
    expect(store.notificationsEnabled).toBe(false);

    const raw = storage.getItem('raspisanie:settings');
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw as string)).toMatchObject({
      skin: 'dark',
      accent: 'purple',
      fontSize: 'large',
      defaultKind: 'teacher',
      strikeoutFreeLsn: false,
      showLessonTime: false,
      scheduleView: 'timeline',
      pushQuietHours: false,
      notificationsEnabled: false,
    });
  });

  it('persists pushQuietHours across a new store and defaults it on', () => {
    const storage = memoryStorage();
    const store = createSettingsStore(storage);
    expect(store.pushQuietHours).toBe(true);

    store.setPushQuietHours(false);
    expect(createSettingsStore(storage).pushQuietHours).toBe(false);
  });

  it('persists notificationsEnabled across a new store and defaults it to null', () => {
    const storage = memoryStorage();
    const store = createSettingsStore(storage);
    expect(store.notificationsEnabled).toBeNull();

    store.setNotificationsEnabled(true);
    expect(store.notificationsEnabled).toBe(true);
    expect(createSettingsStore(storage).notificationsEnabled).toBe(true);
  });

  it('keeps an explicit notificationsEnabled=false through a reload', () => {
    const storage = memoryStorage();
    const store = createSettingsStore(storage);
    store.setNotificationsEnabled(false);
    expect(store.notificationsEnabled).toBe(false);
    expect(createSettingsStore(storage).notificationsEnabled).toBe(false);
  });

  it('yields null (never chosen) for a non-boolean notificationsEnabled', () => {
    const store = createSettingsStore(
      memoryStorage({ 'raspisanie:settings': JSON.stringify({ notificationsEnabled: 'yes' }) }),
    );
    expect(store.notificationsEnabled).toBeNull();
  });

  it('persists the schedule view across a new store', () => {
    const storage = memoryStorage();
    createSettingsStore(storage).setScheduleView('cards');
    const reloaded = createSettingsStore(storage);
    expect(reloaded.scheduleView).toBe('cards');
  });

  it('re-reads persisted values on a new store', () => {
    const storage = memoryStorage();
    createSettingsStore(storage).setSkin('contrast');
    const reloaded = createSettingsStore(storage);
    expect(reloaded.skin).toBe('contrast');
  });

  it('defaults the theme mode to «Системный» and persists a change', () => {
    const storage = memoryStorage();
    const store = createSettingsStore(storage);
    expect(store.theme).toBe('system');

    store.setTheme('dark');
    expect(store.theme).toBe('dark');
    expect(JSON.parse(storage.getItem('raspisanie:settings') as string)).toMatchObject({
      theme: 'dark',
    });
    expect(createSettingsStore(storage).theme).toBe('dark');
  });

  it('falls back to «Системный» for an unknown stored theme', () => {
    const store = createSettingsStore(
      memoryStorage({ 'raspisanie:settings': JSON.stringify({ theme: 'midnight' }) }),
    );
    expect(store.theme).toBe('system');
  });

  it('resolves «Системный» against the OS preference and pins explicit modes', () => {
    const dark = createSettingsStore(null, { prefersDark: () => true });
    const light = createSettingsStore(null, { prefersDark: () => false });

    expect(dark.resolvedTheme).toBe('dark');
    expect(light.resolvedTheme).toBe('light');

    dark.setTheme('light');
    expect(dark.resolvedTheme).toBe('light');

    light.setTheme('dark');
    expect(light.resolvedTheme).toBe('dark');

    light.setTheme('system');
    expect(light.resolvedTheme).toBe('light');
  });

  it('writes the resolved data-theme alongside skin/accent/font in apply()', () => {
    const store = createSettingsStore(null, { prefersDark: () => true });
    const target: ThemeAttributeTarget = { setAttribute: vi.fn() };

    store.apply(target);
    expect(target.setAttribute).toHaveBeenCalledWith('data-theme', 'dark');

    store.setTheme('light');
    store.apply(target);
    expect(target.setAttribute).toHaveBeenCalledWith('data-theme', 'light');
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
        scheduleView: 'kanban',
      }),
    });
    const store = createSettingsStore(storage);
    expect(store.current).toEqual(DEFAULT_SETTINGS);
    expect(store.scheduleView).toBe('cards');
  });

  it('rolls a stored «compact» scheduleView back to «Карточки» (cards)', () => {
    const store = createSettingsStore(
      memoryStorage({ 'raspisanie:settings': JSON.stringify({ scheduleView: 'compact' }) }),
    );
    expect(store.scheduleView).toBe('cards');
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
    store.setTheme('dark');
    store.setAccent('green');
    store.setNotificationsEnabled(false);

    store.reset();

    expect(store.current).toEqual(DEFAULT_SETTINGS);
    expect(store.theme).toBe('system');
    expect(store.notificationsEnabled).toBeNull();
    expect(storage.getItem('raspisanie:settings')).toBeNull();
  });
});
