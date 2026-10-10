// frontend/src/lib/stores/settings.svelte.ts
//
// User preferences persisted to localStorage. The store is deliberately
// framework-light: Svelte 5 runes (`$state`) give components reactive reads
// while keeping the module plain and directly testable (a factory lets tests
// inject an isolated {@link StorageLike} and a fake theme target).
//
// `apply()` mirrors the chosen skin/accent/font onto `<html>` as
// `data-skin`/`data-accent`/`data-font`, which `app.css` turns into token sets.
// The app calls `apply()` once at start and again whenever a setting changes.

import { readJson, removeKey, type StorageLike, writeJson } from './persisted';

const SETTINGS_KEY = 'settings';

/** Visual skin presets. `classic` reproduces the original Nikasoft look. */
export type Skin = 'classic' | 'minimal' | 'dark' | 'contrast';
/** Accent colour choice; mapped to the semantic accent tokens in `app.css`. */
export type Accent = 'blue' | 'green' | 'purple';
/** Base font-size choice. */
export type FontSize = 'normal' | 'large';
/** The section offered first when the app opens. */
export type DefaultKind = 'class' | 'teacher';

/** Persisted user preferences. */
export interface Settings {
  skin: Skin;
  accent: Accent;
  fontSize: FontSize;
  defaultKind: DefaultKind;
  /**
   * Strike through subject-less "free" lessons. `null` means "follow the
   * school's `STRIKEOUT_FREE_LSN` feature flag" (the pre-settings behavior);
   * `true`/`false` are an explicit user override.
   */
  strikeoutFreeLsn: boolean | null;
  /** Show the lesson number and time in the day/week rows. */
  showLessonTime: boolean;
}

/** Human-readable labels, shared by the Settings screen and its tests. */
export const SKIN_LABELS: Record<Skin, string> = {
  classic: 'Классика',
  minimal: 'Минимализм',
  dark: 'Тёмная',
  contrast: 'Контрастная',
};

export const ACCENT_LABELS: Record<Accent, string> = {
  blue: 'Синий',
  green: 'Зелёный',
  purple: 'Фиолетовый',
};

export const FONT_LABELS: Record<FontSize, string> = {
  normal: 'Обычный',
  large: 'Крупный',
};

export const DEFAULT_KIND_LABELS: Record<DefaultKind, string> = {
  class: 'Классы',
  teacher: 'Учителя',
};

/** Fresh-install defaults: the current Nikasoft look, blue, follow school. */
export const DEFAULT_SETTINGS: Settings = {
  skin: 'classic',
  accent: 'blue',
  fontSize: 'normal',
  defaultKind: 'class',
  strikeoutFreeLsn: null,
  showLessonTime: true,
};

const SKINS: readonly Skin[] = ['classic', 'minimal', 'dark', 'contrast'];
const ACCENTS: readonly Accent[] = ['blue', 'green', 'purple'];
const FONT_SIZES: readonly FontSize[] = ['normal', 'large'];
const DEFAULT_KINDS: readonly DefaultKind[] = ['class', 'teacher'];

/** Element that receives the `data-*` theme attributes (defaults to `<html>`). */
export interface ThemeAttributeTarget {
  setAttribute(name: string, value: string): void;
}

function pick<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return typeof value === 'string' && (allowed as readonly string[]).includes(value)
    ? (value as T)
    : fallback;
}

/**
 * Keep only well-formed fields; anything malformed falls back to the default so
 * a corrupt/hand-edited localStorage value can never break the UI.
 */
function sanitizeSettings(raw: unknown): Settings {
  if (typeof raw !== 'object' || raw === null) {
    return { ...DEFAULT_SETTINGS };
  }
  const obj = raw as Record<string, unknown>;
  let strikeoutFreeLsn: boolean | null = null;
  if (typeof obj.strikeoutFreeLsn === 'boolean') {
    strikeoutFreeLsn = obj.strikeoutFreeLsn;
  }
  return {
    skin: pick(obj.skin, SKINS, DEFAULT_SETTINGS.skin),
    accent: pick(obj.accent, ACCENTS, DEFAULT_SETTINGS.accent),
    fontSize: pick(obj.fontSize, FONT_SIZES, DEFAULT_SETTINGS.fontSize),
    defaultKind: pick(obj.defaultKind, DEFAULT_KINDS, DEFAULT_SETTINGS.defaultKind),
    strikeoutFreeLsn,
    showLessonTime:
      typeof obj.showLessonTime === 'boolean'
        ? obj.showLessonTime
        : DEFAULT_SETTINGS.showLessonTime,
  };
}

function defaultThemeTarget(): ThemeAttributeTarget | null {
  return typeof document === 'undefined' ? null : document.documentElement;
}

/**
 * Reactive settings store. All mutations persist immediately; reads are
 * reactive inside a Svelte effect/template. The app uses {@link settings}.
 */
export function createSettingsStore(storage?: StorageLike | null) {
  let state = $state<Settings>(sanitizeSettings(readJson<unknown>(SETTINGS_KEY, null, storage)));

  function persist(next: Settings): void {
    state = next;
    writeJson(SETTINGS_KEY, next, storage);
  }

  return {
    /** Full current settings (reactive). */
    get current(): Settings {
      return state;
    },
    get skin(): Skin {
      return state.skin;
    },
    get accent(): Accent {
      return state.accent;
    },
    get fontSize(): FontSize {
      return state.fontSize;
    },
    get defaultKind(): DefaultKind {
      return state.defaultKind;
    },
    get strikeoutFreeLsn(): boolean | null {
      return state.strikeoutFreeLsn;
    },
    get showLessonTime(): boolean {
      return state.showLessonTime;
    },
    setSkin(skin: Skin): void {
      persist({ ...state, skin });
    },
    setAccent(accent: Accent): void {
      persist({ ...state, accent });
    },
    setFontSize(fontSize: FontSize): void {
      persist({ ...state, fontSize });
    },
    setDefaultKind(defaultKind: DefaultKind): void {
      persist({ ...state, defaultKind });
    },
    /** Set an explicit strike-through override, or `null` to follow the school. */
    setStrikeoutFreeLsn(strikeoutFreeLsn: boolean | null): void {
      persist({ ...state, strikeoutFreeLsn });
    },
    setShowLessonTime(showLessonTime: boolean): void {
      persist({ ...state, showLessonTime });
    },
    /**
     * Mirror the current settings onto the theme target (defaults to `<html>`)
     * as `data-skin`/`data-accent`/`data-font`. A no-op without a DOM.
     */
    apply(target?: ThemeAttributeTarget): void {
      const el = target ?? defaultThemeTarget();
      if (!el) {
        return;
      }
      el.setAttribute('data-skin', state.skin);
      el.setAttribute('data-accent', state.accent);
      el.setAttribute('data-font', state.fontSize);
    },
    /** Restore defaults and drop the persisted key. */
    reset(): void {
      state = { ...DEFAULT_SETTINGS };
      removeKey(SETTINGS_KEY, storage);
    },
  };
}

export type SettingsStore = ReturnType<typeof createSettingsStore>;

/** App-level singleton persisted under the default `localStorage`. */
export const settings: SettingsStore = createSettingsStore();
