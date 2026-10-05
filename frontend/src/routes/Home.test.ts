import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Home from './Home.svelte';
import { makeClient, makeDay, makeSelection, makeToday, SAMPLE_SCHOOLS } from '../test-helpers';
import type { DaySchedule } from '../lib/api/types';

function dayFor(date: string, overrides: Partial<DaySchedule> = {}): DaySchedule {
  return makeDay({ date, ...overrides });
}

describe('Home screen', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('lists schools from /api/schools', async () => {
    const client = makeClient();
    const { findByText } = render(Home, {
      props: { client, selection: makeSelection(), today: makeToday() },
    });
    expect(await findByText('Гимназия №1')).toBeTruthy();
    expect(client.getSchools).toHaveBeenCalledTimes(1);
  });

  it('adopts the server today from the schools round-trip', async () => {
    const client = makeClient({
      getSchools: vi.fn().mockResolvedValue({ today: '07.11.2026', schools: SAMPLE_SCHOOLS }),
    });
    const today = makeToday('01.01.2020');
    render(Home, { props: { client, selection: makeSelection(), today } });

    await waitFor(() => expect(today.today).toBe('07.11.2026'));
  });

  it('selecting a school persists it and clears any saved class', async () => {
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');

    const { getByRole } = render(Home, {
      props: { client, selection, today: makeToday() },
    });

    const select = (await waitFor(() =>
      getByRole('combobox', { name: /Школа/ }),
    )) as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: 'school2' } });

    expect(selection.schoolId).toBe('school2');
    expect(selection.name).toBeNull();
  });

  it('shows the saved class "today" schedule using the server date', async () => {
    // Browser clock is a different date/year.
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2030-06-15T12:00:00Z'));

    const client = makeClient({
      getDay: vi.fn().mockResolvedValue(
        dayFor('05.10.2026', {
          lessons: [
            {
              num: 1,
              start: '08:00',
              end: '08:45',
              items: [{ subject: 'Физика', teacher: 'Петров', room: '202', class_name: '5А' }],
              has_exchange: false,
              is_cancelled: false,
            },
          ],
        }),
      ),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');

    const { findByText } = render(Home, {
      props: { client, selection, today: makeToday('05.10.2026') },
    });

    expect(await findByText('Физика')).toBeTruthy();
    expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '05.10.2026');
    const requestedDate = (client.getDay as ReturnType<typeof vi.fn>).mock.calls[0][3] as string;
    expect(requestedDate).not.toContain('2030');
  });

  it('surfaces a load error', async () => {
    const client = makeClient({
      getSchools: vi.fn().mockRejectedValue(new Error('Сеть недоступна')),
    });
    const { findByText } = render(Home, {
      props: { client, selection: makeSelection(), today: makeToday() },
    });
    expect(await findByText('Ошибка загрузки школ')).toBeTruthy();
    expect(await findByText('Сеть недоступна')).toBeTruthy();
  });
});
