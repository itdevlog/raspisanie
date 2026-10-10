<script lang="ts">
  // /variants — a read-only comparison screen: the SAME day rendered in five
  // alternative layouts so the best one can be picked before touching the real
  // Schedule screen.
  //
  // Data: the currently selected entity's day (selection + client.getDay) when
  // available; otherwise the built-in {@link SAMPLE_DAY} (school_133-shaped:
  // 6–7 lessons, a split group, a substitution, a cancellation, a method hour).
  // The page always renders, even with no school selected.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    createAsync,
    isCancelled,
    isExchange,
    isHiddenFreeLesson,
    itemSubjectLabel,
    lessonStatusLabel,
    lessonTime,
    SAMPLE_DAY,
    type DaySchedule,
    type Lesson,
    type LessonItem,
    type ScheduleApiClient,
    type SelectionStore,
    type TodayStore,
  } from '../lib';
  import DayView from '../components/DayView.svelte';
  import StateNotice from '../components/StateNotice.svelte';

  interface Props {
    client?: ScheduleApiClient;
    selection?: SelectionStore;
    today?: TodayStore;
    /** W41: gate free-lesson hiding on the school flag (default `true`). */
    strikeoutFreeLsn?: boolean;
    /** Return to the previous screen. */
    onBack?: () => void;
  }
  let {
    client = defaultApi,
    selection = defaultSelection,
    today = defaultToday,
    strikeoutFreeLsn = true,
    onBack,
  }: Props = $props();

  /** The preview payload plus whether it came from the built-in sample. */
  interface Preview {
    day: DaySchedule;
    sample: boolean;
  }

  // The day to preview. Falls back to the sample when nothing is selected or the
  // real load fails, so the comparison always has data to render.
  const previewResource = createAsync<Preview>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      return { day: SAMPLE_DAY, sample: true };
    }
    try {
      return {
        day: await client.getDay(schoolId, selection.kind, name, today.today || undefined),
        sample: false,
      };
    } catch {
      return { day: SAMPLE_DAY, sample: true };
    }
  });

  const loadKey = $derived(
    `${selection.schoolId ?? ''}|${selection.kind}|${selection.name ?? ''}|${today.today}`,
  );
  $effect(() => {
    void loadKey;
    void previewResource.load();
  });

  const preview = $derived(previewResource.data ?? { day: SAMPLE_DAY, sample: true });
  const day = $derived(preview.day);
  const usingSample = $derived(preview.sample);
  const visibleLessons = $derived(
    day.lessons.filter((lesson) => !isHiddenFreeLesson(lesson, strikeoutFreeLsn)),
  );
  const firstLesson = $derived(visibleLessons[0] ?? null);
  const restLessons = $derived(visibleLessons.slice(1));

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

  /** The lesson's first item (or a placeholder) for the hero layout. */
  function firstItem(lesson: Lesson): LessonItem {
    return lesson.items[0] ?? EMPTY_ITEM;
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
</script>

<section class="variants">
  <button type="button" class="back nika-btn nika-btn-light" aria-label="Назад" onclick={() => onBack?.()}>
    ← назад
  </button>

  <h2>Варианты расписания</h2>
  <p class="intro">
    Один и тот же день в пяти оформлениях — выберите самый удобный. Это только просмотр, экран
    расписания пока не изменён.
  </p>

  {#if usingSample}
    <StateNotice
      tone="muted"
      title="Показан примерный день"
      detail="Школа и класс не выбраны — данные для сравнения вымышленные."
    />
  {/if}

  <!-- 1. Compact — the current Schedule look, for reference. -->
  <section class="variant" data-variant="compact">
    <h3>1. Компактный (текущий)</h3>
    <p class="caption">Как выглядит экран расписания сейчас — эталон для сравнения.</p>
    <DayView {day} kind={day.kind} {strikeoutFreeLsn} />
  </section>

  <!-- 2. Cards — time column + strong subject, muted teacher, room chip. -->
  <section class="variant" data-variant="cards">
    <h3>2. Карточки</h3>
    <p class="caption">Каждый урок — отдельная карточка: слева время, справа предмет.</p>
    <ul class="cards">
      {#each visibleLessons as lesson (lesson.num)}
        <li
          class="card"
          class:cancelled={isCancelled(lesson)}
          class:exchange={isExchange(lesson) && !isCancelled(lesson)}
        >
          <div class="card-time">
            <span class="num">{lesson.num}</span>
            <span class="clock">{lessonTime(lesson)}</span>
          </div>
          <div class="card-body">
            {#each effectiveItems(lesson) as item, i (i)}
              <div class="card-item">
                <span class="subject" class:method={item.is_method_hour}>{itemSubjectLabel(item)}</span>
                {#if item.groups}
                  <span class="group">{item.groups}</span>
                {/if}
                {#if item.teacher}
                  <span class="teacher">{item.teacher}</span>
                {/if}
                {#if item.room}
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
  </section>

  <!-- 3. Table — dense, aligned columns. -->
  <section class="variant" data-variant="table">
    <h3>3. Таблица</h3>
    <p class="caption">Плотные выровненные столбцы — удобно быстро просматривать.</p>
    <table class="grid">
      <thead>
        <tr>
          <th scope="col">№</th>
          <th scope="col">Время</th>
          <th scope="col">Предмет</th>
          <th scope="col">Учитель</th>
          <th scope="col">Кабинет</th>
        </tr>
      </thead>
      <tbody>
        {#each visibleLessons as lesson (lesson.num)}
          {#each effectiveItems(lesson) as item, i (i)}
            <tr
              class:cancelled={isCancelled(lesson)}
              class:exchange={isExchange(lesson) && !isCancelled(lesson)}
            >
              {#if i === 0}
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
              <td class="teacher">{item.teacher ?? '—'}</td>
              <td>
                {#if item.room}
                  <span class="chip">{item.room}</span>
                {:else}
                  —
                {/if}
              </td>
            </tr>
          {/each}
        {/each}
      </tbody>
    </table>
  </section>

  <!-- 4. Timeline — a vertical time gutter with visible gaps. -->
  <section class="variant" data-variant="timeline">
    <h3>4. Таймлайн</h3>
    <p class="caption">Вертикальная шкала времени: пустые промежутки видны как разрывы.</p>
    <ol class="timeline">
      {#each visibleLessons as lesson, index (lesson.num)}
        {#if index > 0}
          {@const gap = gapMinutes(visibleLessons[index - 1], lesson)}
          {#if gap > 0}
            <li class="tl-gap" aria-hidden="true">
              <span class="tl-gap-line"></span>
              <span class="tl-gap-label">{gap} мин перерыв</span>
            </li>
          {/if}
        {/if}
        <li
          class="tl-item"
          class:cancelled={isCancelled(lesson)}
          class:exchange={isExchange(lesson) && !isCancelled(lesson)}
        >
          <div class="tl-time">
            <span class="num">{lesson.num}</span>
            <span class="clock">{lessonTime(lesson)}</span>
          </div>
          <span class="tl-marker" aria-hidden="true"></span>
          <div class="tl-card">
            {#each effectiveItems(lesson) as item, i (i)}
              <div class="tl-row">
                <span class="subject" class:method={item.is_method_hour}>{itemSubjectLabel(item)}</span>
                {#if item.groups}
                  <span class="group">{item.groups}</span>
                {/if}
                {#if item.teacher}
                  <span class="teacher">{item.teacher}</span>
                {/if}
                {#if item.room}
                  <span class="chip">{item.room}</span>
                {/if}
              </div>
            {/each}
            {#if lessonStatusLabel(lesson)}
              <span class="badge">{lessonStatusLabel(lesson)}</span>
            {/if}
          </div>
        </li>
      {/each}
    </ol>
  </section>

  <!-- 5. Now / next — a hero card for the current/next lesson + the rest. -->
  <section class="variant" data-variant="now-next">
    <h3>5. Сейчас / далее</h3>
    <p class="caption">Крупная карточка ближайшего урока, остальные — компактным списком.</p>
    {#if firstLesson}
      <article
        class="hero"
        class:cancelled={isCancelled(firstLesson)}
        class:exchange={isExchange(firstLesson) && !isCancelled(firstLesson)}
      >
        <span class="hero-eyebrow">Далее</span>
        <div class="hero-top">
          <span class="clock hero-clock">{lessonTime(firstLesson)}</span>
          <span class="num">Урок {firstLesson.num}</span>
          {#if lessonStatusLabel(firstLesson)}
            <span class="badge">{lessonStatusLabel(firstLesson)}</span>
          {/if}
        </div>
        <span class="subject hero-subject" class:method={firstItem(firstLesson).is_method_hour}>
          {itemSubjectLabel(firstItem(firstLesson))}
        </span>
        <div class="hero-meta">
          {#if firstItem(firstLesson).groups}
            <span class="group">{firstItem(firstLesson).groups}</span>
          {/if}
          {#if firstItem(firstLesson).teacher}
            <span class="teacher">{firstItem(firstLesson).teacher}</span>
          {/if}
          {#if firstItem(firstLesson).room}
            <span class="chip">{firstItem(firstLesson).room}</span>
          {/if}
        </div>
      </article>

      {#if restLessons.length > 0}
        <ol class="rest">
          {#each restLessons as lesson (lesson.num)}
            <li
              class="rest-item"
              class:cancelled={isCancelled(lesson)}
              class:exchange={isExchange(lesson) && !isCancelled(lesson)}
            >
              <span class="num">{lesson.num}</span>
              <span class="clock">{lessonTime(lesson)}</span>
              <span class="subject" class:method={firstItem(lesson).is_method_hour}>
                {itemSubjectLabel(firstItem(lesson))}
              </span>
              {#if firstItem(lesson).room}
                <span class="chip">{firstItem(lesson).room}</span>
              {/if}
            </li>
          {/each}
        </ol>
      {/if}
    {:else}
      <StateNotice title="Занятий нет" detail="Расписание на этот день пустое." />
    {/if}
  </section>
</section>

<style>
  .variants {
    text-align: left;
  }

  .back {
    margin: 0 0 var(--space-3);
    font-size: var(--text-sm);
  }

  h2 {
    font-size: var(--text-xl);
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    margin: 0 0 var(--space-2);
  }

  .intro {
    margin: 0 0 var(--space-4);
    font-size: var(--text-sm);
    color: var(--color-muted);
  }

  .variant {
    margin: 0 0 var(--space-6);
    padding-top: var(--space-2);
  }

  .variant > h3 {
    margin: 0 0 var(--space-1);
    font-size: var(--text-lg);
    font-weight: bold;
    color: var(--color-accent);
    border-bottom: 2px solid var(--color-accent);
    padding-bottom: var(--space-1);
  }

  .caption {
    margin: 0 0 var(--space-3);
    font-size: var(--text-xs);
    color: var(--color-muted);
  }

  /* ---- Shared lesson primitives (subject/teacher/room/group/status) -------- */
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

  /* Status is shared across every variant: red = cancelled, amber = exchange. */
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

  /* ---- 2. Cards ------------------------------------------------------------ */
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

  .card.cancelled {
    border-left-color: var(--color-cancel);
  }

  .card.exchange {
    border-left-color: var(--color-exchange);
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

  /* ---- 3. Table ------------------------------------------------------------ */
  .grid {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--text-sm);
  }

  .grid th,
  .grid td {
    text-align: left;
    padding: var(--space-2);
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

  .grid .num {
    width: 2.5rem;
    font-weight: bold;
    color: var(--lesson-num);
  }

  .grid .clock {
    width: 6.5rem;
    white-space: nowrap;
    color: var(--lesson-time);
  }

  .grid .subject {
    font-size: var(--text-sm);
  }

  /* ---- 4. Timeline --------------------------------------------------------- */
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

  .tl-row {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-2);
  }

  .tl-card .subject {
    flex-basis: 100%;
    font-size: var(--text-base);
  }

  .tl-card .badge {
    margin-top: var(--space-1);
  }

  .tl-gap {
    display: grid;
    grid-template-columns: 6rem 1rem 1fr;
    gap: var(--space-2);
    align-items: center;
    min-height: var(--space-5);
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

  .tl-gap-label {
    grid-column: 3;
    font-size: var(--text-xs);
    color: var(--color-muted);
    font-style: italic;
  }

  /* ---- 5. Now / next ------------------------------------------------------- */
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
</style>
