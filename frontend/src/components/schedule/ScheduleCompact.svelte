<script lang="ts">
  // «Компактный» layout — the original Schedule look: a plain lesson list with
  // one {@link LessonRow} per lesson. Extracted from `DayView` so the real
  // screen and the `/variants` preview share the exact same rendering.
  import type { Lesson, ScheduleKind } from '../../lib/api/types';
  import LessonRow from '../LessonRow.svelte';

  interface Props {
    /** Already filtered lessons (hidden free/cancelled rows are removed). */
    lessons: Lesson[];
    kind: ScheduleKind;
    /** W41: gate free-lesson strike-through on `STRIKEOUT_FREE_LSN`. */
    strikeoutFreeLsn?: boolean;
    /** Show lesson numbers/times (user setting). */
    showLessonTime?: boolean;
  }
  let { lessons, kind, strikeoutFreeLsn = true, showLessonTime = true }: Props = $props();
</script>

<ul class="lessons">
  {#each lessons as lesson (lesson.num)}
    <LessonRow
      {lesson}
      {strikeoutFreeLsn}
      showTime={showLessonTime}
      showRoom={kind !== 'room'}
      showTeacher={kind !== 'teacher'}
      showClass={kind !== 'class'}
    />
  {/each}
</ul>

<style>
  .lessons {
    list-style: none;
    margin: var(--space-2) 0 0;
    padding: 0;
  }
</style>
