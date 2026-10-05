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
    display: inline-block;
    margin-top: 0.75rem;
    margin-left: 0.5rem;
    padding: 0.5rem 0.9rem;
    border-radius: 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    background: transparent;
    color: inherit;
    cursor: pointer;
    font-size: 1rem;
    text-decoration: none;
  }

  .open-telegram:hover {
    border-color: currentColor;
  }
</style>
