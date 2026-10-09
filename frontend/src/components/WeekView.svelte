<script lang="ts">
  // Renders a full week (Mon–Fri) as a stack of {@link DayView}s.
  import type { ScheduleKind, WeekScheduleResponse } from '../lib/api/types';
  import DayView from './DayView.svelte';

  interface Props {
    week: WeekScheduleResponse;
    kind: ScheduleKind;
    /** W41 fix: school `STRIKEOUT_FREE_LSN` flag forwarded to every day. */
    strikeoutFreeLsn?: boolean;
  }
  let { week, kind, strikeoutFreeLsn = true }: Props = $props();
</script>

<div class="week">
  {#each week.days as day (day.date)}
    <DayView {day} {kind} {strikeoutFreeLsn} />
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
