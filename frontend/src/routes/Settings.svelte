<script lang="ts">
  // Settings screen (gear in the app header).
  //
  //   * Оформление — skin preset, accent colour, font size (applied to <html>
  //     via the settings store's `apply()`);
  //   * Поведение — default section, free-lesson strike-through override, and
  //     whether to show lesson numbers/times;
  //   * Уведомления — Web Push opt-in/out (reuse of the existing helpers;
  //     class-only MVP);
  //   * Прочее — reset settings, clear the schedule cache.
  import {
    selection as defaultSelection,
    settings as defaultSettings,
    buildShareUrl,
    enablePush,
    disablePush,
    getPermission,
    supportsServiceWorker,
    ACCENT_LABELS,
    DEFAULT_KIND_LABELS,
    FONT_LABELS,
    SKIN_LABELS,
    type Accent,
    type DefaultKind,
    type FontSize,
    type PushResult,
    type SelectionStore,
    type SettingsStore,
    type Skin,
  } from '../lib';
  import StateNotice from '../components/StateNotice.svelte';
  import { untrack } from 'svelte';

  interface Props {
    settings?: SettingsStore;
    selection?: SelectionStore;
    /** Return to the landing screen. */
    onBack?: () => void;
    /**
     * School `STRIKEOUT_FREE_LSN` value, used as the strike-through checkbox's
     * state while the user has no explicit override (`null`).
     */
    schoolStrikeoutFreeLsn?: boolean;
    /** Browser origin used when building the push share link; defaults to `location`. */
    origin?: string;
    /** Injectable push opt-in (tests); defaults to the real {@link enablePush}. */
    pushEnable?: typeof enablePush;
    /** Injectable push opt-out (tests); defaults to the real {@link disablePush}. */
    pushDisable?: typeof disablePush;
    /** Test seam: force whether Web Push UI is available. */
    pushSupported?: boolean;
    /** Test seam: start with notifications already enabled. */
    pushInitiallyOn?: boolean;
    /** Clear the offline schedule cache; defaults to the Cache Storage API. */
    clearCache?: () => Promise<void>;
  }
  let {
    settings = defaultSettings,
    selection = defaultSelection,
    onBack,
    schoolStrikeoutFreeLsn = true,
    origin = typeof window === 'undefined' ? '' : window.location.origin,
    pushEnable = enablePush,
    pushDisable = disablePush,
    pushSupported = undefined,
    pushInitiallyOn = false,
    clearCache = defaultClearCache,
  }: Props = $props();

  const SKINS: Skin[] = ['classic', 'minimal', 'dark', 'contrast', 'youth'];
  const ACCENTS: Accent[] = ['blue', 'green', 'purple'];
  const FONTS: FontSize[] = ['normal', 'large'];
  const DEFAULT_KINDS: DefaultKind[] = ['class', 'teacher'];

  let pushState = $state<'idle' | 'busy' | 'on'>(untrack(() => pushInitiallyOn) ? 'on' : 'idle');
  let pushNotice = $state<string | null>(null);
  let cacheNotice = $state<string | null>(null);
  let resetNotice = $state<string | null>(null);

  // Keep `<html>` in sync while this screen is open (the shell also applies on
  // every settings change, so this is belt-and-braces for standalone use).
  $effect(() => {
    settings.apply();
  });

  const strikeoutChecked = $derived(settings.strikeoutFreeLsn ?? schoolStrikeoutFreeLsn);

  const canUsePush = $derived(
    pushSupported ??
      (supportsServiceWorker() && (typeof window === 'undefined' || 'Notification' in window)),
  );
  const isPushOn = $derived(pushState === 'on' || getPermission() === 'granted');
  /** Push is class-only (MVP) and needs a saved class name. */
  const savedClass = $derived(
    selection.schoolId !== null && selection.kind === 'class' && selection.name !== null,
  );

  function defaultClearCache(): Promise<void> {
    if (typeof caches === 'undefined') {
      return Promise.resolve();
    }
    return caches.keys().then(async (keys) => {
      await Promise.all(keys.map((key) => caches.delete(key)));
    });
  }

  function handleSkinChange(event: Event) {
    settings.setSkin((event.currentTarget as HTMLInputElement).value as Skin);
  }
  function handleAccentChange(event: Event) {
    settings.setAccent((event.currentTarget as HTMLInputElement).value as Accent);
  }
  function handleFontChange(event: Event) {
    settings.setFontSize((event.currentTarget as HTMLInputElement).value as FontSize);
  }
  function handleDefaultKindChange(event: Event) {
    settings.setDefaultKind((event.currentTarget as HTMLInputElement).value as DefaultKind);
  }
  function handleStrikeoutChange(event: Event) {
    settings.setStrikeoutFreeLsn((event.currentTarget as HTMLInputElement).checked);
  }
  function handleShowLessonTimeChange(event: Event) {
    settings.setShowLessonTime((event.currentTarget as HTMLInputElement).checked);
  }

  function handleReset() {
    settings.reset();
    resetNotice = 'Настройки сброшены';
  }

  async function handleClearCache() {
    cacheNotice = null;
    try {
      await clearCache();
      cacheNotice = 'Кэш расписания очищен';
    } catch {
      cacheNotice = 'Не удалось очистить кэш';
    }
  }

  async function handleEnablePush() {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      pushNotice = 'Сначала выберите класс';
      return;
    }
    pushState = 'busy';
    pushNotice = null;
    const url = buildShareUrl(origin, schoolId, 'class', name, null);
    const result: PushResult = await pushEnable({ schoolId, name, kind: 'class', url });
    if (result.ok) {
      pushState = 'on';
    } else {
      pushState = 'idle';
      pushNotice = result.error ?? 'Не удалось включить уведомления';
    }
  }

  async function handleDisablePush() {
    pushState = 'busy';
    pushNotice = null;
    const result = await pushDisable();
    if (result.ok) {
      pushState = 'idle';
      pushNotice = 'Уведомления выключены';
    } else {
      pushState = 'on';
      pushNotice = result.error ?? 'Не удалось выключить уведомления';
    }
  }
