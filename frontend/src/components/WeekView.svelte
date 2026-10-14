<script lang="ts">
  // Renders a full week (Mon–Fri) as a stack of {@link DayView}s.
  import type { ScheduleKind, WeekScheduleResponse } from '../lib/api/types';
  import type { ScheduleView } from '../lib/stores/settings.svelte';
  import DayView from './DayView.svelte';

  interface Props {
    week: WeekScheduleResponse;
    kind: ScheduleKind;
    /** W41 fix: school `STRIKEOUT_FREE_LSN` flag forwarded to every day. */
    strikeoutFreeLsn?: boolean;
    /** Show lesson numbers/times (user setting; forwarded to every day). */
    showLessonTime?: boolean;
    /** Day layout for every day in the week; defaults to «Карточки». */
    view?: ScheduleView;
  }
  let {
    week,
    kind,
    strikeoutFreeLsn = true,
    showLessonTime = true,
    view = 'cards',
  }: Props = $props();

  // A hero card per day would be odd in a week grid, so `nownext` falls back to
  // the cards list for each day (the week has no single "current" lesson).
  const perDayView = $derived(view === 'nownext' ? 'cards' : view);
</script>

<div class="week">
  {#each week.days as day (day.date)}
    <DayView {day} {kind} {strikeoutFreeLsn} {showLessonTime} view={perDayView} />
  {/each}
</div>

<style>
  .week {
    display: block;
  }

  /* Thin divider between stacked days; the first day needs no rule. */
  .week :global(.day + .day) {
    border-top: 1px solid var(--color-border);
    padding-top: var(--space-4);
  }
</style>
