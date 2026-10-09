<script lang="ts">
  // W21 «Поиск и свободные кабинеты» screen.
  //
  // Hosts two tools that build on the W19 data layer:
  //   * teacher/room search (`client.search`) — clicking a result selects the
  //     entity and jumps to its schedule (W20 selection store + navigation);
  //   * free rooms for a chosen lesson (`client.getFreeRooms`) — the lesson is
  //     picked with an inline selector, never `window.prompt`.
  //
  // Dates come from the server-today store, never the browser clock. The search
  // input is debounced so a fast typist does not fire a request per keystroke.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    createAsync,
    type FreeRoomsResponse,
    type ScheduleApiClient,
    type ScheduleKind,
    type SearchResponse,
    type SelectionStore,
    type TodayStore,
  } from '../lib';
  import SearchPanel from '../components/SearchPanel.svelte';
  import FreeRooms from '../components/FreeRooms.svelte';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    /** Jump to an entity's schedule (typically the Schedule tab). */
    onOpenSchedule?: () => void;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    onOpenSchedule,
  }: Props = $props();

  const SEARCH_DEBOUNCE_MS = 300;
  const MIN_QUERY_LENGTH = 1;
  const DEFAULT_LESSON = 1;

  let query = $state('');
  let lesson = $state(DEFAULT_LESSON);

  const searchResource = createAsync<SearchResponse>(async () => {
    const schoolId = selection.schoolId;
    if (!schoolId || query.trim().length < MIN_QUERY_LENGTH) {
      return { classes: [], teachers: [], rooms: [] };
    }
    return client.search(schoolId, query.trim());
  });

  const freeRoomsResource = createAsync<FreeRoomsResponse>(async () => {
    const schoolId = selection.schoolId;
    if (!schoolId) {
      throw new Error('Школа не выбрана');
    }
    const date = today.today || undefined;
    return client.getFreeRooms(schoolId, lesson, date);
  });

  function handleQueryChange(next: string): void {
    query = next;
  }

  function handleSelect(kind: ScheduleKind, name: string): void {
    selection.selectEntity(kind, name);
    onOpenSchedule?.();
  }

  // Debounce the query; re-runs whenever the raw text changes. The cleanup
  // clears the pending timer so only the last keystroke triggers a request.
  $effect(() => {
    const current = query;
    const schoolId = selection.schoolId;
    if (!schoolId || current.trim().length < MIN_QUERY_LENGTH) {
      searchResource.reset();
      return;
    }
    const timer = setTimeout(() => void searchResource.load(), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  });

  // Load free rooms whenever school/lesson changes and the server today is known.
  $effect(() => {
    void selection.schoolId;
    void lesson;
    if (selection.schoolId && today.isLoaded) {
      void freeRoomsResource.load();
    }
  });

  // Refresh the server today on entry so the free-rooms date is authoritative.
  $effect(() => {
    if (!today.isLoaded) {
      void today.load().catch(() => {
        // Non-fatal: the free-rooms effect stays idle until a date is known.
      });
    }
  });

  const searchHasQuery = $derived(query.trim().length >= MIN_QUERY_LENGTH);
</script>

<section class="tools">
  <h2>Поиск и кабинеты</h2>

  {#if !selection.schoolId}
    <StateNotice title="Школа не выбрана" detail="Сначала выберите школу на главной." />
  {:else}
    <SearchPanel
      classes={searchResource.data?.classes ?? []}
      teachers={searchResource.data?.teachers ?? []}
      rooms={searchResource.data?.rooms ?? []}
      status={searchResource.status}
      error={searchResource.error}
      hasQuery={searchHasQuery}
      onQueryChange={handleQueryChange}
      onSelect={handleSelect}
    />

    <hr />

    <FreeRooms
      date={today.today || null}
      {lesson}
      rooms={freeRoomsResource.data?.free_rooms ?? []}
      status={freeRoomsResource.status}
      error={freeRoomsResource.error}
      onLessonChange={(next) => (lesson = next)}
    />
  {/if}
</section>

<style>
  .tools {
    text-align: left;
  }

  h2 {
    font-size: var(--text-xl);
    margin: 0 0 var(--space-3);
  }

  hr {
    margin: var(--space-4) 0;
    border: none;
    border-top: 1px solid var(--color-border);
  }
</style>
