<script lang="ts">
  // W21 free-rooms view: pick a lesson inline (no window.prompt) and show the
  // rooms that are free for that lesson on a given date.
  //
  // Stateful but client-agnostic: the parent screen owns the API call. This
  // component renders the inline lesson selector, the date label and the result
  // list, and reports the chosen lesson via `onLessonChange`.
  import { LESSONS_PER_DAY, lessonNumbers } from '../lib/schedule-view';
  import StateNotice from './StateNotice.svelte';

  interface Props {
    /** Date the free-rooms answer is for, as `DD.MM.YYYY` (server today). */
    date: string | null;
    /** Currently selected lesson number (1..12). */
    lesson: number;
    /** Free room names, or `[]` when none are free / not loaded yet. */
    rooms: string[];
    /** Discriminated load state of the free-rooms request. */
    status: 'idle' | 'loading' | 'ready' | 'error';
    /** Human-readable error message when `status === 'error'`. */
    error?: string | null;
    /** Raised when the user picks another lesson. */
    onLessonChange: (lesson: number) => void;
  }
  let { date, lesson, rooms, status, error = null, onLessonChange }: Props = $props();

  const lessons = lessonNumbers(LESSONS_PER_DAY);

  function selectLesson(event: Event) {
    const value = Number((event.currentTarget as HTMLSelectElement).value);
    if (Number.isInteger(value) && value >= 1 && value <= LESSONS_PER_DAY) {
      onLessonChange(value);
    }
  }
</script>

<section class="free-rooms">
  <h3>Свободные кабинеты</h3>

  <div class="controls">
    <label class="field">
      <span>Урок</span>
      <select value={String(lesson)} onchange={selectLesson}>
        {#each lessons as n (n)}
          <option value={String(n)}>{n}</option>
        {/each}
      </select>
    </label>
    {#if date}
      <p class="date">{date}</p>
    {/if}
  </div>

  {#if status === 'loading' || status === 'idle'}
    <p class="loading" role="status">Загрузка…</p>
  {:else if status === 'error'}
    <StateNotice
      tone="error"
      title="Ошибка загрузки"
      detail={error ?? 'Не удалось загрузить свободные кабинеты'}
    />
  {:else if rooms.length === 0}
    <StateNotice tone="muted" title="Все кабинеты заняты" detail="Свободных кабинетов нет." />
  {:else}
    <ul class="rooms">
      {#each rooms as room (room)}
        <li>{room}</li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  h3 {
    font-size: var(--text-lg);
    font-weight: 600;
    letter-spacing: -0.011em;
    margin: 0 0 var(--space-2);
  }

  .controls {
    display: flex;
    align-items: flex-end;
    gap: var(--space-4);
    margin-bottom: var(--space-3);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  select {
    min-height: 44px;
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-sm);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    color: var(--color-text);
    transition:
      background-color 0.15s,
      border-color 0.15s,
      color 0.15s;
  }

  .date {
    margin: 0 0 var(--space-1);
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-sm);
    background: var(--color-surface-2);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .rooms {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .rooms li {
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-sm);
    background: var(--color-surface-2);
  }

  .loading {
    margin: var(--space-4) 0;
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  [role='status'] {
    color: var(--color-muted);
  }
</style>
