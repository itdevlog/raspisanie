<script lang="ts">
  // Renders a single day payload through {@link ScheduleBody}: heading, the
  // teaching period / second-shift line (W40), holiday/weekend/no-period
  // notices, then the chosen lesson layout. `view` defaults to the original
  // «Компактный» look.
  import type { DaySchedule, ScheduleKind } from '../lib/api/types';
  import type { NowHint } from '../lib/schedule-view';
  import type { ScheduleView } from '../lib/stores/settings.svelte';
  import ScheduleBody from './schedule/ScheduleBody.svelte';

  interface Props {
    day: DaySchedule;
    kind: ScheduleKind;
    /**
     * W41: gate free-lesson strike-through on `STRIKEOUT_FREE_LSN`
     * (default `true` when absent). Forwarded to {@link ScheduleBody}.
     */
    strikeoutFreeLsn?: boolean;
    /** Show lesson numbers/times (user setting; forwarded to the layout). */
    showLessonTime?: boolean;
    /** Which layout to render; defaults to the original «Компактный». */
    view?: ScheduleView;
    /** Server current/next hint for the `nownext` layout (optional). */
    now?: NowHint | null;
  }
  let {
    day,
    kind,
    strikeoutFreeLsn = true,
    showLessonTime = true,
    view = 'compact',
    now = null,
  }: Props = $props();
</script>

<ScheduleBody {day} {kind} {view} {strikeoutFreeLsn} {showLessonTime} {now} />
