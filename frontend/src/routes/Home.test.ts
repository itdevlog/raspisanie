import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Home from './Home.svelte';
import {
  makeClient,
  makeDay,
  makeFavorites,
  makeSelection,
  makeToday,
  SAMPLE_SCHOOLS,
} from '../test-helpers';
import type { DaySchedule, NowResponse, School } from '../lib/api/types';

function dayFor(date: string, overrides: Partial<DaySchedule> = {}): DaySchedule {
  return makeDay({ date, ...overrides });
}

const NOW_CURRENT: NowResponse = {
  server_time: '2026-10-05T10:00:00+03:00',
  current: { num: 2, time: '09:00-09:45', subject: 'Физика', room: '202', in_minutes: 20 },
  next: null,
};

function schoolWithMeta(overrides: Partial<School> = {}): School {
  return {
    id: 'gym1',
    name: 'Гимназия №1',
    loaded: true,
    city: 'Москва',
    updated: '01.09.2026 10:00',
    homepage_url: 'https://gym1.example.ru',
    features: { teachers: true, classrooms: true, rooms: true, homepage: true },
    ...overrides,
  };
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
              items: [
                {
                  subject: 'Физика',
                  teacher: 'Петров',
                  room: '202',
                  class_name: '5А',
                  groups: null,
                  is_method_hour: false,
                },
              ],
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

  describe('school metadata', () => {
    function metaClient(school: School) {
      return makeClient({
        getSchools: vi.fn().mockResolvedValue({ today: '05.10.2026', schools: [school] }),
      });
    }

    it('shows city, «Обновлено» and the school-site link', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');

      const { findByText, findByRole } = render(Home, {
        props: { client: metaClient(schoolWithMeta()), selection, today: makeToday() },
      });

      expect(await findByText('Москва')).toBeTruthy();
      expect(await findByText('Обновлено 01.09.2026 10:00')).toBeTruthy();
      const link = await findByRole('link', { name: 'Сайт школы' });
      expect(link.getAttribute('href')).toBe('https://gym1.example.ru');
    });

    it('hides the site link when features.homepage is false', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');

      const { findByText, queryByRole } = render(Home, {
        props: {
          client: metaClient(schoolWithMeta({ features: { homepage: false } })),
          selection,
          today: makeToday(),
        },
      });

      expect(await findByText('Москва')).toBeTruthy();
      expect(queryByRole('link', { name: 'Сайт школы' })).toBeNull();
    });

    it('hides the site link when there is no homepage_url', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');

      const { findByText, queryByRole } = render(Home, {
        props: {
          client: metaClient(schoolWithMeta({ homepage_url: null })),
          selection,
          today: makeToday(),
        },
      });

      expect(await findByText('Москва')).toBeTruthy();
      expect(queryByRole('link', { name: 'Сайт школы' })).toBeNull();
    });
  });

  describe('current-lesson widget', () => {
    it('renders the running lesson from /now for the saved class', async () => {
      const client = makeClient({ getNow: vi.fn().mockResolvedValue(NOW_CURRENT) });
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');

      const { findByText } = render(Home, {
        props: { client, selection, today: makeToday('05.10.2026') },
      });

      expect(await findByText('Идёт урок')).toBeTruthy();
      expect(await findByText(/Физика/)).toBeTruthy();
      await waitFor(() =>
        expect(client.getNow).toHaveBeenCalledWith('gym1', 'class', '5А', '05.10.2026'),
      );
    });

    it('renders the next lesson when none is running', async () => {
      const client = makeClient({
        getNow: vi.fn().mockResolvedValue({
          server_time: '2026-10-05T08:00:00+03:00',
          current: null,
          next: { num: 1, time: '08:00-08:45', subject: 'Химия', room: '303', in_minutes: 5 },
        } satisfies NowResponse),
      });
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');

      const { findByText } = render(Home, {
        props: { client, selection, today: makeToday('05.10.2026') },
      });

      expect(await findByText('До начала')).toBeTruthy();
      expect(await findByText(/Химия/)).toBeTruthy();
    });

    it('handles a day with no lessons left', async () => {
      const client = makeClient({
        getNow: vi.fn().mockResolvedValue({
          server_time: '2026-10-05T20:00:00+03:00',
          current: null,
          next: null,
        } satisfies NowResponse),
      });
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');

      const { findByText } = render(Home, {
        props: { client, selection, today: makeToday('05.10.2026') },
      });

      expect(await findByText('Уроков нет')).toBeTruthy();
    });
  });

  it('navigates to the free-rooms screen', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const onOpenFreeRooms = vi.fn();

    const { findByRole } = render(Home, {
      props: { client: makeClient(), selection, today: makeToday(), onOpenFreeRooms },
    });

    await fireEvent.click(await findByRole('button', { name: 'Свободные кабинеты' }));
    expect(onOpenFreeRooms).toHaveBeenCalledTimes(1);
  });

  it('toggles the saved class as a favorite', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const favorites = makeFavorites();

    const { findByRole } = render(Home, {
      props: { client: makeClient(), selection, today: makeToday(), favorites },
    });

    const button = await findByRole('button', { name: /5А/ });
    await fireEvent.click(button);
    expect(favorites.has('gym1', 'class', '5А')).toBe(true);

    await fireEvent.click(button);
    expect(favorites.has('gym1', 'class', '5А')).toBe(false);
  });
});
