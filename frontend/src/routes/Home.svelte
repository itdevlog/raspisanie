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
    /**
     * W41 fix: `STRIKEOUT_FREE_LSN` for the selected school. The shell passes it
     * down from `/api/schools`; when omitted, Home reads its own school list.
     */
    strikeoutFreeLsn?: boolean;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    favorites = defaultFavorites,
    onOpenSchedule,
    onOpenFreeRooms,
    strikeoutFreeLsn = undefined,
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

  // W41 fix: flag from the shell if provided, else from Home's own school list;
  // absent means the server default (enabled).
  const freeLsn = $derived(
    strikeoutFreeLsn ?? selectedSchool?.features?.strikeout_free_lsn ?? true,
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
        <button type="button" class="primary" onclick={onOpenSchedule}>Открыть расписание</button>
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
        <DayView day={todayResource.data} kind="class" strikeoutFreeLsn={freeLsn} />
      {/if}

      {#if onOpenSchedule}
        <button type="button" class="primary" onclick={onOpenSchedule}>Открыть расписание</button>
      {/if}
    {/if}
  {/if}
</section>

<style>
  .home {
    text-align: left;
  }

  h2 {
    font-size: var(--text-xl);
    margin: 0 0 var(--space-3);
  }

  h3 {
    font-size: var(--text-lg);
    margin: var(--space-2) 0 var(--space-1);
  }

  .school-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin: calc(-1 * var(--space-2)) 0 var(--space-3);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .homepage {
    color: var(--color-link);
  }

  button {
    margin-top: var(--space-3);
    min-height: 44px;
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-sm);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    color: var(--color-text);
    cursor: pointer;
    transition:
      background-color 0.15s,
      border-color 0.15s,
      color 0.15s;
  }

  button:hover {
    border-color: color-mix(in srgb, var(--color-accent) 45%, var(--color-border));
  }

  button.primary {
    background: var(--color-accent);
    color: var(--color-accent-contrast);
    border-color: var(--color-accent);
    font-weight: 600;
  }

  button.primary:hover {
    background: color-mix(in srgb, var(--color-accent) 88%, black);
  }

  .free-rooms {
    margin-bottom: var(--space-3);
  }

  [role='status'] {
    color: var(--color-muted);
  }
</style>
