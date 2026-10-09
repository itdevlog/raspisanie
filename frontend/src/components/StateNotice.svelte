<script lang="ts">
  // Generic inline notice for empty / holiday / weekend / error states.
  interface Props {
    /** Visual tone; `error` is red, `muted` is subdued. */
    tone?: 'info' | 'muted' | 'error';
    /** Short heading, e.g. «Каникулы». */
    title: string;
    /** Optional explanatory line. */
    detail?: string;
  }
  let { tone = 'info', title, detail }: Props = $props();
</script>

<p class="notice {tone}" role="status">
  <strong>{title}</strong>
  {#if detail}
    <span class="detail">{detail}</span>
  {/if}
</p>

<style>
  .notice {
    margin: var(--space-2) 0;
    padding: var(--space-3) var(--space-4);
    border-radius: var(--radius-md);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    box-shadow: var(--shadow-sm);
  }

  .muted {
    color: var(--color-muted);
    background: var(--color-surface-2);
  }

  .error {
    color: var(--color-cancel);
    background: var(--color-cancel-soft);
    border-color: color-mix(in srgb, var(--color-cancel) 30%, transparent);
  }

  .detail {
    display: block;
    margin-top: var(--space-1);
    opacity: 0.8;
  }
</style>
