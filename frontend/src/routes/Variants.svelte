<script lang="ts">
  // /variants — a read-only comparison screen: the SAME day rendered in five
  // alternative layouts so the best one can be picked before touching the real
  // Schedule screen.
  //
  // Data: the currently selected entity's day (selection + client.getDay) when
  // available; otherwise the built-in {@link SAMPLE_DAY} (school_133-shaped:
  // 6–7 lessons, a split group, a substitution, a cancellation, a method hour).
  // The page always renders, even with no school selected.
  //
  // Each layout is rendered through the SAME components the real Schedule screen
  // uses ({@link DayView} for «Компактный», {@link ScheduleBody} for the rest),
  // so the preview can never drift from the live screen. `chrome={false}` hides
  // the day heading/notices that the section captions already convey.
  import {
    api as defaultApi,
    selection as defaultSelection,
    serverToday as defaultToday,
    createAsync,
    SAMPLE_DAY,
    type DaySchedule,
    type ScheduleApiClient,
    type SelectionStore,
    type TodayStore,
  } from '../lib';
  import DayView from '../components/DayView.svelte';
  import ScheduleBody from '../components/schedule/ScheduleBody.svelte';
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
    /** True when a real day loaded but had no lessons, so the sample stands in. */
    emptyReal?: boolean;
  }

  // The day to preview. Falls back to the sample when nothing is selected, the
  // real load fails, or the real day has no lessons (weekend/vacation), so the
  // comparison always has data to render.
  const previewResource = createAsync<Preview>(async () => {
    const schoolId = selection.schoolId;
    const name = selection.name;
    if (!schoolId || !name) {
      return { day: SAMPLE_DAY, sample: true };
    }
    try {
      const realDay = await client.getDay(schoolId, selection.kind, name, today.today || undefined);
      if (realDay.lessons.length === 0) {
        return { day: SAMPLE_DAY, sample: true, emptyReal: true };
      }
      return { day: realDay, sample: false };
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
</script>

<section class="variants">
  <button
    type="button"
    class="back nika-btn nika-btn-light"
    aria-label="Назад"
    onclick={() => onBack?.()}
  >
    ← назад
  </button>

  <h2>Варианты расписания</h2>
  <p class="intro">
    Один и тот же день в пяти оформлениях — выберите самый удобный. Вид можно выбрать в настройках
    («Вид расписания»), экран расписания использует его сразу.
  </p>

  {#if usingSample}
    <StateNotice
      tone="muted"
      title="Показан примерный день"
      detail={preview.emptyReal
        ? 'В расписании на этот день нет уроков — показан пример для сравнения.'
        : 'Школа и класс не выбраны — данные для сравнения вымышленные.'}
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
    <ScheduleBody {day} kind={day.kind} view="cards" {strikeoutFreeLsn} chrome={false} />
  </section>

  <!-- 3. Table — dense, aligned columns. -->
  <section class="variant" data-variant="table">
    <h3>3. Таблица</h3>
    <p class="caption">Плотные выровненные столбцы — удобно быстро просматривать.</p>
    <ScheduleBody {day} kind={day.kind} view="table" {strikeoutFreeLsn} chrome={false} />
  </section>

  <!-- 4. Timeline — a vertical time gutter with visible gaps. -->
  <section class="variant" data-variant="timeline">
    <h3>4. Таймлайн</h3>
    <p class="caption">Вертикальная шкала времени: пустые промежутки видны как разрывы.</p>
    <ScheduleBody {day} kind={day.kind} view="timeline" {strikeoutFreeLsn} chrome={false} />
  </section>

  <!-- 5. Now / next — a hero card for the current/next lesson + the rest. -->
  <section class="variant" data-variant="now-next">
    <h3>5. Сейчас / далее</h3>
    <p class="caption">Крупная карточка ближайшего урока, остальные — компактным списком.</p>
    <ScheduleBody {day} kind={day.kind} view="nownext" {strikeoutFreeLsn} chrome={false} />
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
</style>
