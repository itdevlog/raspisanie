<script lang="ts">
  // Renders a single day payload: heading, the teaching period / second-shift
  // line (W40), holiday/weekend/no-period notices, or the list of lessons.
  import type { DaySchedule, ScheduleKind } from '../lib/api/types';
  import {
    dayState,
    dayTitle,
    isCancelled,
    isExchange,
    isHiddenFreeLesson,
    periodLabel,
    shiftLabel,
  } from '../lib/schedule-view';
  import LessonRow from './LessonRow.svelte';
  import StateNotice from './StateNotice.svelte';

  interface Props {
    day: DaySchedule;
    kind: ScheduleKind;
    /**
     * W41: gate free-lesson strike-through on `STRIKEOUT_FREE_LSN`
     * (default `true` when absent). Forwarded to every {@link LessonRow}.
     */
    strikeoutFreeLsn?: boolean;
  }
  let { day, kind, strikeoutFreeLsn = true }: Props = $props();

  // W41 fix: when `STRIKEOUT_FREE_LSN` is off the site hides free/cancelled
  // rows. Filter them out first so notices and the empty state reflect what is
  // actually shown (mirrors `base_schedule_service.py` skipping cancelled items).
  const visibleLessons = $derived(
    day.lessons.filter((lesson) => !isHiddenFreeLesson(lesson, strikeoutFreeLsn)),
  );
  const state = $derived(dayState({ ...day, lessons: visibleLessons }));
  const hasExchanges = $derived(visibleLessons.some((lesson) => isExchange(lesson)));
  const hasCancellations = $derived(visibleLessons.some((lesson) => isCancelled(lesson)));
  const period = $derived(periodLabel(day.period));
  const shift = $derived(shiftLabel(day.shift));
</script>

<section class="day">
  <h3>{dayTitle(day)}</h3>

  {#if period}
    <p class="period">{period}</p>
  {/if}
  {#if shift}
    <p class="shift" data-shift={day.shift}>{shift}</p>
  {/if}

  {#if state === 'vacation'}
    <StateNotice tone="muted" title="Каникулы" detail="В этот день занятий нет." />
  {:else if state === 'weekend'}
    <StateNotice tone="muted" title="Выходной" detail="В этот день занятий нет." />
  {:else if state === 'no_period'}
    <StateNotice tone="muted" title="Нет учебного периода" detail="Дата вне учебного периода." />
  {:else if state === 'empty'}
    <StateNotice title="Занятий нет" detail="Расписание на этот день пустое." />
  {:else}
    {#if hasExchanges}<StateNotice title="Есть замены" detail="Изменения отмечены ниже." />{/if}
    {#if hasCancellations}<StateNotice
        tone="error"
        title="Есть отмены"
        detail="Отменённые уроки зачёркнуты."
      />{/if}
    <ul class="lessons">
      {#each visibleLessons as lesson (lesson.num)}
        <LessonRow
          {lesson}
          {strikeoutFreeLsn}
          showRoom={kind !== 'room'}
          showTeacher={kind !== 'teacher'}
          showClass={kind !== 'class'}
        />
      {/each}
    </ul>
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

  .period {
    margin: 0 0 var(--space-1);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .shift {
    margin: 0 0 var(--space-1);
    font-size: var(--text-xs);
    font-weight: bold;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-muted);
  }

  .lessons {
    list-style: none;
    margin: var(--space-2) 0 0;
    padding: 0;
  }
</style>
