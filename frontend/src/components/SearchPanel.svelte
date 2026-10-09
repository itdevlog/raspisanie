<script lang="ts">
  // W21 search panel: find classes/teachers/rooms by name and open their schedule.
  //
  // Presentational + local query state only — the debounced network request is
  // owned by the parent screen, which passes the current `classes`/`teachers`/
  // `rooms` results and the load status. Clicking a result raises `onSelect` so
  // the parent can update the selection store (same navigation as W20).
  import type { ScheduleKind } from '../lib/api/types';

  interface Props {
    /** Matching classes (names). Defaults to none (W37 added classes to `/search`). */
    classes?: string[];
    /** Matching teachers (names). */
    teachers: string[];
    /** Matching rooms (names). */
    rooms: string[];
    /** Discriminated load state of the search request. */
    status: 'idle' | 'loading' | 'ready' | 'error';
    /** Human-readable error message when `status === 'error'`. */
    error?: string | null;
    /** True when a query has been entered (so empty ≠ "no query yet"). */
    hasQuery: boolean;
    /** Raised (debounced by the parent) when the query text changes. */
    onQueryChange: (query: string) => void;
    /** Raised when a result is chosen; opens that entity's schedule. */
    onSelect: (kind: ScheduleKind, name: string) => void;
  }
  let {
    classes = [],
    teachers,
    rooms,
    status,
    error = null,
    hasQuery,
    onQueryChange,
    onSelect,
  }: Props = $props();

  let query = $state('');

  function handleInput(event: Event) {
    const value = (event.currentTarget as HTMLInputElement).value;
    query = value;
    onQueryChange(value);
  }

  const isEmpty = $derived(
    status === 'ready' &&
      hasQuery &&
      classes.length === 0 &&
      teachers.length === 0 &&
      rooms.length === 0,
  );
</script>

<section class="search">
  <label class="field">
    <span>Поиск</span>
    <input
      type="search"
      placeholder="Класс, учитель или кабинет…"
      autocomplete="off"
      value={query}
      oninput={handleInput}
    />
  </label>

  {#if status === 'loading'}
    <p role="status">Поиск…</p>
  {:else if status === 'error'}
    <p class="error" role="status">{error ?? 'Не удалось выполнить поиск'}</p>
  {:else if isEmpty}
    <p class="empty" role="status">Ничего не найдено</p>
  {:else if status === 'ready' && hasQuery}
    {#if classes.length > 0}
      <div class="group">
        <h4>Классы</h4>
        <ul>
          {#each classes as className (className)}
            <li>
              <button type="button" onclick={() => onSelect('class', className)}>
                {className}
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if teachers.length > 0}
      <div class="group">
        <h4>Учителя</h4>
        <ul>
          {#each teachers as teacher (teacher)}
            <li>
              <button type="button" onclick={() => onSelect('teacher', teacher)}>
                {teacher}
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if rooms.length > 0}
      <div class="group">
        <h4>Кабинеты</h4>
        <ul>
          {#each rooms as room (room)}
            <li>
              <button type="button" onclick={() => onSelect('room', room)}>{room}</button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  {/if}
</section>

<style>
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  input {
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

  input:hover {
    border-color: color-mix(in srgb, var(--color-accent) 45%, var(--color-border));
  }

  .group {
    margin-top: var(--space-3);
  }

  h4 {
    font-size: var(--text-sm);
    margin: 0 0 var(--space-1);
    color: var(--color-muted);
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  li button {
    min-height: 36px;
    padding: var(--space-1) var(--space-3);
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

  li button:hover {
    background: var(--color-accent-soft);
    border-color: color-mix(in srgb, var(--color-accent) 40%, var(--color-border));
    color: var(--color-accent);
  }

  [role='status'] {
    color: var(--color-muted);
  }

  .error {
    color: var(--color-cancel);
    opacity: 1;
  }
</style>
