<script lang="ts">
  // Renders a single day payload through {@link ScheduleBody}: heading,
  // holiday/weekend/no-period notices, then the chosen lesson layout. `view`
  // defaults to the «Карточки» look.
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
    /** Which layout to render; defaults to «Карточки». */
    view?: ScheduleView;
    /** Server current/next hint for the `nownext` layout (optional). */
    now?: NowHint | null;
    /** Render the day heading; Task 3 passes `false` in day mode. */
    showHeading?: boolean;
  }
  let {
    day,
    kind,
    strikeoutFreeLsn = true,
    showLessonTime = true,
    view = 'cards',
    now = null,
    showHeading = true,
  }: Props = $props();
</script>

<ScheduleBody {day} {kind} {view} {strikeoutFreeLsn} {showLessonTime} {now} {showHeading} />
