<script lang="ts">
  // W20 Home screen.
  //
  // * school selector (from GET /api/schools);
  // * if a class is saved in the selection store, its schedule for the server's
  //   "today" (never the browser clock);
  // * a link into the full Schedule screen.
  //
  // The `today` store is populated from the same `/api/schools` round-trip via
  // `today.adopt(...)`, so no second request is needed.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    createAsync,
    type DaySchedule,
    type ScheduleApiClient,
    type SchoolsResponse,
    type SelectionStore,
    type TodayStore,
  } from '../lib';
  import SchoolSelect from '../components/SchoolSelect.svelte';
  import DayView from '../components/DayView.svelte';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    /** Navigate to the full schedule screen. */
    onOpenSchedule?: () => void;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    onOpenSchedule,
  }: Props = $props();

  const schoolsResource = createAsync<SchoolsResponse>(async () => {
    const response = await client.getSchools();
    // Adopt the server's today in the same round-trip.
    today.adopt(response.today);
    return response;
  });

  // "Сегодня" for the saved class, fetched once the server today is known.
  const todayResource = createAsync<DaySchedule | null>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      return null;
    }
    const date = today.today;
    if (!date) {
      throw new Error('Не удалось определить дату');
    }
    return client.getDay(schoolId, 'class', name, date);
  });

  const todayKey = $derived(
    `${selection.schoolId ?? ''}|${selection.name ?? ''}|${today.today}|${schoolsResource.status}`,
  );

  $effect(() => {
    void schoolsResource.load();
  });

  $effect(() => {
    void todayKey;
    if (schoolsResource.status === 'ready' && selection.schoolId && selection.name) {
      void todayResource.load();
    }
  });

  function handleSchoolChange(schoolId: string) {
    selection.selectSchool(schoolId);
  }

  const hasSavedClass = $derived(selection.schoolId !== null && selection.name !== null);
</script>

<section class="home">
  <h2>Главная</h2>

  {#if schoolsResource.status === 'error'}
    <StateNotice tone="error" title="Ошибка загрузки школ" detail={schoolsResource.error ?? ''} />
  {:else if schoolsResource.status === 'loading' || schoolsResource.status === 'idle'}
    <p role="status">Загрузка…</p>
  {:else if schoolsResource.data}
    <SchoolSelect
      schools={schoolsResource.data.schools}
      selectedId={selection.schoolId}
      onChange={handleSchoolChange}
    />

    {#if !selection.schoolId}
      <StateNotice tone="muted" title="Выберите школу" detail="Затем откройте расписание." />
    {:else if !hasSavedClass}
      <StateNotice tone="muted" title="Класс не сохранён" detail="Выберите класс в расписании." />
      {#if onOpenSchedule}
        <button type="button" onclick={onOpenSchedule}>Открыть расписание</button>
      {/if}
    {:else if todayResource.status === 'error'}
      <StateNotice
        tone="error"
        title="Ошибка загрузки расписания"
        detail={todayResource.error ?? ''}
      />
    {:else if todayResource.status === 'loading' || todayResource.status === 'idle'}
      <p role="status">Загрузка…</p>
    {:else if todayResource.data}
      <h3>Сегодня</h3>
      <DayView day={todayResource.data} kind="class" />
      {#if onOpenSchedule}
        <button type="button" onclick={onOpenSchedule}>Открыть расписание</button>
      {/if}
    {/if}
  {/if}
</section>

<style>
  .home {
    text-align: left;
  }

  h2 {
    font-size: 1.25rem;
    margin: 0 0 0.75rem;
  }

  h3 {
    font-size: 1rem;
    margin: 0.5rem 0 0.35rem;
  }

  button {
    margin-top: 0.75rem;
    padding: 0.5rem 0.9rem;
    border-radius: 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    background: transparent;
    color: inherit;
    cursor: pointer;
    font-size: 1rem;
  }

  [role='status'] {
    opacity: 0.7;
  }
</style>
