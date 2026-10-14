<script lang="ts">
  // «Таймлайн» layout — a vertical time gutter with a dot per lesson and the
  // inter-lesson gaps drawn as visible breaks. Extracted from `/variants`.
  import type { Lesson, LessonItem, ScheduleKind } from '../../lib/api/types';
  import { isCancelled, isExchange, itemSubjectLabel, lessonTime } from '../../lib/schedule-view';
  import { formatDuration } from '../../lib/format';
  import ExchangeBadge from '../ExchangeBadge.svelte';

  interface Props {
    lessons: Lesson[];
    kind: ScheduleKind;
    showLessonTime?: boolean;
    /** Lesson number to highlight as the current/next one, or null. */
    heroNum?: number | null;
    /** Whether the highlighted lesson is in progress (else upcoming). */
    heroIsCurrent?: boolean;
  }
  let {
    lessons,
    kind,
    showLessonTime = true,
    heroNum = null,
    heroIsCurrent = false,
  }: Props = $props();

  const EMPTY_ITEM: LessonItem = {
    subject: null,
    teacher: null,
    room: null,
    class_name: null,
    groups: null,
    is_method_hour: false,
  };

  /** A lesson's items, or a single placeholder so free slots still render. */
  function effectiveItems(lesson: Lesson): LessonItem[] {
    return lesson.items.length > 0 ? lesson.items : [EMPTY_ITEM];
  }

  function toMinutes(value: string): number | null {
    const match = /^(\d{1,2}):(\d{2})$/.exec(value);
    if (!match) {
      return null;
    }
    return Number(match[1]) * 60 + Number(match[2]);
  }

  /** Free minutes between two lessons (0 when adjacent/overlapping/unknown). */
  function gapMinutes(previous: Lesson, next: Lesson): number {
    const end = toMinutes(previous.end);
    const start = toMinutes(next.start);
    if (end === null || start === null || start <= end) {
      return 0;
    }
    return start - end;
  }

  const showTeacher = $derived(kind !== 'teacher');
  const showRoom = $derived(kind !== 'room');
</script>

<ol class="timeline" class:no-time={!showLessonTime}>
  {#each lessons as lesson, index (lesson.num)}
    {#if index > 0}
      {@const gap = gapMinutes(lessons[index - 1], lesson)}
      {#if gap > 0}
        <li class="tl-gap" aria-hidden="true">
          <span class="tl-gap-line"></span>
          <span class="tl-gap-label">{formatDuration(gap)} перерыв</span>
        </li>
      {/if}
    {/if}
    <li
      class="tl-item"
      class:cancelled={isCancelled(lesson)}
      class:exchange={isExchange(lesson) && !isCancelled(lesson)}
      class:is-now={lesson.num === heroNum}
    >
      {#if showLessonTime}
        <div class="tl-time">
          <span class="num">{lesson.num}</span>
          <span class="clock">{lessonTime(lesson)}</span>
        </div>
      {/if}
      <span class="tl-marker" aria-hidden="true"></span>
      <div class="tl-card">
        {#if lesson.num === heroNum}
          <span class="now-eyebrow">{heroIsCurrent ? 'Сейчас' : 'Далее'}</span>
        {/if}
        {#each effectiveItems(lesson) as item, i (i)}
          <div class="tl-row">
            <span class="subject" class:method={item.is_method_hour}>{itemSubjectLabel(item)}</span>
            {#if item.groups}
              <span class="group">{item.groups}</span>
            {/if}
            {#if showTeacher && item.teacher}
              <span class="teacher">{item.teacher}</span>
            {/if}
            {#if showRoom && item.room}
              <span class="chip">{item.room}</span>
            {/if}
          </div>
        {/each}
        <ExchangeBadge {lesson} />
      </div>
    </li>
  {/each}
</ol>

<style>
  .timeline {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .tl-item {
    display: grid;
    grid-template-columns: 6rem 1rem 1fr;
    gap: var(--space-2);
    align-items: stretch;
  }

  .timeline.no-time .tl-item {
    grid-template-columns: 1rem 1fr;
  }

  .tl-time {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding-top: var(--space-3);
    text-align: right;
  }

  .tl-time .num {
    font-size: var(--text-xs);
    font-weight: bold;
    color: var(--lesson-num);
  }

  .tl-time .clock {
    font-size: var(--text-sm);
    font-weight: bold;
    color: var(--lesson-time);
    white-space: nowrap;
  }

  /* The vertical gutter: a continuous line with a dot per lesson. */
  .tl-marker {
    position: relative;
    background: var(--color-border);
    width: 2px;
    margin: 0 auto;
  }

  .tl-marker::before {
    content: '';
    position: absolute;
    top: var(--space-4);
    left: 50%;
    width: 10px;
    height: 10px;
    margin-left: -5px;
    border-radius: 50%;
    background: var(--color-accent);
  }

  .tl-item.cancelled .tl-marker::before {
    background: var(--color-cancel);
  }

  .tl-item.exchange .tl-marker::before {
    background: var(--color-exchange);
  }

  .tl-card {
    position: relative;
    margin: var(--space-2) 0;
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
  }

  .tl-item.is-now .tl-card {
    border-color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 10%, var(--color-surface));
    box-shadow: var(--shadow-md);
  }

  .tl-item.is-now .tl-marker::before {
    transform: scale(1.4);
  }

  .now-eyebrow {
    display: block;
    margin-bottom: var(--space-1);
    font-size: var(--text-xs);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-accent);
  }

  .tl-row {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
  }

  .subject {
    font-weight: 700;
    line-height: 1.25;
    color: var(--lesson-subject);
  }

  .subject.method {
    font-style: italic;
  }

  .group {
    font-size: var(--text-xs);
    font-weight: bold;
    color: var(--lesson-group);
  }

  .teacher {
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .chip {
    display: inline-block;
    padding: 1px var(--space-2);
    border-radius: 999px;
    border: 1px solid var(--color-border);
    background: var(--color-surface-2);
    font-size: var(--text-xs);
    font-weight: bold;
    color: var(--lesson-room);
    white-space: nowrap;
  }

  .clock,
  .num {
    font-variant-numeric: tabular-nums;
  }

  .tl-card .subject {
    flex-basis: 100%;
    font-size: var(--text-base);
  }

  .tl-gap {
    display: grid;
    grid-template-columns: 6rem 1rem 1fr;
    gap: var(--space-2);
    align-items: center;
    min-height: var(--space-5);
  }

  .timeline.no-time .tl-gap {
    grid-template-columns: 1rem 1fr;
  }

  .tl-gap-line {
    grid-column: 2;
    justify-self: center;
    width: 2px;
    height: 100%;
    background: repeating-linear-gradient(
      to bottom,
      var(--color-border) 0,
      var(--color-border) 4px,
      transparent 4px,
      transparent 8px
    );
  }

  .timeline.no-time .tl-gap-line {
    grid-column: 1;
  }

  .tl-gap-label {
    grid-column: 3;
    font-size: var(--text-xs);
    color: var(--color-muted);
    font-style: italic;
  }

  .timeline.no-time .tl-gap-label {
    grid-column: 2;
  }

  .cancelled .subject {
    color: var(--color-cancel);
    text-decoration: line-through;
  }

  .exchange .subject {
    color: var(--color-exchange);
  }
</style>
