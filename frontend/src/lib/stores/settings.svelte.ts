// frontend/src/lib/stores/settings.svelte.ts
//
// User preferences persisted to localStorage. The store is deliberately
// framework-light: Svelte 5 runes (`$state`) give components reactive reads
// while keeping the module plain and directly testable (a factory lets tests
// inject an isolated {@link StorageLike} and a fake theme target).
//
// `apply()` mirrors the chosen skin/accent/font/theme onto `<html>` as
// `data-skin`/`data-accent`/`data-font`/`data-theme`, which `app.css` turns into
// token sets. `data-theme` carries the *resolved* light/dark mode: the `theme`
// setting is `system` (follow the OS) or an explicit `light`/`dark`, and only
// the skins that have both palettes (`classic`, `minimal`) react to it.
// The app calls `apply()` once at start, again whenever a setting changes, and
// again when the OS preference flips (see the media-query listener in App).

import { readJson, removeKey, type StorageLike, writeJson } from './persisted';

const SETTINGS_KEY = 'settings';

/** Visual skin presets. `classic` reproduces the original Nikasoft look. */
export type Skin = 'classic' | 'minimal' | 'dark' | 'contrast' | 'youth';
/** Accent colour choice; mapped to the semantic accent tokens in `app.css`. */
export type Accent = 'blue' | 'green' | 'purple';
/** Base font-size choice. */
export type FontSize = 'normal' | 'large';
/** The section offered first when the app opens. */
export type DefaultKind = 'class' | 'teacher';
/** How the real Schedule screen lays out a day. */
export type ScheduleView = 'cards' | 'table' | 'timeline' | 'nownext';
/**
 * Light/dark mode, independent from the {@link Skin}: `system` follows the OS
 * `prefers-color-scheme`, `light`/`dark` pin it. Only the dual-palette skins
 * (`classic`, `minimal`) honour it; `dark`/`youth` are always dark and
 * `contrast` always light, so an explicit skin still wins.
 */
export type ThemeMode = 'system' | 'light' | 'dark';
/** The value `data-theme` actually receives once `system` is resolved. */
export type ResolvedTheme = 'light' | 'dark';

/** Persisted user preferences. */
export interface Settings {
  skin: Skin;
  /** Light/dark mode; see {@link ThemeMode}. */
  theme: ThemeMode;
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
  /** Day layout used by the Schedule screen. */
  scheduleView: ScheduleView;
  /** «Не беспокоить ночью» (Web Push, 22:00–07:00); default on. */
  pushQuietHours: boolean;
  /**
   * Master switch for Web Push notifications. `null` means "the user never
   * chose" (the key predates this flag, or was corrupted): consumers defer to
   * the browser permission instead of forcing the control off (which used to
   * nudge a re-subscribe that could rebind the endpoint). `true`/`false` are an
   * explicit user choice.
   */
  notificationsEnabled: boolean | null;
}

/** Human-readable labels, shared by the Settings screen and its tests. */
export const SKIN_LABELS: Record<Skin, string> = {
  classic: 'Классика',
  minimal: 'Минимализм',
  dark: 'Тёмная',
  contrast: 'Контрастная',
  youth: 'Молодёжный',
};

