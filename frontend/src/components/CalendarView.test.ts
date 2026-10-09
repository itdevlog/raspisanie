import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import CalendarView from './CalendarView.svelte';
import { fireSwipe, makeCalendar, makeCalendarDay } from '../test-helpers';
import { formatRuDate } from '../lib/dates';

/** October 2026 with one marked exchange, cancellation and vacation day. */
function october() {
  return makeCalendar(
    Array.from({ length: 31 }, (_, i) =>
      makeCalendarDay({
        date: formatRuDate(2026, 10, i + 1),
        day_name: i === 4 ? 'Понедельник' : '',
        has_exchange: i === 4, // 05.10.2026
        has_cancelled: i === 6, // 07.10.2026
        vacation: i === 10, // 11.10.2026
        lesson_count: i === 4 ? 6 : 0,
      }),
    ),
  );
}

function props(overrides: Record<string, unknown> = {}) {
  return {
    month: october(),
    year: 2026,
    monthNumber: 10,
    onSelectDay: vi.fn(),
    onPrevMonth: vi.fn(),
    onNextMonth: vi.fn(),
    ...overrides,
  };
}

describe('CalendarView', () => {
  it('renders the month label and Monday-first weekday header', () => {
    const { getByText } = render(CalendarView, { props: props() });
    expect(getByText('Октябрь 2026')).toBeTruthy();
    expect(getByText('Пн')).toBeTruthy();
    expect(getByText('Ср')).toBeTruthy();
    expect(getByText('Вс')).toBeTruthy();
  });

  it('marks exchanges, cancellations and vacations distinctly', () => {
    const { container } = render(CalendarView, { props: props() });
    expect(container.querySelector('[data-exchange="true"]')).toBeTruthy();
    expect(container.querySelector('[data-cancelled="true"]')).toBeTruthy();
    expect(container.querySelector('[data-vacation="true"]')).toBeTruthy();
  });

  it('labels marked days for assistive tech', () => {
    const { getByRole } = render(CalendarView, { props: props() });
    expect(getByRole('button', { name: /замена/i })).toBeTruthy();
    expect(getByRole('button', { name: /отмена/i })).toBeTruthy();
    expect(getByRole('button', { name: /каникулы/i })).toBeTruthy();
  });

  it('emits the clicked date', async () => {
    const onSelectDay = vi.fn();
    const { getByRole } = render(CalendarView, { props: props({ onSelectDay }) });
    await fireEvent.click(getByRole('button', { name: /06\.10\.2026/ }));
    expect(onSelectDay).toHaveBeenCalledWith('06.10.2026');
  });

  it('emits month navigation events', async () => {
    const onPrevMonth = vi.fn();
    const onNextMonth = vi.fn();
    const { getByRole } = render(CalendarView, { props: props({ onPrevMonth, onNextMonth }) });
    await fireEvent.click(getByRole('button', { name: 'Предыдущий месяц' }));
    await fireEvent.click(getByRole('button', { name: 'Следующий месяц' }));
    expect(onPrevMonth).toHaveBeenCalledOnce();
    expect(onNextMonth).toHaveBeenCalledOnce();
  });

  it('swipes the grid to the next and previous month', () => {
    const onPrevMonth = vi.fn();
    const onNextMonth = vi.fn();
    const { container } = render(CalendarView, { props: props({ onPrevMonth, onNextMonth }) });
    const grid = container.querySelector('.grid') as HTMLElement;

    fireSwipe(grid, -60);
    expect(onNextMonth).toHaveBeenCalledOnce();

    fireSwipe(grid, 60);
    expect(onPrevMonth).toHaveBeenCalledOnce();
  });
});
