<script lang="ts">
  // W38: month grid for a class/teacher/room.
  //
  // Pure presentation: the parent owns the month cursor and the data; this
  // component renders the grid and raises `onSelectDay`/`onPrevMonth`/
  // `onNextMonth`. Dates come from the server payload (`DD.MM.YYYY`); the grid
  // is padded with blank cells by a clock-free UTC calculation.
  import type { CalendarResponse } from '../lib/api/types';
  import { calendarDayAriaLabel, dayNumber, monthGrid, monthLabel } from '../lib/calendar';
  import { swipe } from '../lib/swipe';

  interface Props {
    month: CalendarResponse;
    year: number;
    /** 1-based month. */
    monthNumber: number;
    /** Server today `DD.MM.YYYY`, highlighted in the grid. */
    today?: string | null;
    onSelectDay: (date: string) => void;
    onPrevMonth: () => void;
    onNextMonth: () => void;
  }
  let {
    month,
    year,
    monthNumber,
    today = null,
    onSelectDay,
    onPrevMonth,
    onNextMonth,
  }: Props = $props();

  const weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  const cells = $derived(monthGrid(month.days, year, monthNumber));
  const label = $derived(monthLabel(year, monthNumber));
</script>

<section class="calendar" aria-label={label}>
  <header class="nav">
    <button type="button" aria-label="Предыдущий месяц" onclick={onPrevMonth}>‹</button>
    <h3>{label}</h3>
    <button type="button" aria-label="Следующий месяц" onclick={onNextMonth}>›</button>
  </header>

  <div class="weekdays" aria-hidden="true">
    {#each weekdays as weekday (weekday)}
      <span>{weekday}</span>
    {/each}
  </div>

  <div class="grid" use:swipe={{ onLeft: onNextMonth, onRight: onPrevMonth }}>
    {#each cells as cell, index (cell ? cell.date : `pad-${index}`)}
      {#if cell}
        <button
          type="button"
          class="cell"
          class:weekend={cell.weekend}
          class:vacation={cell.vacation}
          class:no-period={cell.no_period}
          class:exchange={cell.has_exchange}
          class:cancelled={cell.has_cancelled}
          class:has-lessons={cell.lesson_count > 0}
          class:saturday={index % 7 === 5}
          class:sunday={index % 7 === 6}
          class:today={today === cell.date}
          data-exchange={cell.has_exchange ? 'true' : undefined}
          data-cancelled={cell.has_cancelled ? 'true' : undefined}
          data-vacation={cell.vacation ? 'true' : undefined}
          aria-label={calendarDayAriaLabel(cell)}
          onclick={() => onSelectDay(cell.date)}
        >
          <span class="num">{dayNumber(cell.date)}</span>
          {#if cell.has_exchange}
            <span class="marker marker-exchange" title="Замена">З</span>
          {/if}
          {#if cell.has_cancelled}
            <span class="marker marker-cancelled" title="Отмена">О</span>
          {/if}
          {#if cell.vacation}
            <span class="marker marker-vacation" title="Каникулы">К</span>
          {/if}
          {#if cell.lesson_count > 0}
            <span class="count">{cell.lesson_count}</span>
          {/if}
        </button>
      {:else}
        <span class="cell pad" aria-hidden="true"></span>
      {/if}
    {/each}
  </div>
</section>

<style>
  /* Original month calendar: a tight bordered grid with colour-coded days. */
  .calendar {
    text-align: left;
    padding: var(--space-4);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  .nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }

  .nav h3 {
    font-size: var(--text-base);
    font-weight: bold;
    text-transform: uppercase;
    margin: 0;
    color: var(--color-text);
  }

  .nav button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 40px;
    min-width: 40px;
    padding: 0;
    border: 1px solid var(--nika-btn-blue-border);
    border-radius: 50%;
    background: var(--nika-btn-blue-bg);
    background-image: var(--nika-btn-blue-bg-image);
    color: var(--nika-btn-blue-text);
    text-shadow: var(--nika-btn-blue-text-shadow);
    cursor: pointer;
    font-size: var(--text-lg);
    line-height: 1;
    box-shadow: var(--nika-shadow);
  }

  .nav button:active {
    transform: translateY(1px);
    filter: brightness(0.94);
  }

  .weekdays,
  .grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 0;
  }

  .weekdays {
    margin-bottom: var(--space-1);
  }

  .weekdays span {
    text-align: center;
    font-size: var(--text-xs);
    font-weight: bold;
    color: var(--cal-cell-text);
  }

  .cell {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    padding: var(--space-1);
    border: 1px solid var(--cal-cell-border);
    border-radius: 0;
    background: var(--color-surface);
    color: var(--cal-cell-text);
    cursor: pointer;
    font-size: var(--text-sm);
    font-weight: bold;
  }

  .cell:hover:not(.pad) {
    background: var(--color-accent-soft);
  }

  .cell.pad {
    border-color: transparent;
    background: transparent;
    cursor: default;
  }

  .cell.has-lessons {
    background: var(--cal-day-bg);
  }

  .cell.exchange,
  .cell.cancelled {
    background: var(--cal-changed-bg);
  }

  .cell.vacation {
    background: var(--color-vacation-soft);
  }

  .cell.weekend,
  .cell.no-period {
    opacity: 0.45;
  }

  .cell.today {
    border: 3px solid var(--cal-today-border);
  }

  .cell.saturday {
    color: var(--cal-sat);
  }

  .cell.sunday {
    color: var(--cal-sun);
  }

  .marker {
    font-size: 10px;
    font-weight: bold;
    line-height: 1;
  }

  .marker-exchange {
    color: var(--lesson-exchange);
  }

  .marker-cancelled {
    color: var(--lesson-cancel);
  }

  .marker-vacation {
    color: var(--color-vacation);
  }

  .count {
    font-size: 10px;
    color: var(--color-muted);
  }
</style>
