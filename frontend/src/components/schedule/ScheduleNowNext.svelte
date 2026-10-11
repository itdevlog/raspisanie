<script lang="ts">
  // «Сейчас / далее» layout — a hero card for the current/next lesson plus a
  // compact list of the rest. The server `/now` hint (lesson numbers) picks the
  // hero; without a reliable hint the first lesson is featured. Extracted from
  // `/variants`.
  import type { Lesson, LessonItem, ScheduleKind } from '../../lib/api/types';
  import {
    isCancelled,
    isExchange,
    itemSubjectLabel,
    lessonStatusLabel,
    lessonTime,
    pickNowNext,
    type NowHint,
  } from '../../lib/schedule-view';
  import StateNotice from '../StateNotice.svelte';

  interface Props {
    lessons: Lesson[];
    kind: ScheduleKind;
    showLessonTime?: boolean;
    /** Server current/next lesson numbers, or `null` when unavailable. */
    now?: NowHint | null;
  }
  let { lessons, kind, showLessonTime = true, now = null }: Props = $props();

  const EMPTY_ITEM: LessonItem = {
    subject: null,
    teacher: null,
    room: null,
    class_name: null,
    groups: null,
    is_method_hour: false,
  };

  /** The lesson's first item (or a placeholder) for the hero layout. */
  function firstItem(lesson: Lesson): LessonItem {
    return lesson.items[0] ?? EMPTY_ITEM;
  }

  const showTeacher = $derived(kind !== 'teacher');
  const showRoom = $derived(kind !== 'room');
  const pick = $derived(pickNowNext(lessons, now));
</script>

{#if pick.hero}
  {@const hero = pick.hero}
  <article
    class="hero"
    class:cancelled={isCancelled(hero)}
    class:exchange={isExchange(hero) && !isCancelled(hero)}
  >
    <span class="hero-eyebrow">{pick.heroIsCurrent ? 'Сейчас' : 'Далее'}</span>
    <div class="hero-top">
      {#if showLessonTime}
        <span class="clock hero-clock">{lessonTime(hero)}</span>
        <span class="num">Урок {hero.num}</span>
      {/if}
      {#if lessonStatusLabel(hero)}
        <span class="badge">{lessonStatusLabel(hero)}</span>
      {/if}
    </div>
    <span class="subject hero-subject" class:method={firstItem(hero).is_method_hour}>
      {itemSubjectLabel(firstItem(hero))}
    </span>
    <div class="hero-meta">
      {#if firstItem(hero).groups}
        <span class="group">{firstItem(hero).groups}</span>
      {/if}
      {#if showTeacher && firstItem(hero).teacher}
        <span class="teacher">{firstItem(hero).teacher}</span>
      {/if}
      {#if showRoom && firstItem(hero).room}
        <span class="chip">{firstItem(hero).room}</span>
      {/if}
    </div>
  </article>

  {#if pick.rest.length > 0}
    <ol class="rest">
      {#each pick.rest as lesson (lesson.num)}
        <li
          class="rest-item"
          class:cancelled={isCancelled(lesson)}
          class:exchange={isExchange(lesson) && !isCancelled(lesson)}
        >
          {#if showLessonTime}
            <span class="num">{lesson.num}</span>
            <span class="clock">{lessonTime(lesson)}</span>
          {/if}
          <span class="subject" class:method={firstItem(lesson).is_method_hour}>
            {itemSubjectLabel(firstItem(lesson))}
          </span>
          {#if showRoom && firstItem(lesson).room}
            <span class="chip">{firstItem(lesson).room}</span>
          {/if}
        </li>
      {/each}
    </ol>
  {/if}
{:else}
  <StateNotice title="Занятий нет" detail="Расписание на этот день пустое." />
{/if}

<style>
  .hero {
    display: grid;
    gap: var(--space-2);
    padding: var(--space-4);
    border: 1px solid var(--color-border);
    border-left: 6px solid var(--color-accent);
    border-radius: var(--radius-lg);
    background: var(--color-surface);
    box-shadow: var(--shadow-md);
  }

  .hero.cancelled {
    border-left-color: var(--color-cancel);
  }

  .hero.exchange {
    border-left-color: var(--color-exchange);
  }

  .hero-eyebrow {
    font-size: var(--text-xs);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--color-muted);
  }

  .hero-top {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
  }

  .hero-clock {
    font-size: var(--text-lg);
    font-weight: bold;
    color: var(--lesson-time);
  }

  .hero-top .num {
    font-size: var(--text-sm);
    color: var(--lesson-num);
  }

  .hero-subject {
    font-size: var(--text-xl);
  }

  .hero-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }

  .rest {
    list-style: none;
    margin: var(--space-3) 0 0;
    padding: 0;
  }

  .rest-item {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--color-border);
  }

  .rest-item .num {
    min-width: 1.2em;
    font-weight: bold;
    color: var(--lesson-num);
  }

  .rest-item .clock {
    min-width: 6rem;
    font-size: var(--text-sm);
    color: var(--lesson-time);
  }

  .rest-item .subject {
    flex: 1;
    min-width: 8rem;
    font-size: var(--text-base);
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
