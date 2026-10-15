<script lang="ts">
  // App shell driven by the History-API router. The URL mirrors the share
  // scheme (`/s/{school}/{kind}/{name}?date=…`), so a deep link opens the right
  // screen and back/forward work.
  //
  // Navigation model: the LANDING (`/`, the original Nikasoft home) offers the
  // school picker, favorites and large section buttons. Choosing a section opens
  // the per-kind LIST (`/list/{kind}`); tapping a name opens its SCHEDULE
  // (`/s/...`). A gear in the header opens SETTINGS (`/settings`). The kind tab
  // bar lives on the list screen (compact switcher).
  //
  // A `router` prop is injectable so tests can drive navigation with a fake
  // browser env; production uses the default `route` store.
  import Home from './routes/Home.svelte';
  import List from './routes/List.svelte';
  import Schedule from './routes/Schedule.svelte';
  import Tools from './routes/Tools.svelte';
  import Settings from './routes/Settings.svelte';
  import Variants from './routes/Variants.svelte';
  import { untrack } from 'svelte';
  import {
    api as defaultApi,
    route as defaultRoute,
    selection as defaultSelection,
    serverToday as defaultToday,
    favorites as defaultFavorites,
    settings as defaultSettings,
    createAsync,
    enablePush,
    disablePush,
    getPermission,
    isPushSupported,
    telegramEnv,
    initTelegramWebApp,
    initTelegramBackButton,
    type SchoolsResponse,
    type TelegramEnv,
    type RouteStore,
    type FavoritesStore,
    type ScheduleApiClient,
    type ScheduleKind,
    type SelectionStore,
    type SettingsStore,
    type TodayStore,
  } from './lib';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    favorites?: FavoritesStore;
    settings?: SettingsStore;
    router?: RouteStore;
    /** Injectable push opt-in (tests); defaults to the real {@link enablePush}. */
    pushEnable?: typeof enablePush;
    /** Injectable push opt-out (tests); defaults to the real {@link disablePush}. */
    pushDisable?: typeof disablePush;
    /** Test seam: force whether the header bell is shown; defaults to Web Push support. */
    pushSupported?: boolean;
    /** Injectable Telegram WebApp env (tests); defaults to the real `window.Telegram`. */
    telegram?: TelegramEnv;
    /** Element to receive Telegram theme CSS variables; defaults to `<html>`. */
    themeTarget?: { style: { setProperty(name: string, value: string): void } };
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    favorites = defaultFavorites,
    settings = defaultSettings,
    router = defaultRoute,
    pushEnable = enablePush,
    pushDisable = disablePush,
    pushSupported: injectedPushSupported = undefined,
    telegram = typeof window === 'undefined' ? { webApp: undefined } : telegramEnv(),
    themeTarget = typeof document === 'undefined' ? undefined : document.documentElement,
  }: Props = $props();

  // Parse the initial location and subscribe to popstate (back/forward).
  $effect(() => {
    const unsubscribe = router.start();
    return unsubscribe;
  });

  // The shell owns the school feature flags. Fetch `/api/schools` once and
  // thread `STRIKEOUT_FREE_LSN` (default true) down to the schedule screens so
  // the flag actually reaches the UI; also adopt the server's today here.
  const schoolsResource = createAsync<SchoolsResponse>(async () => {
    const response = await client.getSchools();
    today.adopt(response.today);
    return response;
  });

  $effect(() => {
    void schoolsResource.load();
  });

  const selectedSchool = $derived(
    schoolsResource.data?.schools.find((school) => school.id === selection.schoolId) ?? null,
  );
  const schoolStrikeoutFreeLsn = $derived(selectedSchool?.features?.strikeout_free_lsn ?? true);
  // The header offers the school homepage when the school has one and the
  // feature is enabled; missing `features`/`homepage` mirrors the server
  // default (enabled).
  const showHomepageLink = $derived(
    !!selectedSchool?.homepage_url && (selectedSchool?.features?.homepage ?? true),
  );
  // A `null` user override follows the school feature flag; an explicit
  // true/false wins (the user's strike-through preference).
  const strikeoutFreeLsn = $derived(settings.strikeoutFreeLsn ?? schoolStrikeoutFreeLsn);

  // The header bell is a master on/off switch for push. It is shown only where
  // Web Push is usable; `pushSupported` is injectable so tests can force it.
  const pushSupported = $derived(injectedPushSupported ?? isPushSupported());
  // Local submit state. The `pushState` rune is what re-renders the bell after a
  // subscribe: the browser permission read (`getPermission`) is not reactive.
  let pushState = $state<'idle' | 'busy' | 'on'>('idle');
  let pushNotice = $state<string | null>(null);
  // Push is class-only (MVP), so the master switch needs a selected class.
  const hasNotificationTarget = $derived(
    selection.schoolId !== null && selection.name !== null && selection.kind === 'class',
  );
  // The single on/off rule shared with Schedule and Settings: the user's flag
  // AND a live subscription (local `pushState`) or a granted permission.
  const bellOn = $derived(
    settings.notificationsEnabled && (pushState === 'on' || getPermission() === 'granted'),
  );

  // Mirror the chosen skin/accent/font onto `<html>` at start and on change.
  $effect(() => {
    settings.apply();
  });

  // "Default section on open": adopt the configured kind once, when no entity
  // is selected yet.
  let adoptedDefault = false;
  $effect(() => {
    const preferred = settings.defaultKind;
    if (!adoptedDefault && selection.name === null) {
      adoptedDefault = true;
      if (selection.kind !== preferred) {
        selection.selectKind(preferred);
      }
    }
  });

  // W24: inside Telegram only — expand/ready + adopt the SDK theme. A regular
  // browser (no SDK) hits the no-op branch and is completely unaffected.
  $effect(() => {
    if (!themeTarget) {
      return;
    }
    return initTelegramWebApp(telegram, themeTarget);
  });

  // W24: show the Telegram BackButton on any non-Home screen and route it home.
  $effect(() => {
    return initTelegramBackButton(telegram, router.route, () => router.goTo('home'));
  });

  // A schedule deep link carries the selection in the URL: adopt it into the
  // selection store so the screen opens on the linked class/teacher/room.
  $effect(() => {
    const current = router.route;
    if (current.view === 'schedule' && current.school && current.name) {
      if (selection.schoolId !== current.school) {
        selection.selectSchool(current.school);
      }
      if (selection.kind !== current.kind || selection.name !== current.name) {
        selection.selectEntity(current.kind, current.name);
      }
    }
  });

  // A list deep link carries the active kind: keep the selection in sync.
  $effect(() => {
    const current = router.route;
    if (current.view === 'list' && selection.kind !== current.kind) {
      selection.selectKind(current.kind);
    }
  });

  // Auto-favorite: any opened entity (its schedule shown for a school+name) is
  // added to favorites. `favorites.add` is idempotent, so re-opening the same
  // entity is a no-op. The write is untracked: reading the favorites state here
  // would re-subscribe the effect, so removing the entity from the schedule's
  // own toggle would immediately re-add it.
  $effect(() => {
    const current = router.route;
    if (current.view === 'schedule' && current.school && current.name) {
      const { school, kind, name } = current;
      untrack(() => favorites.add(school, kind, name));
    }
  });

  /**
   * Open the schedule tab. When an entity is selected, encode it in the URL
   * (share scheme); otherwise switch to the bare schedule view.
   */
  function openSchedule(): void {
    const school = selection.schoolId;
    const name = selection.name;
    const current = router.route;
    if (school && name) {
      const next = { view: 'schedule' as const, school, kind: selection.kind, name, date: null };
      // Avoid pushing a duplicate entry when already showing this entity.
      if (
        current.view === 'schedule' &&
        current.school === school &&
        current.kind === selection.kind &&
        current.name === name &&
        current.date === null
      ) {
        return;
      }
      router.navigate(next);
    } else {
      router.goTo('schedule');
    }
  }

  /**
   * Open a specific entity picked in the list: adopt it into the selection
   * store and jump to its schedule (encoded in the URL via `openSchedule`).
   */
  function openEntity(kind: ScheduleKind, name: string): void {
    selection.selectEntity(kind, name);
    openSchedule();
  }

  /** Open the per-kind list screen for `kind`. */
  function openList(kind: ScheduleKind): void {
    selection.selectKind(kind);
    router.navigate({ view: 'list', kind });
  }

  /**
   * List-screen kind switch: make `kind` active and keep the URL in sync.
   * Selecting the already-active kind is a no-op.
   */
  function handleKindChange(kind: ScheduleKind): void {
    if (selection.kind === kind && router.route.view === 'list') {
      return;
    }
    selection.selectKind(kind);
    router.navigate({ view: 'list', kind });
  }

  /** The schedule/tools back button returns to the list for the current kind. */
  function backToList(): void {
    router.navigate({ view: 'list', kind: selection.kind });
  }

  /**
   * W38: open a specific day from the month calendar. Encodes the date in the
   * same share scheme so the URL is deep-linkable and the back button works.
   */
  function openDay(date: string): void {
    const school = selection.schoolId;
    const name = selection.name;
    if (!school || !name) {
      return;
    }
    router.navigate({ view: 'schedule', school, kind: selection.kind, name, date });
  }

  const currentRoute = $derived(router.route);
  const view = $derived(currentRoute.view);
  const pinnedDate = $derived(currentRoute.view === 'schedule' ? currentRoute.date : null);
  // A schedule view is only meaningful when the URL actually carries an entity.
  // A bare `/schedule` (no entity) falls back to the landing instead of a broken
  // screen.
  const showSchedule = $derived(
    currentRoute.view === 'schedule' && currentRoute.school !== null && currentRoute.name !== null,
  );

  function goHome(): void {
    router.goTo('home');
  }

  /**
   * Toggle the master push switch from the header bell. Turning off drops the
   * subscription and clears the shared flag; turning on requires a selected
   * class, then subscribes it and lights the flag so every control agrees.
   */
  async function toggleNotifications(): Promise<void> {
    if (bellOn) {
      pushState = 'busy';
      pushNotice = null;
      const result = await pushDisable();
      if (result.ok) {
        pushState = 'idle';
        settings.setNotificationsEnabled(false);
        pushNotice = 'Уведомления выключены';
      } else {
        pushState = 'on';
        pushNotice = result.error ?? 'Не удалось выключить уведомления';
      }
      return;
    }
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name || selection.kind !== 'class') {
      pushNotice = 'Выберите класс, чтобы включить уведомления.';
      return;
    }
    pushState = 'busy';
    pushNotice = null;
    const result = await pushEnable({
      schoolId,
      name,
      kind: 'class',
      quiet: settings.pushQuietHours,
    });
    if (result.ok) {
      pushState = 'on';
      settings.setNotificationsEnabled(true);
    } else {
      pushState = 'idle';
      settings.setNotificationsEnabled(false);
      pushNotice = result.error ?? 'Не удалось включить уведомления';
    }
  }
