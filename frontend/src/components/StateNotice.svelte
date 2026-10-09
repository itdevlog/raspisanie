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
    margin: var(--space-4) 0;
    padding: var(--space-5) var(--space-4);
    border-radius: var(--radius-lg);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    text-align: center;
    color: var(--color-muted);
  }

  .notice strong {
    display: block;
    color: var(--color-text);
    font-weight: 600;
  }

  .muted {
    background: var(--color-surface-2);
  }

  .error {
    color: var(--color-cancel);
    border-left: 3px solid var(--color-cancel);
  }

  .error strong {
    color: var(--color-cancel);
  }

  .detail {
    display: block;
    margin-top: var(--space-2);
    font-size: var(--text-sm);
    opacity: 0.85;
  }
</style>
