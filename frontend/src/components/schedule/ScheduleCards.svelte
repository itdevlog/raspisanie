<script lang="ts">
  // «Карточки» layout — one card per lesson: a fixed-width time column plus a
  // strong subject, muted teacher and room chip. Extracted from `/variants`.
  import type { Lesson, LessonItem, ScheduleKind } from '../../lib/api/types';
  import {
    isCancelled,
    isExchange,
    itemSubjectLabel,
    lessonStatusLabel,
    lessonTime,
  } from '../../lib/schedule-view';

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

  const showTeacher = $derived(kind !== 'teacher');
  const showRoom = $derived(kind !== 'room');
</script>

<ul class="cards">
  {#each lessons as lesson (lesson.num)}
    <li
      class="card"
      class:no-time={!showLessonTime}
      class:cancelled={isCancelled(lesson)}
      class:exchange={isExchange(lesson) && !isCancelled(lesson)}
      class:is-now={lesson.num === heroNum}
    >
      {#if lesson.num === heroNum}
        <span class="now-eyebrow">{heroIsCurrent ? 'Сейчас' : 'Далее'}</span>
      {/if}
      {#if showLessonTime}
        <div class="card-time">
          <span class="num">{lesson.num}</span>
          <span class="clock">{lessonTime(lesson)}</span>
        </div>
      {/if}
      <div class="card-body">
        {#each effectiveItems(lesson) as item, i (i)}
          <div class="card-item">
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
      </div>
      {#if lessonStatusLabel(lesson)}
        <span class="badge">{lessonStatusLabel(lesson)}</span>
      {/if}
    </li>
  {/each}
</ul>

<style>
  .cards {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-3);
  }

  .card {
    display: grid;
    grid-template-columns: 5.5rem 1fr auto;
    gap: var(--space-3);
    align-items: start;
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-left: 4px solid var(--color-accent);
    border-radius: var(--radius-lg);
    background: var(--color-surface);
    box-shadow: var(--shadow-sm);
  }

  .card.no-time {
    grid-template-columns: 1fr auto;
  }

  .card.cancelled {
    border-left-color: var(--color-cancel);
  }

  .card.exchange {
    border-left-color: var(--color-exchange);
  }

  .card.is-now {
    border-left-width: 6px;
    background: color-mix(in srgb, var(--color-accent) 10%, var(--color-surface));
    box-shadow: var(--shadow-md);
  }

  .now-eyebrow {
    grid-column: 1 / -1;
    font-size: var(--text-xs);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-accent);
  }

  .card-time {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .card-time .num {
    font-size: var(--text-xs);
    font-weight: bold;
    color: var(--lesson-num);
  }

  .card-time .clock {
    font-size: var(--text-sm);
    font-weight: bold;
    color: var(--lesson-time);
  }

  .card-body {
    display: grid;
    gap: var(--space-2);
    min-width: 0;
  }

  .card-item {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
  }

  .card-item .subject {
    flex-basis: 100%;
    font-size: var(--text-lg);
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

  .badge {
    display: inline-block;
    padding: 1px var(--space-2);
    border-radius: 999px;
    font-size: var(--text-xs);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .clock,
  .num {
    font-variant-numeric: tabular-nums;
  }

  .cancelled .subject {
    color: var(--color-cancel);
    text-decoration: line-through;
  }

  .exchange .subject {
    color: var(--color-exchange);
  }

  .cancelled .badge {
    color: var(--color-cancel);
    background: var(--color-cancel-soft);
  }

  .exchange .badge {
    color: var(--color-exchange);
    background: var(--color-exchange-soft);
  }
</style>
