import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import { flushSync, tick } from 'svelte';
import App from './App.svelte';
import {
  makeCalendar,
  makeCalendarDay,
  makeClient,
  makeFakeEnv,
  makeFavorites,
  makeRouter,
  makeSelection,
  makeSettings,
  makeToday,
} from './test-helpers';
import { createRouteStore } from './lib/stores/route.svelte';

/**
 * Base App props: a selected school carrying homepage metadata, opened on a
 * schedule deep link so the only «Школьный сайт» link on screen can be the
 * header's (the landing still carries its own until Task 7 removes it).
 */
function baseProps() {
  const selection = makeSelection();
  selection.selectSchool('gym1');
  const fake = makeFakeEnv('/s/gym1/class/5%D0%90');
  const router = createRouteStore(fake.env);
  const client = makeClient({
    getSchools: vi.fn().mockResolvedValue({
      today: '05.10.2026',
      schools: [
        {
          id: 'gym1',
          name: 'Гимназия №1',
          loaded: true,
          homepage_url: 'https://gym1.example.ru',
          features: { homepage: true },
        },
      ],
    }),
  });
  return { client, selection, today: makeToday(), router };
}

describe('App shell', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders the landing by default', async () => {
    const { router } = makeRouter();
    const { findByRole } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday(), router },
    });
    // School-number quick buttons are the switcher on the landing.
    expect(await findByRole('button', { name: '1' })).toBeTruthy();
  });

  it('shows the selected school name and «Обновлено» in the header', async () => {
    const { router } = makeRouter();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const client = makeClient({
      getSchools: vi.fn().mockResolvedValue({
        today: '05.10.2026',
        schools: [
          {
            id: 'gym1',
            name: 'Гимназия №1',
            loaded: true,
            updated: '01.09.2026 10:00',
          },
        ],
      }),
    });

    const { findByRole, findByText } = render(App, {
      props: { client, selection, today: makeToday(), router },
    });

    expect(await findByRole('heading', { name: 'Гимназия №1' })).toBeTruthy();
    expect(await findByText('Обновлено 01.09.2026 10:00')).toBeTruthy();
  });

  it('shows a school-site link in the header when the school has a homepage', async () => {
    // school с homepage_url и features.homepage !== false
    const { findByRole } = render(App, { props: baseProps() });
    const link = await findByRole('link', { name: 'Школьный сайт' });
    expect(link.getAttribute('href')).toContain('http');
  });

  it('places the school-site link on the «Обновлено» row, not the title row', async () => {
    const client = makeClient({
      getSchools: vi.fn().mockResolvedValue({
        today: '05.10.2026',
        schools: [
          {
            id: 'gym1',
            name: 'Гимназия №1',
            loaded: true,
            updated: '01.09.2026 10:00',
            homepage_url: 'https://gym1.example.ru',
          },
        ],
      }),
    });

    const { findByRole } = render(App, { props: { ...baseProps(), client } });
    const link = await findByRole('link', { name: 'Школьный сайт' });
    expect(link.closest('.header-row')).toBeNull();
    expect(link.closest('.app-header-sub')).not.toBeNull();
  });

  it('hides the school-site link when there is no homepage', async () => {
    // Школа без homepage_url.
    const client = makeClient({
      getSchools: vi.fn().mockResolvedValue({
        today: '05.10.2026',
        schools: [{ id: 'gym1', name: 'Гимназия №1', loaded: true, homepage_url: null }],
      }),
    });

    const { findByRole, queryByRole } = render(App, { props: { ...baseProps(), client } });

    // The header reflects the loaded school before the absence is checked.
    await findByRole('heading', { name: 'Гимназия №1' });
    expect(queryByRole('link', { name: 'Школьный сайт' })).toBeNull();
  });

  it('hides the school-site link when features.homepage is false', async () => {
    const client = makeClient({
      getSchools: vi.fn().mockResolvedValue({
        today: '05.10.2026',
        schools: [
          {
            id: 'gym1',
            name: 'Гимназия №1',
            loaded: true,
            homepage_url: 'https://gym1.example.ru',
            features: { homepage: false },
          },
        ],
      }),
    });

    const { findByRole, queryByRole } = render(App, { props: { ...baseProps(), client } });

    await findByRole('heading', { name: 'Гимназия №1' });
    expect(queryByRole('link', { name: 'Школьный сайт' })).toBeNull();
  });

  it('opens the settings screen from the header gear', async () => {
    const fake = makeFakeEnv('/');
    const router = createRouteStore(fake.env);

    const { getByRole, findByText } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday(), router },
    });

    await fireEvent.click(getByRole('button', { name: 'Настройки' }));
    expect(await findByText('Оформление')).toBeTruthy();
    expect(fake.location.pathname).toBe('/settings');
  });

  it('opens the per-kind list from the landing section buttons', async () => {
    const fake = makeFakeEnv('/');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const client = makeClient();

    const { findByRole } = render(App, {
      props: { client, selection, today: makeToday(), router },
    });

    await fireEvent.click(await findByRole('button', { name: 'Учителя' }));

    await waitFor(() => expect(fake.location.pathname).toBe('/list/teacher'));
    expect(selection.kind).toBe('teacher');
    await waitFor(() => expect(client.getTeachers).toHaveBeenCalledWith('gym1'));
  });

  it('switching a kind on the list updates it and clears the selected entity', async () => {
    const fake = makeFakeEnv('/list/class');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const client = makeClient();

    const { getByRole } = render(App, {
      props: { client, selection, today: makeToday(), router },
    });

    await fireEvent.click(getByRole('tab', { name: 'Учителя' }));

    await waitFor(() => expect(selection.kind).toBe('teacher'));
    expect(selection.name).toBeNull();
    expect(fake.location.pathname).toBe('/list/teacher');
    await waitFor(() => expect(client.getTeachers).toHaveBeenCalledWith('gym1'));
  });

  it('opens the schedule variants comparison from settings', async () => {
    const fake = makeFakeEnv('/settings');
    const router = createRouteStore(fake.env);

    const { getByRole, findByText } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday(), router },
    });

    await fireEvent.click(getByRole('button', { name: 'Показать варианты расписания' }));

    expect(await findByText('1. Карточки')).toBeTruthy();
    expect(fake.location.pathname).toBe('/variants');
  });

  it('opens the /variants deep link directly', async () => {
    const fake = makeFakeEnv('/variants');
    const router = createRouteStore(fake.env);

    const { findByText } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday(), router },
    });

    expect(await findByText('Варианты расписания')).toBeTruthy();
  });

  it('opens a list deep link for the linked kind', async () => {
    const fake = makeFakeEnv('/list/teacher');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const client = makeClient();

    render(App, { props: { client, selection, today: makeToday(), router } });

    await waitFor(() => expect(client.getTeachers).toHaveBeenCalledWith('gym1'));
    expect(selection.kind).toBe('teacher');
  });

  it('opens the free-rooms screen from the «Кабинеты» list', async () => {
    const fake = makeFakeEnv('/list/room');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    selection.selectSchool('gym1');

    const { findByRole } = render(App, {
      props: { client: makeClient(), selection, today: makeToday(), router },
    });

    await fireEvent.click(await findByRole('button', { name: 'Свободные кабинеты' }));

    expect(await findByRole('combobox', { name: 'Урок' })).toBeTruthy();
    expect(fake.location.pathname).toBe('/tools');
  });

  it('opens a class picked on the list and syncs the URL', async () => {
    const fake = makeFakeEnv('/list/class');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const client = makeClient({
      getClasses: vi.fn().mockResolvedValue({ classes: ['5А', '6Б'] }),
    });

    const { findByRole, getByRole } = render(App, {
      props: { client, selection, today: makeToday(), router },
    });

    await fireEvent.click(await findByRole('button', { name: '6' }));
    await fireEvent.click(getByRole('button', { name: 'Б' }));

    await waitFor(() => expect(selection.name).toBe('6Б'));
    expect(selection.kind).toBe('class');
    expect(fake.location.pathname).toBe('/s/gym1/class/6%D0%91');
  });

  it('returns to the kind list from the schedule back button', async () => {
    const fake = makeFakeEnv('/s/gym1/class/5%D0%90');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();

    const { findByRole } = render(App, {
      props: { client: makeClient(), selection, today: makeToday(), router },
    });
    await waitFor(() => expect(selection.name).toBe('5А'));

    await fireEvent.click(await findByRole('button', { name: 'К списку' }));
    await waitFor(() => expect(fake.location.pathname).toBe('/list/class'));
  });

  it('routes the schedule «На главную» control home', async () => {
    const fake = makeFakeEnv('/s/gym1/class/5%D0%90');
    const router = createRouteStore(fake.env);

    const { findByRole } = render(App, { props: { ...baseProps(), router } });

    await fireEvent.click(await findByRole('button', { name: 'На главную' }));
    await waitFor(() => expect(fake.location.pathname).toBe('/'));
  });

  it('opens a share deep link at the linked entity and date', async () => {
    const fake = makeFakeEnv('/s/gym1/class/5%D0%90?date=07.09.2026');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    const client = makeClient();

    const { findByText } = render(App, {
      props: { client, selection, today: makeToday(), router },
    });

    await waitFor(() => expect(router.started).toBe(true));
    await waitFor(() => expect(selection.schoolId).toBe('gym1'));
    expect(selection.kind).toBe('class');
    expect(selection.name).toBe('5А');
    await waitFor(() =>
      expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '07.09.2026'),
    );
    expect(await findByText('Расписание на 07.09.2026')).toBeTruthy();
  });

  it('uses the server today for a deep link without a date', async () => {
    const fake = makeFakeEnv('/s/gym1/class/5%D0%90');
    const router = createRouteStore(fake.env);
    const client = makeClient();

    render(App, {
      props: { client, selection: makeSelection(), today: makeToday('05.10.2026'), router },
    });

    await waitFor(() =>
      expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '05.10.2026'),
    );
  });

  it('adds an opened entity to favorites automatically', async () => {
    const favorites = makeFavorites();
    const { router } = makeRouter(makeFakeEnv('/s/gym1/class/5%D0%90').env);
    render(App, { props: { ...baseProps(), favorites, router } });
    await waitFor(() => expect(favorites.has('gym1', 'class', '5А')).toBe(true));
  });

  it('honors removing an auto-favorited entity while its schedule stays open', async () => {
    const favorites = makeFavorites();
    const { router } = makeRouter(makeFakeEnv('/s/gym1/class/5%D0%90').env);
    render(App, { props: { ...baseProps(), favorites, router } });
    // The auto-favorite effect runs on open.
    await waitFor(() => expect(favorites.has('gym1', 'class', '5А')).toBe(true));
    // The user removes it via the schedule's own toggle, then Svelte flushes the
    // pending effect. The write is untracked, so it must not be re-added.
    flushSync(() => favorites.remove('gym1', 'class', '5А'));
    await tick();
    expect(favorites.has('gym1', 'class', '5А')).toBe(false);
  });

  it('threads strikeout_free_lsn=false from /api/schools into the schedule (W41 fix)', async () => {
    const fake = makeFakeEnv('/s/gym1/class/5%D0%90');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    const client = makeClient({
      getSchools: vi.fn().mockResolvedValue({
        today: '05.10.2026',
        schools: [
          {
            id: 'gym1',
            name: 'Гимназия №1',
            loaded: true,
            features: { strikeout_free_lsn: false },
          },
        ],
      }),
      getDay: vi.fn().mockResolvedValue({
        date: '05.10.2026',
        day_name: 'Понедельник',
        kind: 'class',
        entity: '5А',
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
        vacation: false,
        weekend: false,
        no_period: false,
        period: null,
        shift: null,
      }),
    });

    const { findByText, queryByText } = render(App, {
      props: { client, selection, today: makeToday('05.10.2026'), router },
    });

    await waitFor(() => expect(selection.name).toBe('5А'));
    expect(await findByText('Занятий нет')).toBeTruthy();
    expect(queryByText('Отменён')).toBeNull();
  });

  it('lets the settings strike-through override the school flag', async () => {
    const fake = makeFakeEnv('/s/gym1/class/5%D0%90');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    const settings = makeSettings();
    // School hides free lessons; the user explicitly re-enables strike-through.
    settings.setStrikeoutFreeLsn(true);
    const client = makeClient({
      getSchools: vi.fn().mockResolvedValue({
        today: '05.10.2026',
        schools: [
          {
            id: 'gym1',
            name: 'Гимназия №1',
            loaded: true,
            features: { strikeout_free_lsn: false },
          },
        ],
      }),
      getDay: vi.fn().mockResolvedValue({
        date: '05.10.2026',
        day_name: 'Понедельник',
        kind: 'class',
        entity: '5А',
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
        vacation: false,
        weekend: false,
        no_period: false,
        period: null,
        shift: null,
      }),
    });

    const { findByText } = render(App, {
      props: { client, selection, settings, today: makeToday('05.10.2026'), router },
    });

    // The user override wins, so the cancelled row is shown (struck through).
    await waitFor(() => expect(selection.name).toBe('5А'));
    expect(await findByText('Отменён')).toBeTruthy();
  });

  it('honours the «show lesson number and time» setting in the schedule', async () => {
    const fake = makeFakeEnv('/s/gym1/class/5%D0%90');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    const settings = makeSettings();
    settings.setShowLessonTime(false);
    const client = makeClient({
      getDay: vi.fn().mockResolvedValue({
        date: '05.10.2026',
        day_name: 'Понедельник',
        kind: 'class',
        entity: '5А',
        lessons: [
          {
            num: 1,
            start: '08:00',
            end: '08:45',
            items: [
              {
                subject: 'Математика',
                teacher: 'Иванов',
                room: '101',
                class_name: '5А',
                groups: null,
                is_method_hour: false,
              },
            ],
            has_exchange: false,
            is_cancelled: false,
          },
        ],
        vacation: false,
        weekend: false,
        no_period: false,
        period: null,
        shift: null,
      }),
    });

    const { findByText, queryByText } = render(App, {
      props: { client, selection, settings, today: makeToday('05.10.2026'), router },
    });

    expect(await findByText('Математика')).toBeTruthy();
    expect(queryByText('08:00–08:45')).toBeNull();
  });

  it('falls back to the landing for an unknown deep link', async () => {
    const fake = makeFakeEnv('/s/gym1/magic/5%D0%90');
    const router = createRouteStore(fake.env);
    const { findByRole } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday(), router },
    });
    expect(await findByRole('button', { name: '1' })).toBeTruthy();
  });

  it('renders the landing (not a broken schedule) for a bare /schedule URL', async () => {
    const fake = makeFakeEnv('/schedule');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const client = makeClient();

    const { findByRole } = render(App, {
      props: { client, selection, today: makeToday(), router },
    });

    expect(await findByRole('button', { name: '1' })).toBeTruthy();
    expect(client.getDay).not.toHaveBeenCalled();
  });

  it('syncs the URL to a day opened from the month calendar', async () => {
    const fake = makeFakeEnv('/s/gym1/class/5%D0%90');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    const client = makeClient({
      getCalendar: vi
        .fn()
        .mockResolvedValue(makeCalendar([makeCalendarDay({ date: '05.10.2026' })])),
    });

    const { getByRole } = render(App, {
      props: { client, selection, today: makeToday('05.10.2026'), router },
    });
    await waitFor(() => expect(selection.name).toBe('5А'));
    await waitFor(() => expect(client.getDay).toHaveBeenCalled());

    await fireEvent.click(getByRole('tab', { name: 'Месяц' }));
    await waitFor(() => expect(client.getCalendar).toHaveBeenCalled());

    await fireEvent.click(getByRole('button', { name: /05\.10\.2026/ }));
    await waitFor(() => expect(fake.location.search).toContain('date=05.10.2026'));
  });

  describe('W24 Telegram WebApp', () => {
    it('works in a regular browser with no SDK (no crash, BackButton inert)', async () => {
      const fake = makeFakeEnv('/list/room');
      const router = createRouteStore(fake.env);
      const selection = makeSelection();
      selection.selectSchool('gym1');
      const { findByRole } = render(App, {
        props: {
          client: makeClient(),
          selection,
          today: makeToday(),
          router,
          telegram: {},
        },
      });
      await fireEvent.click(await findByRole('button', { name: 'Свободные кабинеты' }));
      expect(await findByRole('combobox', { name: 'Урок' })).toBeTruthy();
    });

    it('applies the SDK theme and shows the BackButton off Home', async () => {
      const fake = makeFakeEnv('/tools');
      const router = createRouteStore(fake.env);
      const style = { setProperty: vi.fn() };
      const show = vi.fn();
      const hide = vi.fn();
      const onClick = vi.fn();
      const offClick = vi.fn();

      render(App, {
        props: {
          client: makeClient(),
          selection: makeSelection(),
          today: makeToday(),
          router,
          themeTarget: { style },
          telegram: {
            webApp: {
              initData: 'query_id=abc',
              colorScheme: 'dark',
              themeParams: { bg_color: '#101010' },
              BackButton: { show, hide, onClick, offClick },
            },
          },
        },
      });

      await waitFor(() => expect(show).toHaveBeenCalled());
      expect(style.setProperty).toHaveBeenCalledWith('--tg-bg', '#101010');
      expect(onClick).toHaveBeenCalled();
    });

    it('hides the BackButton on Home even with the SDK present', async () => {
      const { router } = makeRouter();
      const show = vi.fn();
      const hide = vi.fn();
      render(App, {
        props: {
          client: makeClient(),
          selection: makeSelection(),
          today: makeToday(),
          router,
          telegram: { webApp: { initData: 'x', BackButton: { show, hide } } },
        },
      });
      await waitFor(() => expect(hide).toHaveBeenCalled());
      expect(show).not.toHaveBeenCalled();
    });
  });
});
