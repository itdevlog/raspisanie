<script lang="ts">
  // One lesson row: number + time, every parallel item (subject/group/teacher/
  // room/class), a «Метод. час» label for method hours, and a status marker for
  // substitutions/cancellations. Subject-less "free" lessons are struck through.
  import type { Lesson } from '../lib/api/types';
  import {
    isCancelled,
    isExchange,
    isFreeLesson,
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
</script>

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

<style>
  .lesson {
    padding: 0.5rem 0.6rem;
    border: 1px solid color-mix(in srgb, currentColor 18%, transparent);
    border-radius: 0.5rem;
    margin-bottom: 0.4rem;
  }

  .lesson.exchange {
    border-left: 4px solid #f0a000;
    background: color-mix(in srgb, #f0a000 12%, transparent);
  }

  .lesson.cancelled {
    border-left: 4px solid #b00020;
    background: color-mix(in srgb, #b00020 10%, transparent);
    opacity: 0.85;
  }

  .head {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }

  .num {
    font-weight: 700;
  }

  .time {
    font-variant-numeric: tabular-nums;
  }

  .badge {
    margin-left: auto;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }

  .cancelled .subject {
    text-decoration: line-through;
  }

  .lesson.free {
    opacity: 0.65;
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
    margin: 0.25rem 0 0;
    padding: 0;
    display: grid;
    gap: 0.15rem;
  }

  .item {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .subject {
    font-weight: 500;
  }

  .meta {
    display: flex;
    gap: 0.5rem;
    opacity: 0.75;
    font-size: 0.9rem;
  }
</style>