</script>

<section class="settings">
  <button
    type="button"
    class="back nika-btn nika-btn-light"
    aria-label="На главную"
    onclick={() => onBack?.()}
  >
    ← на главную
  </button>

  <h2>Настройки</h2>

  <fieldset>
    <legend>Оформление</legend>

    <div class="group" role="radiogroup" aria-label="Тема оформления">
      <span class="group-label">Тема</span>
      {#each SKINS as skin (skin)}
        <label class="choice">
          <input
            type="radio"
            name="skin"
            value={skin}
            checked={settings.skin === skin}
            onchange={handleSkinChange}
          />
          <span>{SKIN_LABELS[skin]}</span>
        </label>
      {/each}
    </div>

    <div class="group" role="radiogroup" aria-label="Цвет акцента">
      <span class="group-label">Цвет</span>
      {#each ACCENTS as accent (accent)}
        <label class="choice">
          <input
            type="radio"
            name="accent"
            value={accent}
            checked={settings.accent === accent}
            onchange={handleAccentChange}
          />
          <span>{ACCENT_LABELS[accent]}</span>
        </label>
      {/each}
    </div>

    <div class="group" role="radiogroup" aria-label="Размер шрифта">
      <span class="group-label">Шрифт</span>
      {#each FONTS as font (font)}
        <label class="choice">
          <input
            type="radio"
            name="font"
            value={font}
            checked={settings.fontSize === font}
            onchange={handleFontChange}
          />
          <span>{FONT_LABELS[font]}</span>
        </label>
      {/each}
    </div>
  </fieldset>

  <fieldset>
    <legend>Поведение</legend>

    <div class="group" role="radiogroup" aria-label="Раздел по умолчанию">
      <span class="group-label">Раздел по умолчанию</span>
      {#each DEFAULT_KINDS as kind (kind)}
        <label class="choice">
          <input
            type="radio"
            name="default-kind"
            value={kind}
            checked={settings.defaultKind === kind}
            onchange={handleDefaultKindChange}
          />
          <span>{DEFAULT_KIND_LABELS[kind]}</span>
        </label>
      {/each}
    </div>

    <label class="toggle">
      <input
        type="checkbox"
        checked={strikeoutChecked}
        onchange={handleStrikeoutChange}
      />
      <span>Зачёркивать свободные уроки</span>
    </label>

    <label class="toggle">
      <input
        type="checkbox"
        checked={settings.showLessonTime}
        onchange={handleShowLessonTimeChange}
      />
      <span>Показывать номер урока и время</span>
    </label>
  </fieldset>

  <fieldset>
    <legend>Уведомления</legend>
    {#if canUsePush}
      <button
        type="button"
        class="push nika-btn nika-btn-light"
        disabled={pushState === 'busy' || (!isPushOn && !savedClass)}
        onclick={isPushOn ? handleDisablePush : handleEnablePush}
      >
        {isPushOn ? 'Выключить уведомления' : 'Включить уведомления'}
      </button>
      {#if !isPushOn && !savedClass}
        <p class="hint" role="status">Выберите класс, чтобы включить уведомления.</p>
      {/if}
      {#if pushNotice}
        <p class="hint" role="status">{pushNotice}</p>
      {/if}
    {:else}
      <StateNotice tone="muted" title="Уведомления недоступны" detail="Браузер не поддерживает Web Push." />
    {/if}
  </fieldset>

  <fieldset>
    <legend>Прочее</legend>
    <div class="actions">
      <button type="button" class="reset nika-btn nika-btn-light" onclick={handleReset}>
        Сбросить настройки
      </button>
      <button type="button" class="clear-cache nika-btn nika-btn-light" onclick={handleClearCache}>
        Очистить кэш расписания
      </button>
    </div>
    {#if resetNotice}
      <p class="hint" role="status">{resetNotice}</p>
    {/if}
    {#if cacheNotice}
      <p class="hint" role="status">{cacheNotice}</p>
    {/if}
  </fieldset>
</section>

<style>
  .settings {
    text-align: left;
  }

  .back {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
  }

  h2 {
    font-size: var(--text-2xl);
    margin: 0 0 var(--space-5);
  }

  fieldset {
    margin: 0 0 var(--space-5);
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    background: var(--color-surface);
  }

  legend {
    padding: 0 var(--space-2);
    font-weight: bold;
  }

  .group {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-3);
    margin-bottom: var(--space-3);
  }

  .group-label {
    flex-basis: 100%;
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .choice,
  .toggle {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    min-height: 44px;
    cursor: pointer;
  }

  .toggle {
    display: flex;
    margin-top: var(--space-2);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
  }

  .push {
    width: 100%;
  }

  .push:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .hint {
    margin: var(--space-2) 0 0;
    font-size: var(--text-sm);
    color: var(--color-muted);
  }
</style>
