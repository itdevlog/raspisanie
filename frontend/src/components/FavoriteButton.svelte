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
    margin-top: 0.75rem;
    padding: 0.5rem 0.9rem;
    border-radius: 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    background: transparent;
    color: inherit;
    cursor: pointer;
    font-size: 1rem;
  }

  .favorite.active {
    border-color: #d4a017;
    color: #a9780a;
  }

  .star {
    margin-right: 0.25rem;
  }
</style>
