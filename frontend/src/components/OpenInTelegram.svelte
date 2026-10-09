<script lang="ts">
  // W24: «Открыть в Telegram» control.
  //
  // Renders an anchor to the bot deep link (`t.me/<bot>?start=…`) that reopens
  // the currently shown share target inside Telegram, where the bot can use its
  // native notifications. The bot username comes from configuration
  // (`VITE_TELEGRAM_BOT`); when it is unset — or the target cannot be encoded —
  // the control hides itself gracefully. Nothing here touches the Telegram SDK.
  import { buildStartPayload, buildTelegramDeepLink, type TelegramShareTarget } from '../lib';

  interface Props {
    /** Bot username without `@`; defaults to the configured `VITE_TELEGRAM_BOT`. */
    bot?: string;
    /** Share target to encode in the `start` payload. */
    target: TelegramShareTarget;
    /** Optional label override. */
    label?: string;
  }
  let {
    bot = import.meta.env.VITE_TELEGRAM_BOT ?? '',
    target,
    label = 'Открыть в Telegram',
  }: Props = $props();

  const payload = $derived(buildStartPayload(target));
  const href = $derived(payload ? buildTelegramDeepLink(bot, payload) : null);
</script>

{#if href}
  <a class="open-telegram" {href} target="_blank" rel="noopener noreferrer">{label}</a>
{/if}

<style>
  .open-telegram {
    display: inline-flex;
    align-items: center;
    margin-top: var(--space-3);
    margin-left: var(--space-2);
    min-height: 44px;
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-sm);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    color: var(--color-link);
    cursor: pointer;
    text-decoration: none;
    transition:
      background-color 0.15s,
      border-color 0.15s,
      color 0.15s;
  }

  .open-telegram:hover {
    border-color: var(--color-accent);
    background: var(--color-accent-soft);
  }
</style>
