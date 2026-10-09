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

    it('shows the city and the yellow school-site button', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');

      const { findByText, findByRole } = render(Home, {
        props: { client: metaClient(schoolWithMeta()), selection, today: makeToday() },
      });

      expect(await findByText('Москва')).toBeTruthy();
      // «Обновлено» now lives in the App header, not on Home.
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

  describe('favorites-first picker', () => {
    it('expands «Классы» and opens a class schedule', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');
      const onOpenEntity = vi.fn();
      const client = makeClient({
        getClasses: vi.fn().mockResolvedValue({ classes: ['5А', '6Б'] }),
      });

      const { findByRole } = render(Home, {
        props: { client, selection, today: makeToday(), onOpenEntity },
      });

      // The list is collapsed behind the big «Классы» button by default.
      await fireEvent.click(await findByRole('button', { name: 'Классы' }));
      await fireEvent.click(await findByRole('button', { name: '6Б' }));
      expect(onOpenEntity).toHaveBeenCalledWith('class', '6Б');
    });

    it('filters teachers case-insensitively and opens a teacher schedule', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');
      const onOpenEntity = vi.fn();
      const client = makeClient({
        getTeachers: vi.fn().mockResolvedValue({ teachers: ['Иванов И.И.', 'Петров П.П.'] }),
      });

      const { findByRole, queryByRole } = render(Home, {
        props: { client, selection, today: makeToday(), onOpenEntity },
      });

      await fireEvent.click(await findByRole('button', { name: 'Учителя' }));
      const input = await findByRole('searchbox', { name: 'Поиск учителя' });
      expect(await findByRole('button', { name: 'Петров П.П.' })).toBeTruthy();

      await fireEvent.input(input, { target: { value: 'петров' } });
      await waitFor(() => expect(queryByRole('button', { name: 'Иванов И.И.' })).toBeNull());

      await fireEvent.click(await findByRole('button', { name: 'Петров П.П.' }));
      expect(onOpenEntity).toHaveBeenCalledWith('teacher', 'Петров П.П.');
    });

    it('shows deliberate error and empty states for the collapsible lists', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');
      const client = makeClient({
        getClasses: vi.fn().mockRejectedValue(new Error('нет классов')),
        getTeachers: vi.fn().mockResolvedValue({ teachers: [] }),
      });

      const { findByText, findByRole } = render(Home, {
        props: { client, selection, today: makeToday() },
      });

      await fireEvent.click(await findByRole('button', { name: 'Классы' }));
      expect(await findByText('Ошибка загрузки классов')).toBeTruthy();
      expect(await findByText('нет классов')).toBeTruthy();

      await fireEvent.click(await findByRole('button', { name: 'Учителя' }));
      expect(await findByText('Учителя не найдены')).toBeTruthy();
    });

    it('groups favorites by kind and opens the chosen entity', async () => {
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
      expect(await findByRole('heading', { level: 4, name: 'Классы' })).toBeTruthy();
      expect(await findByRole('heading', { level: 4, name: 'Учителя' })).toBeTruthy();
      expect(await findByRole('heading', { level: 4, name: 'Кабинеты' })).toBeTruthy();
      expect(await findByText('7В')).toBeTruthy();

      await fireEvent.click(await findByRole('button', { name: '303' }));
      expect(onOpenEntity).toHaveBeenCalledWith('room', '303');
    });

    it('removes a favorite from the Избранное section', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');
      const favorites = makeFavorites();
      favorites.add('gym1', 'class', '7В');

      const { findByRole } = render(Home, {
        props: { client: makeClient(), selection, today: makeToday(), favorites },
      });

      await fireEvent.click(
        await findByRole('button', { name: 'Удалить из избранного: 7В' }),
      );

      expect(favorites.has('gym1', 'class', '7В')).toBe(false);
      expect(favorites.list('gym1')).toHaveLength(0);
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

    it('does not fetch the full day schedule on Home (that lives on Schedule)', async () => {
      const client = makeClient();
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');

      const { findByText } = render(Home, {
        props: { client, selection, today: makeToday('05.10.2026') },
      });

      expect(await findByText('Классы')).toBeTruthy();
      await waitFor(() => expect(client.getClasses).toHaveBeenCalledWith('gym1'));
      expect(client.getDay).not.toHaveBeenCalled();
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

    await fireEvent.click(await findByRole('button', { name: 'В избранное: 5А' }));
    expect(favorites.has('gym1', 'class', '5А')).toBe(true);

    await fireEvent.click(await findByRole('button', { name: 'Убрать из избранного: 5А' }));
    expect(favorites.has('gym1', 'class', '5А')).toBe(false);
  });
});
