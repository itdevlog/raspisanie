import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, screen, waitFor } from '@testing-library/svelte';
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
    ...overrides,
  };
}

/** Base props for the screen: a stub client with a school selected. */
function baseProps() {
  const selection = makeSelection();
  selection.selectSchool('gym1');
  return {
    client: makeClient(),
    selection,
    today: makeToday('05.10.2026'),
    favorites: makeFavorites(),
    onOpenList: vi.fn(),
    onOpenEntity: vi.fn(),
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
    const { findByTitle } = render(Home, {
      props: { client, selection: makeSelection(), today: makeToday() },
    });
    expect(await findByTitle('Гимназия №1')).toBeTruthy();
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

    // «Школа №2» → the quick button labelled `2`.
    await fireEvent.click(await waitFor(() => getByRole('button', { name: '2' })));

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

    // The landing offers the section buttons (and never fetches a list itself).
    expect(await findByRole('button', { name: 'Классы' })).toBeTruthy();
    expect(client.getClasses).not.toHaveBeenCalled();
  });

  describe('school metadata', () => {
    function metaClient(school: School) {
      return makeClient({
        getSchools: vi.fn().mockResolvedValue({ today: '05.10.2026', schools: [school] }),
      });
    }

    it('shows the school city; name and «Обновлено» live in the header', async () => {
      const selection = makeSelection();
      selection.selectSchool('gym1');

      const { findByText, queryByText } = render(Home, {
        props: { client: metaClient(schoolWithMeta()), selection, today: makeToday() },
      });

      // The school name and «Обновлено» live in the app header, not here.
      expect(await findByText('Москва')).toBeTruthy();
      expect(queryByText('Обновлено 01.09.2026 10:00')).toBeNull();
    });
  });

  describe('section buttons', () => {
    it('opens the class, teacher and room lists', async () => {
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

      await fireEvent.click(await findByRole('button', { name: 'Кабинеты' }));
      expect(onOpenList).toHaveBeenCalledWith('room');
    });
  });

  describe('sections and favorite summary cards', () => {
    it('offers Классы, Учителя and Кабинеты sections', async () => {
      render(Home, { props: baseProps() });
      expect(await screen.findByRole('button', { name: 'Классы' })).toBeTruthy();
      expect(screen.getByRole('button', { name: 'Учителя' })).toBeTruthy();
      expect(screen.getByRole('button', { name: 'Кабинеты' })).toBeTruthy();
    });

    it('no longer renders the school-site link (moved to the header)', async () => {
      render(Home, { props: baseProps() });
      await screen.findByRole('button', { name: 'Классы' });
      expect(screen.queryByRole('link', { name: 'Школьный сайт' })).toBeNull();
    });

    it('renders a now summary card for each favorite', async () => {
      // два избранных (class + room), getNow мокается → две сводки
      const client = makeClient({
        getNow: vi.fn().mockResolvedValue(NOW_CURRENT),
      });
      const favorites = makeFavorites();
      favorites.add('gym1', 'class', '7В');
      favorites.add('gym1', 'room', '303');

      render(Home, { props: { ...baseProps(), client, favorites } });

      expect(await screen.findAllByRole('heading', { name: 'Сейчас' })).toHaveLength(2);
      expect(client.getNow).toHaveBeenCalledWith('gym1', 'class', '7В', '05.10.2026');
      expect(client.getNow).toHaveBeenCalledWith('gym1', 'room', '303', '05.10.2026');
    });
  });

  describe('school-number quick buttons', () => {
    function numberedClient(schools: School[]) {
      return makeClient({
        getSchools: vi.fn().mockResolvedValue({ today: '05.10.2026', schools }),
      });
    }

    it('renders one numbered button per school and selects the tapped one', async () => {
      const client = numberedClient([
        { id: 'school_16', name: 'МАОУ СОШ №16', loaded: true },
        { id: 'school_19', name: 'МАОУ СОШ №19', loaded: true },
        { id: 'school_181', name: 'МАОУ СОШ №181', loaded: true },
      ]);
      const selection = makeSelection();

      const { findAllByRole, getByRole, queryByRole } = render(Home, {
        props: { client, selection, today: makeToday() },
      });

      const buttons = await findAllByRole('button', { name: /^\d+$/ });
      expect(buttons.map((button) => button.textContent?.trim())).toEqual(['16', '19', '181']);
      // The quick buttons are the only school switcher now (no dropdown).
      expect(queryByRole('combobox')).toBeNull();

      await fireEvent.click(getByRole('button', { name: '19' }));

      expect(selection.schoolId).toBe('school_19');
      const active = getByRole('button', { name: '19' });
      expect(active.getAttribute('aria-pressed')).toBe('true');
      expect(active.classList.contains('is-active')).toBe(true);
      expect(getByRole('button', { name: '16' }).getAttribute('aria-pressed')).toBe('false');
    });

    it('falls back to the id suffix when the name has no number', async () => {
      const client = numberedClient([{ id: 'school_42', name: 'Лицей', loaded: true }]);

      const { findByRole } = render(Home, {
        props: { client, selection: makeSelection(), today: makeToday() },
      });

      expect(await findByRole('button', { name: '42' })).toBeTruthy();
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

});
