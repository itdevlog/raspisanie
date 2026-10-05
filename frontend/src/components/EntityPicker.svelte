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
    gap: 0.25rem;
    margin-bottom: 0.5rem;
  }

  .tabs button {
    flex: 1;
    padding: 0.4rem 0.6rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    border-radius: 0.4rem;
    background: transparent;
    color: inherit;
    cursor: pointer;
  }

  .tabs button.active {
    font-weight: 700;
    border-color: currentColor;
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
</style>
