<script lang="ts">
  // School selector. Purely presentational: the parent owns the school list and
  // the current selection.
  import type { School } from '../lib/api/types';

  interface Props {
    schools: School[];
    selectedId: string | null;
    disabled?: boolean;
    onChange: (schoolId: string) => void;
  }
  let { schools, selectedId, disabled = false, onChange }: Props = $props();

  function select(event: Event) {
    const value = (event.currentTarget as HTMLSelectElement).value;
    if (value) {
      onChange(value);
    }
  }
</script>

<label class="school">
  <span>Школа</span>
  <select value={selectedId ?? ''} {disabled} onchange={select}>
    <option value="" disabled>Выберите школу…</option>
    {#each schools as school (school.id)}
      <option value={school.id} disabled={!school.loaded}>
        {school.name}{school.loaded ? '' : ' (нет данных)'}
      </option>
    {/each}
  </select>
</label>

<style>
  .school {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--color-muted);
    margin-bottom: var(--space-5);
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
</style>
