<script lang="ts">
  // Dispatcher for a single day's body: the shared day chrome (heading and
  // notices) plus the chosen lesson layout. The real Schedule screen and the
  // `/variants` comparison both render through here, so the preview can never
  // drift from the live screen.
  import type { DaySchedule, ScheduleKind } from '../../lib/api/types';
  import type { NowHint } from '../../lib/schedule-view';
  import type { ScheduleView } from '../../lib/stores/settings.svelte';
  import {
    dayState,
    dayTitle,
    isCancelled,
    isExchange,
    isHiddenFreeLesson,
  } from '../../lib/schedule-view';
  import ScheduleCards from './ScheduleCards.svelte';
  import ScheduleNowNext from './ScheduleNowNext.svelte';
  import ScheduleTable from './ScheduleTable.svelte';
  import ScheduleTimeline from './ScheduleTimeline.svelte';
  import StateNotice from '../StateNotice.svelte';

  interface Props {
    day: DaySchedule;
    kind: ScheduleKind;
    /** Which layout to render. */
    view: ScheduleView;
    /**
     * W41: gate free-lesson strike-through on `STRIKEOUT_FREE_LSN`
     * (default `true` when absent).
     */
    strikeoutFreeLsn?: boolean;
    /** Show lesson numbers/times (user setting). */
    showLessonTime?: boolean;
    /** Server current/next hint for the `nownext` layout (optional). */
    now?: NowHint | null;
    /**
     * Render the day chrome (heading/notices). `false` is used by the
     * `/variants` comparison, which supplies its own section captions.
     */
    chrome?: boolean;
    /** Show the day heading (`<h3>`); default `true`. */
    showHeading?: boolean;
  }
  let {
    day,
    kind,
    view,
    strikeoutFreeLsn = true,
    showLessonTime = true,
    now = null,
    chrome = true,
    showHeading = true,
  }: Props = $props();

  // W41 fix: when `STRIKEOUT_FREE_LSN` is off the site hides free/cancelled
  // rows. Filter them out first so notices and the empty state reflect what is
  // actually shown (mirrors `base_schedule_service.py` skipping cancelled items).
  const visibleLessons = $derived(
    day.lessons.filter((lesson) => !isHiddenFreeLesson(lesson, strikeoutFreeLsn)),
  );
  const state = $derived(dayState({ ...day, lessons: visibleLessons }));
  const hasExchanges = $derived(visibleLessons.some((lesson) => isExchange(lesson)));
  const hasCancellations = $derived(visibleLessons.some((lesson) => isCancelled(lesson)));
</script>

<section class="day">
  {#if chrome && showHeading}
    <h3>{dayTitle(day)}</h3>
  {/if}

  {#if chrome && state === 'vacation'}
    <StateNotice tone="muted" title="Каникулы" detail="В этот день занятий нет." />
  {:else if chrome && state === 'weekend'}
    <StateNotice tone="muted" title="Выходной" detail="В этот день занятий нет." />
  {:else if chrome && state === 'no_period'}
    <StateNotice tone="muted" title="Нет учебного периода" detail="Дата вне учебного периода." />
  {:else if chrome && state === 'empty'}
    <StateNotice title="Занятий нет" detail="Расписание на этот день пустое." />
  {:else}
    {#if chrome && hasExchanges}<StateNotice
        title="Есть замены"
        detail="Изменения отмечены ниже."
      />{/if}
    {#if chrome && hasCancellations}<StateNotice
        tone="error"
        title="Есть отмены"
        detail="Отменённые уроки зачёркнуты."
      />{/if}

    {#if view === 'cards'}
      <ScheduleCards lessons={visibleLessons} {kind} {showLessonTime} />
    {:else if view === 'table'}
      <ScheduleTable lessons={visibleLessons} {kind} {showLessonTime} />
    {:else if view === 'timeline'}
      <ScheduleTimeline lessons={visibleLessons} {kind} {showLessonTime} />
    {:else if view === 'nownext'}
      <ScheduleNowNext lessons={visibleLessons} {kind} {showLessonTime} {now} />
    {/if}
  {/if}
</section>

<style>
  .day {
    margin-bottom: var(--space-5);
  }

  h3 {
    font-size: var(--text-base);
    font-weight: bold;
    margin: 0 0 var(--space-2);
    padding-bottom: var(--space-1);
    border-bottom: 2px solid var(--color-accent);
    color: var(--color-accent);
  }
</style>
