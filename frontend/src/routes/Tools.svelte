<script lang="ts">
  // «Свободные кабинеты» screen.
  //
  // The teacher/room/class search now lives inside the per-kind lists (see
  // `routes/Home.svelte`), so this screen hosts only the free-rooms tool:
  // `client.getFreeRooms` for an inline-selected lesson. The lesson is picked
  // with a selector, never `window.prompt`.
  //
  // Dates come from the server-today store, never the browser clock.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    createAsync,
    type FreeRoomsResponse,
    type ScheduleApiClient,
    type SelectionStore,
    type TodayStore,
  } from '../lib';
  import FreeRooms from '../components/FreeRooms.svelte';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    /** Return to the list view (the kind tab bar's landing screen). */
    onBack?: () => void;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    onBack,
  }: Props = $props();

  const DEFAULT_LESSON = 1;

  let lesson = $state(DEFAULT_LESSON);

  const freeRoomsResource = createAsync<FreeRoomsResponse>(async () => {
    const schoolId = selection.schoolId;
    if (!schoolId) {
      throw new Error('Школа не выбрана');
    }
    const date = today.today || undefined;
    return client.getFreeRooms(schoolId, lesson, date);
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
</script>

<section class="tools">
  <button type="button" class="back nika-btn nika-btn-light" aria-label="К списку" onclick={() => onBack?.()}>
    ← к списку
  </button>

  <h2>Свободные кабинеты</h2>

  {#if !selection.schoolId}
    <StateNotice title="Школа не выбрана" detail="Сначала выберите школу в списке." />
  {:else}
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

  .back {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
  }

  h2 {
    font-size: var(--text-2xl);
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 0 0 var(--space-5);
  }
</style>
