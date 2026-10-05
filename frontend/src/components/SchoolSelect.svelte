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
    gap: 0.2rem;
    font-size: 0.85rem;
    margin-bottom: 1rem;
  }

  select {
    padding: 0.5rem;
    border-radius: 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    background: transparent;
    color: inherit;
    font-size: 1rem;
  }
</style>
