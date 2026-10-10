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
    /** Show the lesson number and time (user setting; default `true`). */
    showTime?: boolean;
  }
  let {
    lesson,
    showRoom = true,
    showTeacher = true,
    showClass = false,
    strikeoutFreeLsn = true,
    showTime = true,
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
      {#if showTime}<span class="num">{lesson.num}</span>{/if}
      {#if showTime && time}<span class="time">{time}</span>{/if}
      {#if status}<span class="badge">{status}</span>{/if}
    </div>
    <ul class="items">
      {#each lesson.items as item, i (i)}
        <li class="item">
          <span class="subject" class:method={item.is_method_hour}>{itemSubjectLabel(item)}</span>
          <span class="meta">
            {#if item.groups}<span class="group">{item.groups}</span>{/if}
            {#if showTeacher && item.teacher}<span class="teacher">{item.teacher}</span>{/if}
            {#if showRoom && item.room}<span class="room">каб. {item.room}</span>{/if}
            {#if showClass && item.class_name}<span class="class-name">{item.class_name}</span>{/if}
          </span>
        </li>
      {/each}
    </ul>
  </li>
{/if}

<style>
  /* Original lesson row: a plain white band with a thin separator, colour-coded
     text (gray number, green time, blue subject, italic teacher, bold room). */
  .lesson {
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--color-border);
    background: transparent;
    color: var(--lesson-subject);
  }

  .lesson.exchange {
    color: var(--lesson-exchange);
  }

  .lesson.cancelled {
    color: var(--lesson-cancel);
  }

  .lesson.cancelled .subject {
    text-decoration: line-through;
  }

  .lesson.free .subject {
    text-decoration: line-through;
  }

  .head {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
  }

  .num {
    display: inline-block;
    min-width: 1.2em;
    color: var(--lesson-num);
    font-weight: bold;
    line-height: 1;
  }

  .time {
    font-variant-numeric: tabular-nums;
    color: var(--lesson-time);
    font-size: var(--text-sm);
  }

  .badge {
    margin-left: auto;
    font-size: var(--text-xs);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .lesson.exchange .badge {
    color: var(--lesson-exchange);
  }

  .lesson.cancelled .badge {
    color: var(--lesson-cancel);
  }

  .items {
    list-style: none;
    margin: var(--space-1) 0 0;
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
    color: var(--lesson-subject);
    font-weight: bold;
  }

  .subject.method {
    font-style: italic;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    font-size: var(--text-sm);
  }

  .teacher {
    color: var(--lesson-teacher);
    font-style: italic;
  }

  .room {
    color: var(--lesson-room);
    font-weight: bold;
  }

  .class-name {
    color: var(--lesson-subject);
  }

  .group {
    color: var(--lesson-group);
    font-weight: bold;
  }
</style>
