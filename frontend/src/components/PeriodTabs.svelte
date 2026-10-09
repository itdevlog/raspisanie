<script lang="ts">
  // Day/week/month period switch: Сегодня / Завтра / Неделя / Месяц.
  export type Period = 'today' | 'tomorrow' | 'week' | 'month';

  interface Props {
    value: Period;
    onChange: (period: Period) => void;
  }
  let { value, onChange }: Props = $props();

  const options: { id: Period; label: string }[] = [
    { id: 'today', label: 'Сегодня' },
    { id: 'tomorrow', label: 'Завтра' },
    { id: 'week', label: 'Неделя' },
    { id: 'month', label: 'Месяц' },
  ];
</script>

<div class="periods" role="tablist" aria-label="Период">
  {#each options as option (option.id)}
    <button
      type="button"
      role="tab"
      aria-selected={value === option.id}
      class:active={value === option.id}
      onclick={() => onChange(option.id)}
    >
      {option.label}
    </button>
  {/each}
</div>

<style>
  .periods {
    display: flex;
    gap: var(--space-1);
    margin-bottom: var(--space-3);
    padding: var(--space-1);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-sm);
  }

  .periods button {
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

  .periods button:hover:not(.active) {
    background: var(--color-surface-2);
    color: var(--color-text);
  }

  .periods button.active {
    font-weight: 700;
    background: var(--color-accent-soft);
    color: var(--color-accent);
    border-color: color-mix(in srgb, var(--color-accent) 35%, transparent);
  }
</style>
