<script lang="ts">
  // W20 Home screen; extended in W39.
  //
  // * school selector (from GET /api/schools);
  // * school metadata: city, «Обновлено», link to the school site (gated by
  //   `features.homepage`);
  // * if a class is saved in the selection store, its «идёт урок / до начала»
  //   widget from GET .../now and its schedule for the server's "today" (never
  //   the browser clock);
  // * a favorite toggle for the saved class;
  // * a link into the full Schedule screen and a shortcut to free rooms.
  //
  // The `today` store is populated from the same `/api/schools` round-trip via
  // `today.adopt(...)`, so no second request is needed.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    favorites as defaultFavorites,
    createAsync,
    type DaySchedule,
    type FavoritesStore,
    type NowResponse,
    type ScheduleApiClient,
    type SchoolsResponse,
    type SelectionStore,
    type TodayStore,
  } from '../lib';
  import SchoolSelect from '../components/SchoolSelect.svelte';
  import DayView from '../components/DayView.svelte';
  import NowWidget from '../components/NowWidget.svelte';
  import FavoriteButton from '../components/FavoriteButton.svelte';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    favorites?: FavoritesStore;
    /** Navigate to the full schedule screen. */
    onOpenSchedule?: () => void;
    /** Navigate to the free-rooms screen. */
    onOpenFreeRooms?: () => void;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    favorites = defaultFavorites,
    onOpenSchedule,
    onOpenFreeRooms,
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

  // W39: current/next lesson for the saved class, from GET .../now.
  const nowResource = createAsync<NowResponse>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      throw new Error('Класс не сохранён');
    }
    const date = today.today;
    if (!date) {
      throw new Error('Не удалось определить дату');
    }
    return client.getNow(schoolId, 'class', name, date);
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
      void nowResource.load();
    }
  });

  function handleSchoolChange(schoolId: string) {
    selection.selectSchool(schoolId);
  }

  const hasSavedClass = $derived(selection.schoolId !== null && selection.name !== null);

  const selectedSchool = $derived(
    schoolsResource.data?.schools.find((school) => school.id === selection.schoolId) ?? null,
  );

  // Missing `features`/`homepage` mirrors the server default (enabled).
  const showHomepageLink = $derived(
    Boolean(selectedSchool?.homepage_url && (selectedSchool.features?.homepage ?? true)),
  );

  const isFavorite = $derived(
    selection.schoolId !== null &&
      selection.name !== null &&
      favorites.has(selection.schoolId, 'class', selection.name),
  );

  function toggleFavorite() {
    if (selection.schoolId && selection.name) {
      favorites.toggle(selection.schoolId, 'class', selection.name);
    }
  }
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

    {#if selectedSchool}
      <div class="school-meta">
        {#if selectedSchool.city}
          <span class="city">{selectedSchool.city}</span>
        {/if}
        {#if selectedSchool.updated}
          <span class="updated">Обновлено {selectedSchool.updated}</span>
        {/if}
        {#if showHomepageLink}
          <a class="homepage" href={selectedSchool.homepage_url}>Сайт школы</a>
        {/if}
      </div>
    {/if}

    {#if selection.schoolId}
      <button type="button" class="free-rooms" onclick={() => onOpenFreeRooms?.()}>
        Свободные кабинеты
      </button>
    {/if}

    {#if !selection.schoolId}
      <StateNotice tone="muted" title="Выберите школу" detail="Затем откройте расписание." />
    {:else if !hasSavedClass}
      <StateNotice tone="muted" title="Класс не сохранён" detail="Выберите класс в расписании." />
      {#if onOpenSchedule}
        <button type="button" onclick={onOpenSchedule}>Открыть расписание</button>
      {/if}
    {:else}
      <NowWidget data={nowResource.data} status={nowResource.status} error={nowResource.error} />

      <FavoriteButton
        active={isFavorite}
        onToggle={toggleFavorite}
        label={selection.name ?? undefined}
      />

      {#if todayResource.status === 'error'}
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
      {/if}

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

  .school-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin: -0.5rem 0 0.75rem;
    font-size: 0.9rem;
    opacity: 0.8;
  }

  .homepage {
    color: inherit;
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

  .free-rooms {
    margin-bottom: 0.75rem;
  }

  [role='status'] {
    opacity: 0.7;
  }
</style>
