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
      class="period nika-btn nika-btn-blue"
      class:is-active={value === option.id}
      onclick={() => onChange(option.id)}
    >
      {option.label}
    </button>
  {/each}
</div>

<style>
  /* Original two-tone segmented bar: blue tabs, active = pressed/highlight. */
  .periods {
    display: flex;
    gap: var(--space-1);
    margin-bottom: var(--space-4);
    padding: var(--space-1);
    background: var(--color-track);
    border-radius: var(--radius-md);
  }

  .period {
    flex: 1;
    min-height: 44px;
    padding: var(--space-2) var(--space-1);
    font-size: var(--text-sm);
  }
</style>
