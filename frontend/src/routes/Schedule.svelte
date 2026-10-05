<script lang="ts">
  // W20 Schedule screen.
  //
  // Layout:
  //   * period tabs: Сегодня / Завтра / Неделя (dates derived from the server
  //     today, never the browser clock);
  //   * entity tabs + name picker: класс / учитель / кабинет;
  //   * body: a {@link DayView} or {@link WeekView}.
  //
  // All data comes from the injected client; the today store is the source of
  // "сегодня"/"завтра". Search and free-rooms screens are W21 and intentionally
  // absent here.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    createAsync,
    type DaySchedule,
    type ScheduleApiClient,
    type ScheduleKind,
    type SelectionStore,
    type TodayStore,
    type WeekScheduleResponse,
  } from '../lib';
  import EntityPicker from '../components/EntityPicker.svelte';
  import PeriodTabs, { type Period } from '../components/PeriodTabs.svelte';
  import DayView from '../components/DayView.svelte';
  import WeekView from '../components/WeekView.svelte';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
  }
  let { client = defaultApi, selection = defaultSelection, today = defaultToday }: Props = $props();

  let period = $state<Period>('today');
  const weekOffset = $state(0);

  // Names for the active kind within the selected school.
  const namesResource = createAsync<string[]>(async () => {
    const schoolId = selection.schoolId;
    if (!schoolId) {
      return [];
    }
    if (selection.kind === 'class') {
      return (await client.getClasses(schoolId)).classes;
    }
    if (selection.kind === 'teacher') {
      return (await client.getTeachers(schoolId)).teachers;
    }
    return (await client.getRooms(schoolId)).rooms;
  });

  // Day payload for today/tomorrow; unused for the week period.
  const dayResource = createAsync<DaySchedule>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      throw new Error('Выберите расписание');
    }
    const date = period === 'tomorrow' ? today.tomorrow : today.today;
    if (!date) {
      throw new Error('Не удалось определить дату');
    }
    return client.getDay(schoolId, selection.kind, name, date);
  });

  // Week payload (Mon–Fri).
  const weekResource = createAsync<WeekScheduleResponse>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      throw new Error('Выберите расписание');
    }
    return client.getWeek(schoolId, selection.kind, name, weekOffset);
  });

  const kindNamesKey = $derived(`${selection.schoolId ?? ''}|${selection.kind}`);
  const bodyKey = $derived(
    `${selection.schoolId ?? ''}|${selection.kind}|${selection.name ?? ''}|${period}|${weekOffset}`,
  );

  // Reload the name list whenever the school/kind changes.
  $effect(() => {
    // Reading the key here registers the reactive dependency; `void` keeps the
    // statement an expression without changing behavior.
    void kindNamesKey;
    void namesResource.load();
  });

  // Reload today from the server so "сегодня" is authoritative on entry.
  $effect(() => {
    if (!today.isLoaded) {
      void today.load().catch(() => {
        // Failure is non-fatal: the day effect simply stays idle and the UI
        // shows its loading/error state once a date is available.
      });
    }
  });

  // Load the payload for the current period. Split into two effects so only the
  // relevant resource is touched and the week offset is respected.
  $effect(() => {
    void bodyKey;
    if (period === 'week') {
      void weekResource.load();
    } else if (today.isLoaded) {
      void dayResource.load();
    }
  });

  function handleKindChange(kind: ScheduleKind) {
    selection.selectKind(kind);
  }

  function handleNameChange(name: string) {
    selection.selectEntity(selection.kind, name);
  }

  const bodyStatus = $derived(period === 'week' ? weekResource.status : dayResource.status);
  const bodyError = $derived(period === 'week' ? weekResource.error : dayResource.error);
  const hasEntity = $derived(selection.name !== null);
</script>

<section class="schedule">
  <h2>Расписание</h2>

  {#if !selection.schoolId}
    <StateNotice title="Школа не выбрана" detail="Сначала выберите школу на главной." />
  {:else}
    <EntityPicker
      kind={selection.kind}
      name={selection.name}
      names={namesResource.data ?? []}
      disabled={namesResource.isLoading}
      onKindChange={handleKindChange}
      onNameChange={handleNameChange}
    />

    {#if namesResource.status === 'error'}
      <StateNotice
        tone="error"
        title="Не удалось загрузить список"
        detail={namesResource.error ?? ''}
      />
    {/if}

    <PeriodTabs value={period} onChange={(p) => (period = p)} />

    {#if !hasEntity}
      <StateNotice
        tone="muted"
        title="Выберите расписание"
        detail="Укажите класс, учителя или кабинет."
      />
    {:else if bodyStatus === 'error'}
      <StateNotice tone="error" title="Ошибка загрузки" detail={bodyError ?? ''} />
    {:else if bodyStatus === 'loading' || bodyStatus === 'idle'}
      <p role="status">Загрузка…</p>
    {:else if period === 'week'}
      {#if weekResource.data && weekResource.data.days.length > 0}
        <WeekView week={weekResource.data} kind={selection.kind} />
      {:else}
        <StateNotice title="Занятий нет" detail="Расписание на неделю пустое." />
      {/if}
    {:else if dayResource.data}
      <DayView day={dayResource.data} kind={selection.kind} />
    {/if}
  {/if}
</section>

<style>
  .schedule {
    text-align: left;
  }

  h2 {
    font-size: 1.25rem;
    margin: 0 0 0.75rem;
  }

  [role='status'] {
    opacity: 0.7;
  }
</style>
