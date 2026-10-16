<script lang="ts">
  // «Таблица» layout — dense, aligned columns. Three columns: a merged
  // number/time cell (shared by a multi-item lesson via `rowspan`), the subject
  // (with the group, the nested teacher line and the status badge) and the room.
  // Extracted from `/variants`.
  import type { Lesson, LessonItem, ScheduleKind } from '../../lib/api/types';
  import { isCancelled, isExchange, itemSubjectLabel, lessonTime } from '../../lib/schedule-view';
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

  const showTeacher = $derived(kind !== 'teacher');
  const showRoom = $derived(kind !== 'room');
</script>

<table class="grid">
  <thead>
    <tr>
      <th scope="col">{showLessonTime ? '№ Время' : '№'}</th>
      <th scope="col">Предмет</th>
      {#if showRoom}
        <th scope="col">Кабинет</th>
      {/if}
    </tr>
  </thead>
  <tbody>
    {#each lessons as lesson (lesson.num)}
      {@const items = effectiveItems(lesson)}
      {#each items as item, i (i)}
        <tr
          class:cancelled={isCancelled(lesson)}
          class:exchange={isExchange(lesson) && !isCancelled(lesson)}
          class:is-now={lesson.num === heroNum}
        >
          {#if i === 0}
            <td class="num-time" rowspan={items.length}>
              <span class="num">{lesson.num}</span>
              {#if showLessonTime}
                <span class="clock">{lessonTime(lesson)}</span>
              {/if}
            </td>
          {/if}
          <td class="subject-cell">
            {#if i === 0 && lesson.num === heroNum}
              <span class="now-eyebrow">{heroIsCurrent ? 'Сейчас' : 'Далее'}</span>
            {/if}
            <span class="subject-line">
              <span class="subject" class:method={item.is_method_hour}
                >{itemSubjectLabel(item)}</span
              >
              {#if item.groups}
                <span class="group">{item.groups}</span>
              {/if}
            </span>
            {#if showTeacher && item.teacher}
              <span class="teacher">{item.teacher}</span>
            {/if}
            {#if i === 0}
              <ExchangeBadge {lesson} />
            {/if}
          </td>
          {#if showRoom}
            <td class="room-cell">
              {#if item.room}
                <span class="chip">{item.room}</span>
              {:else}
                —
              {/if}
            </td>
          {/if}
        </tr>
      {/each}
    {/each}
  </tbody>
</table>

<style>
  .grid {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
  }

  .grid th,
  .grid td {
    text-align: left;
    padding: var(--space-2) var(--space-1);
    border-bottom: 1px solid var(--color-border);
    vertical-align: top;
  }

  .grid thead th {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-muted);
    border-bottom: 2px solid var(--color-border);
  }

  /* Column 1 — lesson number above its time; shared by every item row. */
  .grid .num-time {
    width: 5.5rem;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  .grid .num-time .num {
    display: block;
    font-weight: bold;
    color: var(--lesson-num);
  }

  .grid .num-time .clock {
    display: block;
    color: var(--lesson-time);
    white-space: nowrap;
  }

  .grid tr.is-now td {
    background: color-mix(in srgb, var(--color-accent) 10%, var(--color-surface));
  }

  .now-eyebrow {
    display: block;
    font-size: var(--text-xs);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-accent);
  }

  /* Column 2 — subject + optional group, with the teacher as a muted line
     underneath and the status badge on the lesson's first row. */
  .grid .subject-cell {
    min-width: 8rem;
  }

  .subject-line {
    display: block;
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
    margin-left: var(--space-2);
    font-size: var(--text-xs);
    font-weight: bold;
    color: var(--lesson-group);
  }

  .teacher {
    display: block;
    font-size: var(--text-xs);
    color: var(--color-muted);
  }

  /* Column 3 — the room chip, never broken mid-word. */
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

  /* The «Замена»/«Отменён» pill lives inside ExchangeBadge; keep it on one line. */
  .grid :global(.badge) {
    white-space: nowrap;
  }

  .grid .subject {
    font-size: var(--text-sm);
  }

  .cancelled .subject {
    color: var(--color-cancel);
    text-decoration: line-through;
  }

  .exchange .subject {
    color: var(--color-exchange);
  }
</style>
