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
    margin-bottom: var(--space-4);
    padding: var(--space-1);
    background: var(--color-track);
    border-radius: var(--radius-md);
  }

  .periods button {
    flex: 1;
    min-height: 44px;
    padding: var(--space-2) var(--space-1);
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--color-muted);
    cursor: pointer;
    font-weight: 500;
    transition:
      background-color 0.15s,
      color 0.15s,
      box-shadow 0.15s,
      transform 0.1s;
  }

  .periods button:hover:not(.active) {
    color: var(--color-text);
  }

  .periods button:active {
    transform: scale(0.98);
  }

  .periods button.active {
    font-weight: 600;
    background: var(--color-surface);
    color: var(--color-accent);
    box-shadow: var(--shadow-sm);
  }
</style>
