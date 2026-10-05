<script lang="ts">
  // W20: minimal app shell wiring the two screens together.
  //
  // No routing library and no URL routing yet — that is W22 (share links +
  // history). A thin view toggle keeps W20 self-contained and testable.
  import Home from './routes/Home.svelte';
  import Schedule from './routes/Schedule.svelte';
  import Tools from './routes/Tools.svelte';
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    type ScheduleApiClient,
    type SelectionStore,
    type TodayStore,
  } from './lib';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
  }
  let { client = defaultApi, selection = defaultSelection, today = defaultToday }: Props = $props();

  type View = 'home' | 'schedule' | 'tools';
  let view = $state<View>('home');
</script>

<main>
  <nav aria-label="Разделы">
    <button
      type="button"
      class:active={view === 'home'}
      aria-current={view === 'home' ? 'page' : undefined}
      onclick={() => (view = 'home')}
    >
      Главная
    </button>
    <button
      type="button"
      class:active={view === 'schedule'}
      aria-current={view === 'schedule' ? 'page' : undefined}
      onclick={() => (view = 'schedule')}
    >
      Расписание
    </button>
    <button
      type="button"
      class:active={view === 'tools'}
      aria-current={view === 'tools' ? 'page' : undefined}
      onclick={() => (view = 'tools')}
    >
      Поиск
    </button>
  </nav>

  {#if view === 'home'}
    <Home {client} {selection} {today} onOpenSchedule={() => (view = 'schedule')} />
  {:else if view === 'schedule'}
    <Schedule {client} {selection} {today} />
  {:else}
    <Tools {client} {selection} {today} onOpenSchedule={() => (view = 'schedule')} />
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