</script>

<main>
  <!-- Persistent blue header bar, mirroring the original site: the selected
       school name plus the «Обновлено» timestamp, and the settings gear. -->
  <header class="app-header">
    <div class="header-row">
      <h1 class="app-header-title">{selectedSchool?.name ?? 'Расписание'}</h1>
      {#if pushSupported}
        <button
          type="button"
          class="bell nika-btn nika-btn-light"
          class:on={bellOn}
          class:inactive={!hasNotificationTarget}
          aria-label="Уведомления"
          aria-pressed={bellOn}
          disabled={pushState === 'busy'}
          onclick={toggleNotifications}
        >
          <svg class="bell-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path
              d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              d="M13.73 21a2 2 0 0 1-3.46 0"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </button>
      {/if}
      <button
        type="button"
        class="gear nika-btn nika-btn-light"
        aria-label="Настройки"
        onclick={() => router.goTo('settings')}
      >
        <span aria-hidden="true">⚙</span>
      </button>
    </div>
    {#if selectedSchool?.updated || (showHomepageLink && selectedSchool)}
      <div class="app-header-sub">
        {#if selectedSchool?.updated}
          <span class="app-header-subtitle">Обновлено {selectedSchool.updated}</span>
        {/if}
        {#if showHomepageLink && selectedSchool}
          <a class="site-link" href={selectedSchool.homepage_url}>Школьный сайт</a>
        {/if}
      </div>
    {/if}
    {#if pushNotice}
      <p class="bell-hint" role="status">{pushNotice}</p>
    {/if}
  </header>

  {#if view === 'settings'}
    <Settings
      {settings}
      {selection}
      {schoolStrikeoutFreeLsn}
      {pushSupported}
      {pushEnable}
      {pushDisable}
      onBack={goHome}
      onOpenVariants={() => router.goTo('variants')}
    />
  {:else if view === 'variants'}
    <Variants {client} {selection} {today} onBack={goHome} />
  {:else if view === 'tools'}
    <Tools {client} {selection} {today} onBack={backToList} />
  {:else if showSchedule}
    <Schedule
      {client}
      {selection}
      {today}
      {favorites}
      {pinnedDate}
      {strikeoutFreeLsn}
      showLessonTime={settings.showLessonTime}
      scheduleView={settings.scheduleView}
      pushQuietHours={settings.pushQuietHours}
      {pushSupported}
      {pushEnable}
      {pushDisable}
      notificationsEnabled={settings.notificationsEnabled}
      onNotificationsChange={(on) => settings.setNotificationsEnabled(on)}
      onOpenDay={openDay}
      onBack={backToList}
      onHome={goHome}
    />
  {:else if view === 'list'}
    <List
      {client}
      {selection}
      {favorites}
      onKindChange={handleKindChange}
      onOpenEntity={openEntity}
      onOpenFreeRooms={() => router.goTo('tools')}
      onBack={goHome}
    />
  {:else}
    <Home
      {client}
      {selection}
      {today}
      {favorites}
      onOpenList={openList}
      onOpenEntity={openEntity}
    />
  {/if}
</main>

<style>
  main {
    text-align: left;
  }

  /* Rounded card header: an inset panel with the original bar palette so it
     reads as a polished card instead of a hard-edged full-bleed bar. Radius,
     shadow and text-shadow all come from tokens, so every skin adapts. */
  .app-header {
    margin: 0 0 var(--space-4);
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--nika-header-border);
    border-radius: var(--radius-lg);
    background: var(--nika-header-bg);
    background-image: var(--nika-header-bg-image);
    color: var(--nika-header-text);
    text-shadow: var(--nika-header-text-shadow);
    box-shadow: var(--shadow-sm);
  }

  .header-row {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .app-header-title {
    flex: 1;
    margin: 0;
    font-size: var(--text-xl);
    font-weight: bold;
    line-height: 1.2;
  }

  /* Both header controls share a consistent 44px height in the centred row. */
  .site-link,
  .gear {
    flex: none;
    display: inline-flex;
    align-items: center;
    min-height: 44px;
  }

  /* Stay legible on every header palette (skins recolour the header text). */
  .site-link {
    color: inherit;
  }

  .gear {
    min-width: 44px;
    padding: 0;
    font-size: var(--text-lg);
    line-height: 1;
  }

  /* Push master switch: an inline SVG so it recolours with the active skin,
     sized/aligned to the gear so the header row stays even. */
  .bell {
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 44px;
    min-height: 44px;
    padding: 0;
    color: var(--color-muted);
  }

  .bell.on {
    color: var(--color-accent);
  }

  /* Muted while there is no class to subscribe; still tappable so a tap can
     explain why nothing happens. */
  .bell.inactive {
    opacity: 0.6;
  }

  .bell:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .bell-hint {
    margin: var(--space-1) 0 0;
    font-size: var(--text-sm);
    color: inherit;
    opacity: 0.9;
  }

  .bell-icon {
    display: block;
    width: 22px;
    height: 22px;
  }

  .app-header-subtitle {
    margin: 0;
    font-size: var(--text-sm);
    font-style: italic;
    font-weight: normal;
    opacity: 0.95;
  }

  /* Second header row: the «Обновлено» timestamp with the school-site link. */
  .app-header-sub {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--space-2) var(--space-3);
    margin-top: 2px;
  }
</style>
