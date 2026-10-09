<script lang="ts">
  // W39 favorite toggle. Purely presentational: the parent owns the favorites
  // store and decides what entity the button refers to.
  interface Props {
    /** Whether the entity is currently saved. */
    active: boolean;
    /** Flip the saved state. */
    onToggle: () => void;
    /** Entity name for the accessible label, e.g. «5А». */
    label?: string;
  }
  let { active, onToggle, label }: Props = $props();

  const action = $derived(active ? 'Убрать из избранного' : 'В избранное');
  const ariaLabel = $derived(label ? `${action}: ${label}` : action);
</script>

<button
  type="button"
  class="favorite"
  class:active
  aria-pressed={active}
  aria-label={ariaLabel}
  onclick={onToggle}
>
  <span class="star" aria-hidden="true">{active ? '★' : '☆'}</span>
  {active ? 'В избранном' : 'В избранное'}
</button>

<style>
  .favorite {
    margin-top: var(--space-3);
    min-height: 44px;
    padding: var(--space-2) var(--space-4);
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

  .favorite:hover {
    border-color: color-mix(in srgb, var(--color-accent) 45%, var(--color-border));
  }

  .favorite.active {
    border-color: var(--color-accent);
    color: var(--color-accent);
    background: var(--color-accent-soft);
  }

  .star {
    margin-right: var(--space-1);
  }
</style>
