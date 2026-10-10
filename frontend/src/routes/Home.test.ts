import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Home from './Home.svelte';
import {
  makeClient,
  makeFavorites,
  makeSelection,
  makeToday,
  SAMPLE_SCHOOLS,
} from '../test-helpers';
import type { NowResponse, School } from '../lib/api/types';

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

describe('Home screen (landing)', () => {
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

  it('does not fetch a per-kind list on the landing', async () => {
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');

    const { findByRole } = render(Home, {
      props: { client, selection, today: makeToday() },
    });

    expect(await findByRole('heading', { name: 'Гимназия №1' })).toBeTruthy();
    expect(client.getClasses).not.toHaveBeenCalled();
  });

  describe('school metadata', () => {
    function metaClient(school: School) {
      return makeClient({
        getSchools: vi.fn().mockResolvedValue({ today: '05.10.2026', schools: [school] }),
      });
    }

    it('shows the school name, city, «Обновлено» and the yellow school-site button', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');

      const { findByText, findByRole } = render(Home, {
        props: { client: metaClient(schoolWithMeta()), selection, today: makeToday() },
      });

      expect(await findByRole('heading', { name: 'Гимназия №1' })).toBeTruthy();
      expect(await findByText('Москва')).toBeTruthy();
      expect(await findByText('Обновлено 01.09.2026 10:00')).toBeTruthy();
      const link = await findByRole('link', { name: 'Школьный сайт' });
      expect(link.getAttribute('href')).toBe('https://gym1.example.ru');
    });

    it('hides the site button when features.homepage is false', async () => {
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
      expect(queryByRole('link', { name: 'Школьный сайт' })).toBeNull();
    });

    it('hides the site button when there is no homepage_url', async () => {
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
      expect(queryByRole('link', { name: 'Школьный сайт' })).toBeNull();
    });
  });

  describe('section buttons', () => {
    it('opens the class and teacher lists', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');
      const onOpenList = vi.fn();

      const { findByRole } = render(Home, {
        props: { client: makeClient(), selection, today: makeToday(), onOpenList },
      });

      await fireEvent.click(await findByRole('button', { name: 'Классы' }));
      expect(onOpenList).toHaveBeenCalledWith('class');

      await fireEvent.click(await findByRole('button', { name: 'Учителя' }));
      expect(onOpenList).toHaveBeenCalledWith('teacher');
    });
  });

  describe('favorites-first (all kinds)', () => {
    it('shows favorites of every kind and opens/removes them', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');
      const favorites = makeFavorites();
      favorites.add('gym1', 'class', '7В');
      favorites.add('gym1', 'teacher', 'Сидоров С.С.');
      favorites.add('gym1', 'room', '303');
      const onOpenEntity = vi.fn();

      const { findByRole, findByText } = render(Home, {
        props: { client: makeClient(), selection, today: makeToday(), favorites, onOpenEntity },
      });

      expect(await findByText('Избранное')).toBeTruthy();
      expect(await findByText('7В')).toBeTruthy();
      expect(await findByText('Сидоров С.С.')).toBeTruthy();
      expect(await findByText('303')).toBeTruthy();

      await fireEvent.click(await findByRole('button', { name: 'Открыть расписание: 7В' }));
      expect(onOpenEntity).toHaveBeenCalledWith('class', '7В');

      await fireEvent.click(await findByRole('button', { name: 'Удалить из избранного: 7В' }));
      expect(favorites.has('gym1', 'class', '7В')).toBe(false);
    });

    it('hides the Избранное section when there are no favorites', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');

      const { findByText, queryByText } = render(Home, {
        props: { client: makeClient(), selection, today: makeToday(), favorites: makeFavorites() },
      });

      expect(await findByText('Классы')).toBeTruthy();
      expect(queryByText('Избранное')).toBeNull();
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
});