export const THEME_LABELS: Record<ThemeMode, string> = {
  system: 'Системный',
  light: 'Светлый',
  dark: 'Тёмный',
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

export const SCHEDULE_VIEW_LABELS: Record<ScheduleView, string> = {
  cards: 'Карточки',
  table: 'Таблица',
  timeline: 'Таймлайн',
  nownext: 'Сейчас и далее',
};

/** Fresh-install defaults: the current Nikasoft look, blue, follow school. */
export const DEFAULT_SETTINGS: Settings = {
  skin: 'classic',
  theme: 'system',
  accent: 'blue',
  fontSize: 'normal',
  defaultKind: 'class',
  strikeoutFreeLsn: null,
  showLessonTime: true,
  scheduleView: 'cards',
  pushQuietHours: true,
  notificationsEnabled: null,
};

const SKINS: readonly Skin[] = ['classic', 'minimal', 'dark', 'contrast', 'youth'];
/** Skins that ship both a light and a dark palette (see `app.css`). */
export const DUAL_THEME_SKINS: readonly Skin[] = ['classic', 'minimal'];
const THEMES: readonly ThemeMode[] = ['system', 'light', 'dark'];
const ACCENTS: readonly Accent[] = ['blue', 'green', 'purple'];
const FONT_SIZES: readonly FontSize[] = ['normal', 'large'];
const DEFAULT_KINDS: readonly DefaultKind[] = ['class', 'teacher'];
const SCHEDULE_VIEWS: readonly ScheduleView[] = ['cards', 'table', 'timeline', 'nownext'];

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
    theme: pick(obj.theme, THEMES, DEFAULT_SETTINGS.theme),
    accent: pick(obj.accent, ACCENTS, DEFAULT_SETTINGS.accent),
    fontSize: pick(obj.fontSize, FONT_SIZES, DEFAULT_SETTINGS.fontSize),
    defaultKind: pick(obj.defaultKind, DEFAULT_KINDS, DEFAULT_SETTINGS.defaultKind),
    strikeoutFreeLsn,
    showLessonTime:
      typeof obj.showLessonTime === 'boolean'
        ? obj.showLessonTime
        : DEFAULT_SETTINGS.showLessonTime,
    scheduleView: pick(obj.scheduleView, SCHEDULE_VIEWS, DEFAULT_SETTINGS.scheduleView),
    pushQuietHours:
      typeof obj.pushQuietHours === 'boolean'
        ? obj.pushQuietHours
        : DEFAULT_SETTINGS.pushQuietHours,
    notificationsEnabled:
      typeof obj.notificationsEnabled === 'boolean' ? obj.notificationsEnabled : null,
  };
}

function defaultThemeTarget(): ThemeAttributeTarget | null {
  return typeof document === 'undefined' ? null : document.documentElement;
}

/** Reads the OS "prefer dark" flag; false without a DOM (SSR, unit tests). */
function defaultPrefersDark(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches === true;
}

/** Injectable seams for {@link createSettingsStore}. */
export interface SettingsOptions {
  /**
   * OS "prefer dark" reader, used to resolve the `system` theme mode.
   * Defaults to `matchMedia('(prefers-color-scheme: dark)')`.
   */
  prefersDark?: () => boolean;
}

/**
 * Reactive settings store. All mutations persist immediately; reads are
 * reactive inside a Svelte effect/template. The app uses {@link settings}.
 */
export function createSettingsStore(storage?: StorageLike | null, options: SettingsOptions = {}) {
  const prefersDark = options.prefersDark ?? defaultPrefersDark;
  let state = $state<Settings>(sanitizeSettings(readJson<unknown>(SETTINGS_KEY, null, storage)));

  function persist(next: Settings): void {
    state = next;
    writeJson(SETTINGS_KEY, next, storage);
  }

  /** `system` collapsed to a concrete `light`/`dark`, read at call time. */
  function resolveTheme(): ResolvedTheme {
    return state.theme === 'system' ? (prefersDark() ? 'dark' : 'light') : state.theme;
  }

  return {
    /** Full current settings (reactive). */
    get current(): Settings {
      return state;
    },
    get skin(): Skin {
      return state.skin;
    },
    get theme(): ThemeMode {
      return state.theme;
    },
    /**
     * The light/dark mode the UI actually renders: the `theme` setting with
     * `system` resolved against the OS preference.
     */
    get resolvedTheme(): ResolvedTheme {
      return resolveTheme();
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
    get scheduleView(): ScheduleView {
      return state.scheduleView;
    },
    get pushQuietHours(): boolean {
      return state.pushQuietHours;
    },
    get notificationsEnabled(): boolean | null {
      return state.notificationsEnabled;
    },
    setSkin(skin: Skin): void {
      persist({ ...state, skin });
    },
    setTheme(theme: ThemeMode): void {
      persist({ ...state, theme });
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
    setScheduleView(scheduleView: ScheduleView): void {
      persist({ ...state, scheduleView });
    },
    setPushQuietHours(pushQuietHours: boolean): void {
      persist({ ...state, pushQuietHours });
    },
    setNotificationsEnabled(notificationsEnabled: boolean): void {
      persist({ ...state, notificationsEnabled });
    },
    /**
     * Mirror the current settings onto the theme target (defaults to `<html>`)
     * as `data-skin`/`data-accent`/`data-font`/`data-theme` (`data-theme` is the
     * resolved light/dark mode). A no-op without a DOM.
     */
    apply(target?: ThemeAttributeTarget): void {
      const el = target ?? defaultThemeTarget();
      if (!el) {
        return;
      }
      el.setAttribute('data-skin', state.skin);
      el.setAttribute('data-accent', state.accent);
      el.setAttribute('data-font', state.fontSize);
      el.setAttribute('data-theme', resolveTheme());
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
