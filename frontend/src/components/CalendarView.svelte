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
  .calendar {
    text-align: left;
    padding: var(--space-4);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
  }

  .nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    margin-bottom: var(--space-4);
  }

  .nav h3 {
    font-size: var(--text-lg);
    font-weight: 600;
    letter-spacing: -0.011em;
    margin: 0;
  }

  .nav button {
    min-height: 40px;
    min-width: 40px;
    padding: var(--space-1) var(--space-3);
    border-radius: var(--radius-sm);
    border: none;
    background: var(--color-surface-2);
    color: var(--color-muted);
    cursor: pointer;
    font-size: var(--text-lg);
    line-height: 1;
    transition:
      background-color 0.15s,
      border-color 0.15s,
      color 0.15s,
      transform 0.1s;
  }

  .nav button:hover {
    background: var(--color-accent-soft);
    color: var(--color-accent);
  }

  .nav button:active {
    transform: scale(0.96);
  }

  .weekdays,
  .grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: var(--space-1);
  }

  .weekdays {
    margin-bottom: var(--space-1);
  }

  .weekdays span {
    text-align: center;
    font-size: var(--text-xs);
    font-weight: 600;
    letter-spacing: 0.04em;
    color: var(--color-muted);
  }

  .cell {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    padding: var(--space-1);
    border: none;
    border-radius: var(--radius-sm);
    background: transparent;
    color: var(--color-text);
    cursor: pointer;
    font-size: var(--text-sm);
    transition:
      background-color 0.15s,
      color 0.15s,
      box-shadow 0.15s,
      transform 0.1s;
  }

  .cell:hover:not(.pad) {
    background: var(--color-accent-soft);
  }

  .cell:active:not(.pad) {
    transform: scale(0.96);
  }

  .cell.pad {
    background: transparent;
    cursor: default;
  }

  .cell.weekend,
  .cell.no-period {
    opacity: 0.4;
  }

  .cell.vacation {
    background: var(--color-vacation-soft);
  }

  .cell.exchange {
    box-shadow: inset 0 -2px 0 var(--color-exchange);
  }

  .cell.cancelled {
    box-shadow: inset 0 -2px 0 var(--color-cancel);
  }

  .cell.today {
    background: var(--color-accent-soft);
    color: var(--color-accent);
    font-weight: 600;
    box-shadow: inset 0 0 0 2px var(--color-accent);
  }

  .marker {
    font-size: 10px;
    font-weight: 700;
    line-height: 1;
  }

  .marker-exchange {
    color: var(--color-exchange);
  }

  .marker-cancelled {
    color: var(--color-cancel);
  }

  .marker-vacation {
    color: var(--color-vacation);
  }

  .count {
    font-size: 10px;
    color: var(--color-muted);
  }
</style>
