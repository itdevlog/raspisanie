import { describe, it, expect, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import App from './App.svelte';
import {
  makeCalendar,
  makeCalendarDay,
  makeClient,
  makeFakeEnv,
  makeRouter,
  makeSelection,
  makeToday,
} from './test-helpers';
import { createRouteStore } from './lib/stores/route.svelte';

describe('App shell', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders the home screen with navigation by default', async () => {
    const { router } = makeRouter();
    const { getByRole, findByText } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday(), router },
    });
    expect(getByRole('navigation', { name: 'Разделы' })).toBeTruthy();
    expect(getByRole('button', { name: 'Главная' })).toBeTruthy();
    expect(await findByText('Гимназия №1')).toBeTruthy();
  });

  it('switches to the schedule screen and keeps the URL in sync', async () => {
    const fake = makeFakeEnv('/');
    const router = createRouteStore(fake.env);
    const { getByRole, findByText } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday(), router },
    });
    await waitFor(() => expect(router.started).toBe(true));

    await fireEvent.click(getByRole('button', { name: 'Расписание' }));

    expect(await findByText('Школа не выбрана')).toBeTruthy();
    // Bare schedule view (no entity yet) keeps a clean, deep-linkable URL.
    expect(fake.location.pathname).toBe('/schedule');
  });

  it('switches to the search & free-rooms screen', async () => {
    const { router } = makeRouter();
    const { getByRole, findByText } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday(), router },
    });
    await waitFor(() => expect(getByRole('button', { name: 'Поиск' })).toBeTruthy());

    await fireEvent.click(getByRole('button', { name: 'Поиск' }));

    expect(await findByText('Поиск и кабинеты')).toBeTruthy();
  });

  it('opens the free-rooms screen from the home button', async () => {
    const fake = makeFakeEnv('/');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    selection.selectSchool('gym1');

    const { findByRole, findByText } = render(App, {
      props: { client: makeClient(), selection, today: makeToday(), router },
    });
    await waitFor(() => expect(router.started).toBe(true));

    await fireEvent.click(await findByRole('button', { name: 'Свободные кабинеты' }));

    expect(await findByText('Поиск и кабинеты')).toBeTruthy();
    expect(fake.location.pathname).toBe('/tools');
  });

  it('opens a share deep link at the linked entity and date', async () => {
    // W16-shaped link: /s/{school}/class/{encoded name}?date=…
    const fake = makeFakeEnv('/s/gym1/class/5%D0%90?date=07.09.2026');
    const router = createRouteStore(fake.env);
    const selection = makeSelection();
    const client = makeClient();

    const { findByText } = render(App, {
      props: { client, selection, today: makeToday(), router },
    });

    await waitFor(() => expect(router.started).toBe(true));
    // The selection store was seeded from the URL.
    await waitFor(() => expect(selection.schoolId).toBe('gym1'));
    expect(selection.kind).toBe('class');
    expect(selection.name).toBe('5А');
    // The pinned date was requested from the API, not the server today.
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
    // The cancelled/free row is hidden because the shell read the flag.
    expect(await findByText('Занятий нет')).toBeTruthy();
    expect(queryByText('Отменён')).toBeNull();
  });

  it('falls back to Home for an unknown deep link', async () => {
    const fake = makeFakeEnv('/s/gym1/magic/5%D0%90');
    const router = createRouteStore(fake.env);
    const { findByText } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday(), router },
    });
    expect(await findByText('Гимназия №1')).toBeTruthy();
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
      const { router } = makeRouter();
      const { getByRole, findByText } = render(App, {
        props: {
          client: makeClient(),
          selection: makeSelection(),
          today: makeToday(),
          router,
          telegram: {},
        },
      });
      // The app still renders and navigates without a Telegram SDK.
      await fireEvent.click(getByRole('button', { name: 'Поиск' }));
      expect(await findByText('Поиск и кабинеты')).toBeTruthy();
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
