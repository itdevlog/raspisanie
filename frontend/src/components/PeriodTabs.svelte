<script lang="ts">
  // Day/week period switch: Сегодня / Завтра / Неделя.
  export type Period = 'today' | 'tomorrow' | 'week';

  interface Props {
    value: Period;
    onChange: (period: Period) => void;
  }
  let { value, onChange }: Props = $props();

  const options: { id: Period; label: string }[] = [
    { id: 'today', label: 'Сегодня' },
    { id: 'tomorrow', label: 'Завтра' },
    { id: 'week', label: 'Неделя' },
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
    gap: 0.25rem;
    margin-bottom: 0.75rem;
  }

  .periods button {
    flex: 1;
    padding: 0.4rem 0.6rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    border-radius: 0.4rem;
    background: transparent;
    color: inherit;
    cursor: pointer;
  }

  .periods button.active {
    font-weight: 700;
    border-color: currentColor;
  }
</style>
