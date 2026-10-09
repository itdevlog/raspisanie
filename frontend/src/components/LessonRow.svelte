<script lang="ts">
  // One lesson row: number + time, every parallel item (subject/group/teacher/
  // room/class), a «Метод. час» label for method hours, and a status marker for
  // substitutions/cancellations. Subject-less "free" lessons are struck through.
  import type { Lesson } from '../lib/api/types';
  import {
    isCancelled,
    isExchange,
    isFreeLesson,
    isHiddenFreeLesson,
    itemSubjectLabel,
    lessonStatusLabel,
    lessonTime,
  } from '../lib/schedule-view';

  interface Props {
    lesson: Lesson;
    /** Hide the room column when viewing a room's own schedule. */
    showRoom?: boolean;
    /** Hide the teacher column when viewing a teacher's own schedule. */
    showTeacher?: boolean;
    /** Hide the class column when viewing a class's own schedule. */
    showClass?: boolean;
    /**
     * W41: gate the free-lesson strike-through on `STRIKEOUT_FREE_LSN`.
     * Defaults to `true` (server/flag default) when absent.
     */
    strikeoutFreeLsn?: boolean;
  }
  let {
    lesson,
    showRoom = true,
    showTeacher = true,
    showClass = false,
    strikeoutFreeLsn = true,
  }: Props = $props();

  const status = $derived(lessonStatusLabel(lesson));
  const time = $derived(lessonTime(lesson));
  const free = $derived(isFreeLesson(lesson, strikeoutFreeLsn));
  // W41 fix: with the flag off the site hides free/cancelled rows entirely.
  const hidden = $derived(isHiddenFreeLesson(lesson, strikeoutFreeLsn));
</script>

{#if !hidden}
  <li
    class="lesson"
    class:exchange={isExchange(lesson) && !isCancelled(lesson)}
    class:cancelled={isCancelled(lesson)}
    class:free
    aria-label={status ? 'Урок {lesson.num}: {status}' : undefined}
  >
    <div class="head">
      <span class="num">{lesson.num}</span>
      {#if time}<span class="time">{time}</span>{/if}
      {#if status}<span class="badge">{status}</span>{/if}
    </div>
    <ul class="items">
      {#each lesson.items as item, i (i)}
        <li class="item">
          <span class="subject" class:method={item.is_method_hour}>{itemSubjectLabel(item)}</span>
          <span class="meta">
            {#if item.groups}<span class="group">{item.groups}</span>{/if}
            {#if showTeacher && item.teacher}<span>{item.teacher}</span>{/if}
            {#if showRoom && item.room}<span>каб. {item.room}</span>{/if}
            {#if showClass && item.class_name}<span>{item.class_name}</span>{/if}
          </span>
        </li>
      {/each}
    </ul>
  </li>
{/if}

<style>
  .lesson {
    padding: var(--space-3) var(--space-4);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-surface);
    box-shadow: var(--shadow-sm);
    margin-bottom: var(--space-3);
  }

  .lesson.exchange {
    border-left: 3px solid var(--color-exchange);
  }

  .lesson.cancelled {
    border-left: 3px solid var(--color-cancel);
  }

  .lesson.exchange .badge {
    color: var(--color-exchange);
  }

  .lesson.cancelled .badge {
    color: var(--color-cancel);
  }

  .head {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
  }

  .num {
    font-weight: 700;
  }

  .time {
    font-variant-numeric: tabular-nums;
    color: var(--color-muted);
    font-size: var(--text-sm);
  }

  .badge {
    margin-left: auto;
    font-size: var(--text-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .cancelled .subject {
    text-decoration: line-through;
  }

  .lesson.free {
    opacity: 0.6;
  }

  .lesson.free .subject {
    text-decoration: line-through;
  }

  .subject.method {
    font-style: italic;
    font-weight: 600;
  }

  .group {
    font-weight: 600;
  }

  .items {
    list-style: none;
    margin: var(--space-2) 0 0;
    padding: 0;
    display: grid;
    gap: var(--space-1);
  }

  .item {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: baseline;
  }

  .subject {
    font-weight: 500;
  }

  .meta {
    display: flex;
    gap: var(--space-2);
    color: var(--color-muted);
    font-size: var(--text-sm);
  }
</style>
