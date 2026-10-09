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
  class="favorite nika-btn nika-btn-yellow"
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
    margin-top: var(--space-4);
  }

  .star {
    margin-right: var(--space-1);
  }
</style>
