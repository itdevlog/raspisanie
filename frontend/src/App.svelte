<script lang="ts">
  // W22: app shell now driven by the History-API router. The URL mirrors the
  // W16 share scheme (`/s/{school}/{kind}/{name}?date=…`), so a deep link opens
  // the right screen and back/forward work. Nav tabs push history entries.
  //
  // A `router` prop is injectable so tests can drive navigation with a fake
  // browser env; production uses the default `route` store.
  import Home from './routes/Home.svelte';
  import Schedule from './routes/Schedule.svelte';
  import Tools from './routes/Tools.svelte';
  import {
    api as defaultApi,
    route as defaultRoute,
    selection as defaultSelection,
    serverToday as defaultToday,
    telegramEnv,
    initTelegramWebApp,
    initTelegramBackButton,
    type TelegramEnv,
    type RouteStore,
    type ScheduleApiClient,
    type SelectionStore,
    type TodayStore,
  } from './lib';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    router?: RouteStore;
    /** Injectable Telegram WebApp env (tests); defaults to the real `window.Telegram`. */
    telegram?: TelegramEnv;
    /** Element to receive Telegram theme CSS variables; defaults to `<html>`. */
    themeTarget?: { style: { setProperty(name: string, value: string): void } };
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    router = defaultRoute,
    telegram = typeof window === 'undefined' ? { webApp: undefined } : telegramEnv(),
    themeTarget = typeof document === 'undefined' ? undefined : document.documentElement,
  }: Props = $props();

  // Parse the initial location and subscribe to popstate (back/forward).
  $effect(() => {
    const unsubscribe = router.start();
    return unsubscribe;
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

  const view = $derived(router.route.view);
  const pinnedDate = $derived(router.route.view === 'schedule' ? router.route.date : null);
</script>

<main>
  <nav aria-label="Разделы">
    <button
      type="button"
      class:active={view === 'home'}
      aria-current={view === 'home' ? 'page' : undefined}
      onclick={() => router.goTo('home')}
    >
      Главная
    </button>
    <button
      type="button"
      class:active={view === 'schedule'}
      aria-current={view === 'schedule' ? 'page' : undefined}
      onclick={openSchedule}
    >
      Расписание
    </button>
    <button
      type="button"
      class:active={view === 'tools'}
      aria-current={view === 'tools' ? 'page' : undefined}
      onclick={() => router.goTo('tools')}
    >
      Поиск
    </button>
  </nav>

  {#if view === 'home'}
    <Home {client} {selection} {today} onOpenSchedule={openSchedule} />
  {:else if view === 'schedule'}
    <Schedule {client} {selection} {today} {pinnedDate} onOpenDay={openDay} />
  {:else}
    <Tools {client} {selection} {today} onOpenSchedule={openSchedule} />
  {/if}
</main>

<style>
  main {
    text-align: left;
  }

  nav {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
    margin-bottom: 1rem;
  }

  nav button {
    padding: 0.4rem 0.8rem;
    border-radius: 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    background: transparent;
    color: inherit;
    cursor: pointer;
  }

  nav button.active {
    font-weight: 700;
    border-color: currentColor;
  }
</style>
