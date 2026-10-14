<script lang="ts">
  // «Таблица» layout — dense, aligned columns. Multi-item lessons use a
  // `rowspan` on the shared number/time cells. Extracted from `/variants`.
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
  }
  let { lessons, kind, showLessonTime = true }: Props = $props();

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
      {#if showLessonTime}
        <th scope="col">№</th>
        <th scope="col">Время</th>
      {/if}
      <th scope="col">Предмет</th>
      {#if showTeacher}
        <th scope="col">Учитель</th>
      {/if}
      {#if showRoom}
        <th scope="col">Кабинет</th>
      {/if}
    </tr>
  </thead>
  <tbody>
    {#each lessons as lesson (lesson.num)}
      {#each effectiveItems(lesson) as item, i (i)}
        <tr
          class:cancelled={isCancelled(lesson)}
          class:exchange={isExchange(lesson) && !isCancelled(lesson)}
        >
          {#if showLessonTime && i === 0}
            <td class="num" rowspan={effectiveItems(lesson).length}>{lesson.num}</td>
            <td class="clock" rowspan={effectiveItems(lesson).length}>{lessonTime(lesson)}</td>
          {/if}
          <td>
            <span class="subject" class:method={item.is_method_hour}>{itemSubjectLabel(item)}</span>
            {#if item.groups}
              <span class="group">{item.groups}</span>
            {/if}
            {#if i === 0 && lessonStatusLabel(lesson)}
              <span class="badge">{lessonStatusLabel(lesson)}</span>
            {/if}
          </td>
          {#if showTeacher}
            <td class="teacher">{item.teacher ?? '—'}</td>
          {/if}
          {#if showRoom}
            <td>
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
    table-layout: fixed;
    border-collapse: collapse;
    font-size: var(--text-sm);
  }

  .grid th,
  .grid td {
    text-align: left;
    padding: var(--space-2) var(--space-1);
    border-bottom: 1px solid var(--color-border);
    vertical-align: top;
    overflow-wrap: anywhere;
  }

  .grid thead th {
    font-size: var(--text-xs);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-muted);
    border-bottom: 2px solid var(--color-border);
  }

  .grid .num {
    width: 2.25rem;
    font-weight: bold;
    color: var(--lesson-num);
  }

  .grid .clock {
    width: 5rem;
    color: var(--lesson-time);
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

  .cancelled .badge {
    color: var(--color-cancel);
    background: var(--color-cancel-soft);
  }

  .exchange .badge {
    color: var(--color-exchange);
    background: var(--color-exchange-soft);
  }
</style>
