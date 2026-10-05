<script lang="ts">
  // W38: month grid for a class/teacher/room.
  //
  // Pure presentation: the parent owns the month cursor and the data; this
  // component renders the grid and raises `onSelectDay`/`onPrevMonth`/
  // `onNextMonth`. Dates come from the server payload (`DD.MM.YYYY`); the grid
  // is padded with blank cells by a clock-free UTC calculation.
  import type { CalendarResponse } from '../lib/api/types';
  import { calendarDayAriaLabel, dayNumber, monthGrid, monthLabel } from '../lib/calendar';

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

  <div class="grid">
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
  }

  .nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .nav h3 {
    font-size: 1rem;
    margin: 0;
  }

  .nav button {
    padding: 0.2rem 0.6rem;
    border-radius: 0.4rem;
    border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
    background: transparent;
    color: inherit;
    cursor: pointer;
    font-size: 1.1rem;
    line-height: 1;
  }

  .weekdays,
  .grid {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 0.15rem;
  }

  .weekdays span {
    text-align: center;
    font-size: 0.75rem;
    opacity: 0.6;
  }

  .cell {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    padding: 0.1rem;
    border: 1px solid color-mix(in srgb, currentColor 20%, transparent);
    border-radius: 0.3rem;
    background: transparent;
    color: inherit;
    cursor: pointer;
    font-size: 0.85rem;
  }

  .cell.pad {
    border-color: transparent;
    cursor: default;
  }

  .cell.weekend,
  .cell.no-period {
    opacity: 0.45;
  }

  .cell.vacation {
    background: color-mix(in srgb, currentColor 8%, transparent);
  }

  .cell.exchange {
    border-color: #d18b00;
  }

  .cell.cancelled {
    border-color: #b00020;
  }

  .cell.today {
    outline: 2px solid currentColor;
    outline-offset: -2px;
  }

  .marker {
    font-size: 0.6rem;
    line-height: 1;
  }

  .marker-exchange {
    color: #d18b00;
  }

  .marker-cancelled {
    color: #b00020;
  }

  .count {
    font-size: 0.6rem;
    opacity: 0.6;
  }
</style>
