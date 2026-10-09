<script lang="ts">
  // W39 «идёт урок / до начала» widget.
  //
  // Presentational: the Home screen owns the `/now` request and passes the
  // discriminated status + payload in. `current` wins over `next`; when both are
  // null (day over, weekend, no lessons) a muted notice is shown.
  import type { AsyncStatus } from '../lib/async.svelte';
  import type { LessonSummary, NowResponse } from '../lib/api/types';
  import StateNotice from './StateNotice.svelte';

  interface Props {
    data: NowResponse | null;
    status: AsyncStatus;
    error: string | null;
  }
  let { data, status, error }: Props = $props();

  /** `2. Физика · каб. 202 · 09:00-09:45`, skipping absent fields. */
  function summaryLine(lesson: LessonSummary): string {
    const parts = [`${lesson.num}. ${lesson.subject || 'Урок'}`];
    if (lesson.room) {
      parts.push(`каб. ${lesson.room}`);
    }
    if (lesson.time) {
      parts.push(lesson.time);
    }
    return parts.join(' · ');
  }

  const current = $derived(data?.current ?? null);
  const next = $derived(data?.next ?? null);
</script>

<section class="now">
  <h3>Сейчас</h3>

  {#if status === 'error'}
    <StateNotice tone="error" title="Не удалось загрузить текущий урок" detail={error ?? ''} />
  {:else if status === 'loading' || status === 'idle'}
    <p role="status">Загрузка…</p>
  {:else if current}
    <p class="lesson" role="status">
      <strong>Идёт урок</strong>
      <span class="detail">{summaryLine(current)}</span>
      <span class="hint">осталось {current.in_minutes} мин</span>
    </p>
  {:else if next}
    <p class="lesson" role="status">
      <strong>До начала</strong>
      <span class="detail">{summaryLine(next)}</span>
      <span class="hint">через {next.in_minutes} мин</span>
    </p>
  {:else}
    <StateNotice tone="muted" title="Уроков нет" detail="На сегодня уроков больше нет." />
  {/if}
</section>

<style>
  .now {
    margin-bottom: var(--space-5);
  }

  h3 {
    font-size: var(--text-lg);
    margin: 0 0 var(--space-2);
  }

  .lesson {
    margin: var(--space-2) 0 var(--space-4);
    padding: var(--space-5);
    border-radius: var(--radius-lg);
    border: 1px solid var(--color-border);
    background: var(--color-surface);
    box-shadow: var(--shadow-sm);
  }

  .lesson strong {
    display: block;
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--color-muted);
  }

  .detail {
    display: block;
    margin-top: var(--space-2);
    font-size: var(--text-lg);
    font-weight: 500;
  }

  .hint {
    display: block;
    margin-top: var(--space-1);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  [role='status'] {
    color: var(--color-muted);
  }

  .lesson[role='status'] {
    color: var(--color-text);
  }
</style>
