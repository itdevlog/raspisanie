<script lang="ts">
  // W21 free-rooms view: pick a lesson inline (no window.prompt) and show the
  // rooms that are free for that lesson on a given date.
  //
  // Stateful but client-agnostic: the parent screen owns the API call. This
  // component renders the inline lesson selector, the date label and the result
  // list, and reports the chosen lesson via `onLessonChange`.
  import { LESSONS_PER_DAY, lessonNumbers } from '../lib/schedule-view';

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
    <p role="status">Загрузка…</p>
  {:else if status === 'error'}
    <p class="error" role="status">{error ?? 'Не удалось загрузить свободные кабинеты'}</p>
  {:else if rooms.length === 0}
    <p role="status">Все кабинеты заняты</p>
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
    font-size: 1rem;
    margin: 0 0 0.35rem;
  }

  .controls {
    display: flex;
    align-items: flex-end;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    font-size: 0.85rem;
  }

  select {
    padding: 0.4rem;
    border-radius: 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    background: transparent;
    color: inherit;
  }

  .date {
    margin: 0 0 0.35rem;
    opacity: 0.7;
  }

  .rooms {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .rooms li {
    padding: 0.3rem 0.6rem;
    border-radius: 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
  }

  [role='status'] {
    opacity: 0.7;
  }

  .error {
    color: #b00020;
    opacity: 1;
  }
</style>
