<script lang="ts">
  // Class / teacher / room switch + a name picker for the active kind.
  //
  // The list of names is loaded by the parent (via the API client) and passed in;
  // this component is purely presentational so it stays easy to test.
  import type { ScheduleKind } from '../lib/api/types';
  import { KIND_LABELS } from '../lib/schedule-view';

  interface Props {
    kind: ScheduleKind;
    name: string | null;
    names: string[];
    /** Disable the picker while names are loading or unavailable. */
    disabled?: boolean;
    /** Raised when the user switches kind. */
    onKindChange: (kind: ScheduleKind) => void;
    /** Raised when the user picks a name. */
    onNameChange: (name: string) => void;
  }
  let { kind, name, names, disabled = false, onKindChange, onNameChange }: Props = $props();

  const kinds: ScheduleKind[] = ['class', 'teacher', 'room'];

  function selectKind(next: ScheduleKind) {
    if (next !== kind) {
      onKindChange(next);
    }
  }

  function selectName(event: Event) {
    const value = (event.currentTarget as HTMLSelectElement).value;
    if (value) {
      onNameChange(value);
    }
  }
</script>

<div class="picker">
  <div class="tabs" role="tablist" aria-label="Тип расписания">
    {#each kinds as k (k)}
      <button
        type="button"
        role="tab"
        aria-selected={kind === k}
        class:active={kind === k}
        onclick={() => selectKind(k)}
      >
        {KIND_LABELS[k]}
      </button>
    {/each}
  </div>

  <label class="field">
    <span>{KIND_LABELS[kind]}</span>
    <select value={name ?? ''} {disabled} onchange={selectName}>
      <option value="" disabled>Выберите…</option>
      {#each names as n (n)}
        <option value={n}>{n}</option>
      {/each}
    </select>
  </label>
</div>

<style>
  .tabs {
    display: flex;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
    padding: var(--space-1);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
  }

  .tabs button {
    flex: 1;
    min-height: 40px;
    padding: var(--space-2) var(--space-3);
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--color-muted);
    cursor: pointer;
    font-weight: 500;
    transition:
      background-color 0.15s,
      border-color 0.15s,
      color 0.15s;
  }

  .tabs button:hover:not(.active) {
    background: var(--color-surface-2);
    color: var(--color-text);
  }

  .tabs button.active {
    font-weight: 700;
    background: var(--color-accent-soft);
    color: var(--color-accent);
    border-color: color-mix(in srgb, var(--color-accent) 35%, transparent);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
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

  select:hover:not(:disabled) {
    border-color: color-mix(in srgb, var(--color-accent) 45%, var(--color-border));
  }

  select:disabled {
    opacity: 0.6;
    cursor: default;
  }
</style>
