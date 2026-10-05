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
    margin: 0.5rem 0;
    padding: 0.6rem 0.75rem;
    border-radius: 0.5rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
  }

  .muted {
    opacity: 0.65;
  }

  .error {
    color: #b00020;
  }

  .detail {
    display: block;
    margin-top: 0.15rem;
    opacity: 0.8;
  }
</style>
