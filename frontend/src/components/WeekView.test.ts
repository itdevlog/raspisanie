import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import WeekView from './WeekView.svelte';
import type { DaySchedule } from '../lib/api/types';
import { makeDay } from '../test-helpers';

function day(date: string, overrides: Partial<DaySchedule> = {}): DaySchedule {
  return makeDay({ date, ...overrides });
}

describe('WeekView', () => {
  it('renders each day of the week', () => {
    const week = {
      days: [
        day('05.10.2026'),
        day('06.10.2026', { weekend: true }),
        day('07.10.2026', { no_period: true }),
      ],
      weekday_num: 5,
    };
    const { getByText } = render(WeekView, { props: { week, kind: 'class' } });
    expect(getByText('Понедельник, 05.10.2026')).toBeTruthy();
    expect(getByText('Выходной')).toBeTruthy();
    expect(getByText('Нет учебного периода')).toBeTruthy();
  });

  it('forwards strikeoutFreeLsn=false so free/cancelled rows are hidden (W41 fix)', () => {
    const week = {
      days: [
        day('05.10.2026', {
          lessons: [
            {
              num: 1,
              start: '08:00',
              end: '08:45',
              items: [],
              has_exchange: false,
              is_cancelled: true,
            },
          ],
        }),
      ],
      weekday_num: 5,
    };
    const { container } = render(WeekView, {
      props: { week, kind: 'class', strikeoutFreeLsn: false },
    });
    expect(container.querySelector('.lesson')).toBeNull();
  });
});
