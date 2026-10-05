<script lang="ts">
  // Renders a full week (Mon–Fri) as a stack of {@link DayView}s.
  import type { ScheduleKind, WeekScheduleResponse } from '../lib/api/types';
  import DayView from './DayView.svelte';

  interface Props {
    week: WeekScheduleResponse;
    kind: ScheduleKind;
  }
  let { week, kind }: Props = $props();
</script>

<div class="week">
  {#each week.days as day (day.date)}
    <DayView {day} {kind} />
  {/each}
</div>

<style>
  .week {
    display: block;
  }
</style>
