<script lang="ts">
  // W42 — the «Замена»/«Отменён» lesson badge. Tapping it opens a small popover
  // with the «было → стало» diff carried by the lesson's optional `exchange`
  // payload (see `services/base_schedule_service.py::_lesson_exchange`).
  //
  // Degrades gracefully: a normal lesson renders nothing; an exchanged/cancelled
  // lesson whose payload has no `exchange` still shows the plain label but opens
  // no popover. Colours come from the shared tokens so all five skins work.
  import type { Lesson } from '../lib/api/types';
  import {
    exchangeDiffLines,
    isCancelled,
    isExchange,
    lessonStatusLabel,
  } from '../lib/schedule-view';

  interface Props {
    lesson: Lesson;
  }
  let { lesson }: Props = $props();

  let open = $state(false);
  let root = $state<HTMLSpanElement>();

  const label = $derived(lessonStatusLabel(lesson));
  const exchange = $derived(lesson.exchange ?? null);
  const lines = $derived(exchange ? exchangeDiffLines(exchange) : []);
  const cancelled = $derived(isCancelled(lesson));
  const exchanged = $derived(isExchange(lesson) && !isCancelled(lesson));

  function toggle() {
    if (exchange) {
      open = !open;
    }
  }

  // Close on Escape or a click outside the widget while the popover is open.
  // The listener is attached only when open (inside an effect, so the opening
  // click that bubbles to `document` has already finished).
  $effect(() => {
    if (!open) {
      return;
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        open = false;
      }
    };
    const onOutside = (event: Event) => {
      if (root && !root.contains(event.target as Node)) {
        open = false;
      }
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('click', onOutside);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('click', onOutside);
    };
  });

  // A new lesson (day switch / list re-render) always starts closed.
  $effect(() => {
    void lesson;
    open = false;
  });
</script>

{#if label}
  {#if exchange}
    <span class="exchange" bind:this={root}>
      <button
        type="button"
        class="badge"
        class:cancelled
        class:exchanged
        aria-expanded={open}
        aria-haspopup="dialog"
        onclick={toggle}
      >
        {label}
      </button>

      {#if open}
        <div class="popover" role="dialog" aria-label="Что изменилось">
          <button type="button" class="close" aria-label="Закрыть" onclick={() => (open = false)}>
            ×
          </button>
          {#if exchange.is_cancelled}
            <p class="note">Урок отменён</p>
          {:else}
            <p class="title">Что изменилось</p>
            <ul class="diff">
              {#each lines as line (line.label)}
                <li class="row">
                  <span class="field">{line.label}</span>
                  <span class="from">{line.from}</span>
                  <span class="arrow" aria-hidden="true">→</span>
                  <span class="to">{line.to}</span>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/if}
    </span>
  {:else}
    <span class="badge" class:cancelled class:exchanged>{label}</span>
  {/if}
{/if}

<style>
  .exchange {
    position: relative;
    display: inline-block;
  }

  .badge {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 1px var(--space-2);
    border: none;
    border-radius: 999px;
    font-size: var(--text-xs);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-muted);
    background: var(--color-surface-2);
  }

  button.badge {
    cursor: pointer;
  }

  /* Touch target ≥ 44px without inflating the visual pill. */
  button.badge::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: max(100%, 44px);
    height: max(100%, 44px);
    transform: translate(-50%, -50%);
  }

  .badge.cancelled {
    color: var(--color-cancel);
    background: var(--color-cancel-soft);
  }

  .badge.exchanged {
    color: var(--color-exchange);
    background: var(--color-exchange-soft);
  }

  .popover {
    position: absolute;
    top: calc(100% + var(--space-2));
    right: 0;
    z-index: 20;
    min-width: 12rem;
    max-width: min(18rem, 80vw);
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    box-shadow: var(--shadow-md);
    color: var(--color-text);
    text-align: left;
    text-transform: none;
    letter-spacing: normal;
    font-weight: normal;
  }

  .close {
    position: absolute;
    top: var(--space-1);
    right: var(--space-1);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.75rem;
    height: 1.75rem;
    padding: 0;
    border: none;
    border-radius: 50%;
    background: var(--color-surface-2);
    color: var(--color-text);
    font-size: var(--text-base);
    line-height: 1;
    cursor: pointer;
  }

  /* Touch target ≥ 44px for the close control too. */
  .close::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: max(100%, 44px);
    height: max(100%, 44px);
    transform: translate(-50%, -50%);
  }

  .title,
  .note {
    margin: 0 0 var(--space-2);
    font-size: var(--text-xs);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-muted);
  }

  .note {
    margin-bottom: 0;
    color: var(--color-cancel);
  }

  .diff {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-1);
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-1) var(--space-2);
    font-size: var(--text-sm);
  }

  .field {
    min-width: 4.5rem;
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-muted);
  }

  .from {
    color: var(--color-muted);
  }

  .arrow {
    color: var(--color-muted);
  }

  .to {
    font-weight: bold;
  }
</style>
