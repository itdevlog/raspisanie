import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Schedule from './Schedule.svelte';
import {
  fireSwipe,
  makeCalendar,
  makeCalendarDay,
  makeClient,
  makeDay,
  makeFavorites,
  makeSelection,
  makeToday,
} from '../test-helpers';
import type { DaySchedule } from '../lib/api/types';

function dayFor(date: string, overrides: Partial<DaySchedule> = {}): DaySchedule {
  return makeDay({ date, ...overrides });
}

describe('Schedule screen', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('requests the server today (not the browser clock) for "Сегодня"', async () => {
    // Browser clock is far in the future; the server says 05.10.2026.
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2030-06-15T12:00:00Z'));

    const client = makeClient({
      getDay: vi.fn().mockResolvedValue(dayFor('05.10.2026')),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const today = makeToday('05.10.2026');

    render(Schedule, { props: { client, selection, today } });

    await waitFor(() => expect(client.getDay).toHaveBeenCalled());
    // The requested date is the server's, never the browser's year/month.
    expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '05.10.2026');
    const requestedDate = (client.getDay as ReturnType<typeof vi.fn>).mock.calls[0][3] as string;
    expect(requestedDate).not.toContain('2030');
  });

  it('requests a day the browser clock does not know about for "Завтра"', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2030-06-15T12:00:00Z'));

    const client = makeClient({
      getDay: vi.fn().mockResolvedValue(dayFor('06.10.2026')),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const today = makeToday('05.10.2026');

    const { getByRole } = render(Schedule, { props: { client, selection, today } });
    await waitFor(() => expect(client.getDay).toHaveBeenCalled());
    (client.getDay as ReturnType<typeof vi.fn>).mockClear();

    await fireEvent.click(getByRole('tab', { name: 'Завтра' }));

    await waitFor(() =>
      expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '06.10.2026'),
    );
  });

  it('loads the week payload for the "Неделя" tab', async () => {
    const client = makeClient({
      getWeek: vi.fn().mockResolvedValue({ days: [dayFor('05.10.2026'), dayFor('06.10.2026')] }),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const today = makeToday('05.10.2026');

    const { getByRole } = render(Schedule, { props: { client, selection, today } });
    await waitFor(() => expect(client.getDay).toHaveBeenCalled());

    await fireEvent.click(getByRole('tab', { name: 'Неделя' }));
    await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', 0));
  });

  it('shows a vacation notice from the day payload', async () => {
    const client = makeClient({
      getDay: vi.fn().mockResolvedValue(dayFor('05.10.2026', { vacation: true })),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const today = makeToday('05.10.2026');

    const { findByText } = render(Schedule, { props: { client, selection, today } });
    expect(await findByText('Каникулы')).toBeTruthy();
  });

  it('prompts for a school when none is selected', async () => {
    const client = makeClient();
    const { findByText } = render(Schedule, {
      props: { client, selection: makeSelection(), today: makeToday() },
    });
    expect(await findByText('Школа не выбрана')).toBeTruthy();
    expect(client.getDay).not.toHaveBeenCalled();
  });

  it('opens the date pinned by a share link instead of the server today', async () => {
    const client = makeClient({
      getDay: vi.fn().mockResolvedValue(dayFor('07.09.2026')),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');

    const { findByText } = render(Schedule, {
      props: { client, selection, today: makeToday('05.10.2026'), pinnedDate: '07.09.2026' },
    });

    await waitFor(() =>
      expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '07.09.2026'),
    );
    expect(await findByText('Расписание на 07.09.2026')).toBeTruthy();
  });

  it('switching period tabs drops the pinned share date', async () => {
    const client = makeClient({ getDay: vi.fn().mockResolvedValue(dayFor('06.10.2026')) });
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');

    const { getByRole } = render(Schedule, {
      props: { client, selection, today: makeToday('05.10.2026'), pinnedDate: '07.09.2026' },
    });
    await waitFor(() =>
      expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '07.09.2026'),
    );
    (client.getDay as ReturnType<typeof vi.fn>).mockClear();

    await fireEvent.click(getByRole('tab', { name: 'Завтра' }));

    await waitFor(() =>
      expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '06.10.2026'),
    );
  });

  it('copies a W16-identical share link to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');

    const { getByRole, findByText } = render(Schedule, {
      props: {
        client,
        selection,
        today: makeToday('05.10.2026'),
        origin: 'https://rasp.example.ru',
        navigatorLike: { clipboard: { writeText } },
      },
    });

    // Wait until the server today is loaded so the link can pin the date.
    await waitFor(() => expect(client.getDay).toHaveBeenCalled());
    await fireEvent.click(getByRole('button', { name: 'Поделиться' }));

    // Byte-for-byte the W16 builder's output.
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith(
        'https://rasp.example.ru/s/gym1/class/5%D0%90?date=05.10.2026',
      ),
    );
    expect(await findByText('Ссылка скопирована')).toBeTruthy();
  });

  it('uses navigator.share when available', async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('teacher', 'Иванов И.И.');

    const { getByRole } = render(Schedule, {
      props: {
        client,
        selection,
        today: makeToday('05.10.2026'),
        origin: 'https://rasp.example.ru',
        navigatorLike: { share },
      },
    });

    await waitFor(() => expect(client.getDay).toHaveBeenCalled());
    await fireEvent.click(getByRole('button', { name: 'Поделиться' }));

    await waitFor(() =>
      expect(share).toHaveBeenCalledWith(
        expect.objectContaining({
          url: 'https://rasp.example.ru/s/gym1/teacher/%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2%20%D0%98.%D0%98.?date=05.10.2026',
        }),
      ),
    );
  });

  // W23: push opt-in. The fake push fn receives the selected class + W16 URL.
  it('enables push for the selected class with the W16 share URL', async () => {
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const pushEnable = vi.fn().mockResolvedValue({ ok: true, state: 'subscribed' });

    const { getByRole, findByText } = render(Schedule, {
      props: {
        client,
        selection,
        today: makeToday('05.10.2026'),
        origin: 'https://rasp.example.ru',
        pushEnable,
        pushDisable: vi.fn(),
        pushSupported: true,
      },
    });

    await waitFor(() => expect(client.getDay).toHaveBeenCalled());
    await fireEvent.click(getByRole('button', { name: 'Включить уведомления' }));

    await waitFor(() =>
      expect(pushEnable).toHaveBeenCalledWith({
        schoolId: 'gym1',
        name: '5А',
        kind: 'class',
        url: 'https://rasp.example.ru/s/gym1/class/5%D0%90?date=05.10.2026',
      }),
    );
    expect(await findByText('Выключить уведомления')).toBeTruthy();
  });

  it('disables push through the injected handler', async () => {
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const pushDisable = vi.fn().mockResolvedValue({ ok: true, state: 'subscribed' });

    const { getByRole, findByText } = render(Schedule, {
      props: {
        client,
        selection,
        today: makeToday('05.10.2026'),
        pushEnable: vi.fn(),
        pushDisable,
        // Pretend a subscription already exists so the button offers opt-out.
        pushInitiallyOn: true,
        pushSupported: true,
      },
    });

    await waitFor(() => expect(client.getDay).toHaveBeenCalled());
    expect(await findByText('Выключить уведомления')).toBeTruthy();
    await fireEvent.click(getByRole('button', { name: 'Выключить уведомления' }));
    await waitFor(() => expect(pushDisable).toHaveBeenCalled());
  });

  it('does not offer push for teacher/room (MVP class-only)', async () => {
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('teacher', 'Иванов И.И.');

    const { queryByRole, getByRole } = render(Schedule, {
      props: { client, selection, today: makeToday('05.10.2026') },
    });

    await waitFor(() => expect(client.getDay).toHaveBeenCalled());
    expect(queryByRole('button', { name: /уведомления/ })).toBeNull();
    expect(getByRole('button', { name: 'Поделиться' })).toBeTruthy();
  });

  it('shows the offline indicator when the browser reports offline', async () => {
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');

    const { findByText } = render(Schedule, {
      props: {
        client,
        selection,
        today: makeToday('05.10.2026'),
        connectivity: {
          online: false,
          addEventListener: () => {},
          removeEventListener: () => {},
        },
      },
    });

    expect(await findByText('Нет подключения к сети')).toBeTruthy();
  });

  // W24: «Открыть в Telegram» control on the schedule screen.
  it('renders an «Открыть в Telegram» deep link carrying the shown target', async () => {
    vi.stubEnv('VITE_TELEGRAM_BOT', 'raspisanie_bot');
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');

    const { findByRole } = render(Schedule, {
      props: { client, selection, today: makeToday('05.10.2026') },
    });

    const link = (await findByRole('link', { name: 'Открыть в Telegram' })) as HTMLAnchorElement;
    expect(link.getAttribute('href')).toContain('https://t.me/raspisanie_bot?start=');
    vi.unstubAllEnvs();
  });

  it('hides the Telegram control when no bot username is configured', async () => {
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');

    const { queryByRole, findByRole } = render(Schedule, {
      props: { client, selection, today: makeToday('05.10.2026') },
    });

    // The Schedule («Поделиться») is present, but no Telegram link without config.
    await findByRole('button', { name: 'Поделиться' });
    expect(queryByRole('link', { name: 'Открыть в Telegram' })).toBeNull();
  });

  // W38: month calendar tab.
  describe('month calendar', () => {
    it('loads the month for the selected class using the server month', async () => {
      const client = makeClient({
        getCalendar: vi.fn().mockResolvedValue(makeCalendar([makeCalendarDay()])),
      });
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');

      const { getByRole } = render(Schedule, {
        props: { client, selection, today: makeToday('05.10.2026') },
      });
      await waitFor(() => expect(client.getDay).toHaveBeenCalled());

      await fireEvent.click(getByRole('tab', { name: 'Месяц' }));

      await waitFor(() =>
        expect(client.getCalendar).toHaveBeenCalledWith('gym1', 'class', '5А', 2026, 10),
      );
    });

    it('requests the month for a teacher too', async () => {
      const client = makeClient({
        getCalendar: vi.fn().mockResolvedValue(makeCalendar([makeCalendarDay()])),
      });
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('teacher', 'Иванов И.И.');

      const { getByRole } = render(Schedule, {
        props: { client, selection, today: makeToday('05.10.2026') },
      });
      await waitFor(() => expect(client.getDay).toHaveBeenCalled());

      await fireEvent.click(getByRole('tab', { name: 'Месяц' }));

      await waitFor(() =>
        expect(client.getCalendar).toHaveBeenCalledWith('gym1', 'teacher', 'Иванов И.И.', 2026, 10),
      );
    });

    it('opens the clicked day and notifies the router hook', async () => {
      const onOpenDay = vi.fn();
      const client = makeClient({
        getCalendar: vi
          .fn()
          .mockResolvedValue(
            makeCalendar([makeCalendarDay({ date: '05.10.2026', lesson_count: 6 })]),
          ),
        getDay: vi.fn().mockResolvedValue(dayFor('05.10.2026')),
      });
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');

      const { getByRole, findByText } = render(Schedule, {
        props: { client, selection, today: makeToday('05.10.2026'), onOpenDay },
      });
      await waitFor(() => expect(client.getDay).toHaveBeenCalled());
      (client.getDay as ReturnType<typeof vi.fn>).mockClear();

      await fireEvent.click(getByRole('tab', { name: 'Месяц' }));
      await waitFor(() => expect(client.getCalendar).toHaveBeenCalled());

      await fireEvent.click(getByRole('button', { name: /05\.10\.2026/ }));

      await waitFor(() =>
        expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '05.10.2026'),
      );
      expect(onOpenDay).toHaveBeenCalledWith('05.10.2026');
      // The day view replaced the calendar.
      expect(await findByText('Понедельник, 05.10.2026')).toBeTruthy();
    });

    it('navigates months across the year boundary', async () => {
      const client = makeClient({
        getCalendar: vi.fn().mockResolvedValue(makeCalendar([makeCalendarDay()])),
      });
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');

      const { getByRole } = render(Schedule, {
        props: { client, selection, today: makeToday('15.01.2026') },
      });
      await waitFor(() => expect(client.getDay).toHaveBeenCalled());

      await fireEvent.click(getByRole('tab', { name: 'Месяц' }));
      await waitFor(() =>
        expect(client.getCalendar).toHaveBeenCalledWith('gym1', 'class', '5А', 2026, 1),
      );

      await fireEvent.click(getByRole('button', { name: 'Предыдущий месяц' }));
      await waitFor(() =>
        expect(client.getCalendar).toHaveBeenCalledWith('gym1', 'class', '5А', 2025, 12),
      );

      await fireEvent.click(getByRole('button', { name: 'Следующий месяц' }));
      await waitFor(() =>
        expect(client.getCalendar).toHaveBeenCalledWith('gym1', 'class', '5А', 2026, 1),
      );
    });
  });

  // W38/W41 fix: week navigation and out-of-period calendar days.
  describe('week navigation (W38 fix)', () => {
    it('moves the week offset with prev/next and disables at bounds', async () => {
      const client = makeClient({
        getWeek: vi
          .fn()
          .mockResolvedValue({ days: [dayFor('05.10.2026')], weekday_num: 5 }),
      });
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');

      const { getByRole } = render(Schedule, {
        props: { client, selection, today: makeToday('05.10.2026') },
      });
      await waitFor(() => expect(client.getDay).toHaveBeenCalled());

      await fireEvent.click(getByRole('tab', { name: 'Неделя' }));
      await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', 0));

      const prev = getByRole('button', { name: 'Предыдущая неделя' }) as HTMLButtonElement;
      const next = getByRole('button', { name: 'Следующая неделя' }) as HTMLButtonElement;

      await fireEvent.click(next);
      await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', 1));
      await fireEvent.click(next);
      await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', 2));
      // Upper bound (-2..2) reached.
      expect(next.disabled).toBe(true);

      await fireEvent.click(prev);
      await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', 1));
      await fireEvent.click(prev);
      await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', 0));
      await fireEvent.click(prev);
      await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', -1));
      await fireEvent.click(prev);
      await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', -2));
      // Lower bound reached.
      expect(prev.disabled).toBe(true);
    });
  });

  describe('out-of-period calendar day (W41 fix)', () => {
    it('shows a graceful notice instead of a 422 load error', async () => {
      const onOpenDay = vi.fn();
      const client = makeClient({
        getCalendar: vi
          .fn()
          .mockResolvedValue(
            makeCalendar([makeCalendarDay({ date: '04.10.2026', no_period: true })]),
          ),
        getDay: vi.fn().mockResolvedValue(dayFor('05.10.2026')),
      });
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');

      const { getByRole, findByText } = render(Schedule, {
        props: { client, selection, today: makeToday('05.10.2026'), onOpenDay },
      });
      await waitFor(() => expect(client.getDay).toHaveBeenCalled());
      (client.getDay as ReturnType<typeof vi.fn>).mockClear();

      await fireEvent.click(getByRole('tab', { name: 'Месяц' }));
      await waitFor(() => expect(client.getCalendar).toHaveBeenCalled());

      await fireEvent.click(getByRole('button', { name: /04\.10\.2026/ }));

      expect(await findByText('Нет учебного периода')).toBeTruthy();
      expect(onOpenDay).toHaveBeenCalledWith('04.10.2026');
      // No day request for the out-of-period date (which the server would 422).
      expect(client.getDay).not.toHaveBeenCalledWith('gym1', 'class', '5А', '04.10.2026');
    });
  });

  describe('strikeout_free_lsn threading (W41 fix)', () => {
    it('hides a cancelled row when strikeoutFreeLsn is false', async () => {
      const cancelled = dayFor('05.10.2026', {
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
      });
      const client = makeClient({ getDay: vi.fn().mockResolvedValue(cancelled) });
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');

      const { findByText, queryByText } = render(Schedule, {
        props: {
          client,
          selection,
          today: makeToday('05.10.2026'),
          strikeoutFreeLsn: false,
        },
      });

      expect(await findByText('Занятий нет')).toBeTruthy();
      expect(queryByText('Отменён')).toBeNull();
    });
  });

  // W39: favorites for class/teacher/room, persisted per kind.
  describe('favorites', () => {
    it('toggles the shown class as a favorite', async () => {
      const client = makeClient();
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');
      const favorites = makeFavorites();

      const { getByRole } = render(Schedule, {
        props: { client, selection, today: makeToday('05.10.2026'), favorites },
      });
      await waitFor(() => expect(client.getDay).toHaveBeenCalled());

      const button = getByRole('button', { name: /5А/ });
      await fireEvent.click(button);
      expect(favorites.has('gym1', 'class', '5А')).toBe(true);

      await fireEvent.click(button);
      expect(favorites.has('gym1', 'class', '5А')).toBe(false);
    });

    it('favorites a teacher and a room under their own kinds', async () => {
      const client = makeClient();
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('teacher', 'Иванов И.И.');
      const favorites = makeFavorites();

      const { getByRole } = render(Schedule, {
        props: { client, selection, today: makeToday('05.10.2026'), favorites },
      });
      await waitFor(() => expect(client.getDay).toHaveBeenCalled());

      await fireEvent.click(getByRole('button', { name: /Иванов И\.И\./ }));
      expect(favorites.has('gym1', 'teacher', 'Иванов И.И.')).toBe(true);

      // The entity name is now chosen from the list; switching the shown entity
      // reloads the schedule for the new kind/name.
      selection.selectEntity('room', '101');
      await waitFor(() =>
        expect(client.getDay).toHaveBeenCalledWith('gym1', 'room', '101', '05.10.2026'),
      );
      await fireEvent.click(getByRole('button', { name: /101/ }));
      expect(favorites.has('gym1', 'room', '101')).toBe(true);
    });
  });

  it('renders a «К списку» back control wired to onBack', async () => {
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const onBack = vi.fn();

    const { getByRole } = render(Schedule, {
      props: { client, selection, today: makeToday('05.10.2026'), onBack },
    });

    await fireEvent.click(getByRole('button', { name: 'К списку' }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  // Swipe navigation: day cursor, week offset and month cursor.
  describe('swipe navigation', () => {
    function setup() {
      const selection = makeSelection();
      selection.selectSchool('gym1');
      selection.selectEntity('class', '5А');
      return selection;
    }

    it('renders a date + weekday heading for the day cursor', async () => {
      const client = makeClient({ getDay: vi.fn().mockResolvedValue(dayFor('05.10.2026')) });
      const { findByText } = render(Schedule, {
        props: { client, selection: setup(), today: makeToday('05.10.2026') },
      });

      expect(await findByText('05.10.2026, Понедельник')).toBeTruthy();
    });

    it('swipes the day pane to the next/previous day, clamped at the baseline', async () => {
      const client = makeClient({ getDay: vi.fn().mockResolvedValue(dayFor('05.10.2026')) });
      const { container } = render(Schedule, {
        props: { client, selection: setup(), today: makeToday('05.10.2026') },
      });
      await waitFor(() =>
        expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '05.10.2026'),
      );

      const pane = container.querySelector('.day-pane') as HTMLElement;
      fireSwipe(pane, -60); // left → next day
      await waitFor(() =>
        expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '06.10.2026'),
      );

      fireSwipe(pane, 60); // right → back to today
      await waitFor(() =>
        expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '05.10.2026'),
      );

      // Already at the baseline: a right swipe is a no-op (no past days).
      (client.getDay as ReturnType<typeof vi.fn>).mockClear();
      fireSwipe(pane, 60);
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(client.getDay).not.toHaveBeenCalled();
    });

    it('swipes the week pane to the next/previous week', async () => {
      const client = makeClient({
        getWeek: vi.fn().mockResolvedValue({ days: [dayFor('05.10.2026')] }),
      });
      const { getByRole, container } = render(Schedule, {
        props: { client, selection: setup(), today: makeToday('05.10.2026') },
      });
      await waitFor(() => expect(client.getDay).toHaveBeenCalled());

      await fireEvent.click(getByRole('tab', { name: 'Неделя' }));
      await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', 0));

      const pane = container.querySelector('.week-pane') as HTMLElement;
      fireSwipe(pane, -60);
      await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', 1));

      fireSwipe(pane, 60);
      await waitFor(() => expect(client.getWeek).toHaveBeenCalledWith('gym1', 'class', '5А', 0));
    });

    it('swipes the calendar grid to the next month', async () => {
      const client = makeClient({
        getCalendar: vi.fn().mockResolvedValue(makeCalendar([makeCalendarDay()])),
      });
      const { getByRole, container } = render(Schedule, {
        props: { client, selection: setup(), today: makeToday('05.10.2026') },
      });
      await waitFor(() => expect(client.getDay).toHaveBeenCalled());

      await fireEvent.click(getByRole('tab', { name: 'Месяц' }));
      await waitFor(() =>
        expect(client.getCalendar).toHaveBeenCalledWith('gym1', 'class', '5А', 2026, 10),
      );

      const grid = container.querySelector('.grid') as HTMLElement;
      fireSwipe(grid, -60);
      await waitFor(() =>
        expect(client.getCalendar).toHaveBeenCalledWith('gym1', 'class', '5А', 2026, 11),
      );

      fireSwipe(grid, 60);
      await waitFor(() =>
        expect(client.getCalendar).toHaveBeenCalledWith('gym1', 'class', '5А', 2026, 10),
      );
    });

    it('seeds the day cursor from a pinned date and swipes forward from it', async () => {
      const client = makeClient({ getDay: vi.fn().mockResolvedValue(dayFor('07.09.2026')) });
      const { container, findByText } = render(Schedule, {
        props: {
          client,
          selection: setup(),
          today: makeToday('05.10.2026'),
          pinnedDate: '07.09.2026',
        },
      });
      await waitFor(() =>
        expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '07.09.2026'),
      );
      expect(await findByText('Расписание на 07.09.2026')).toBeTruthy();

      const pane = container.querySelector('.day-pane') as HTMLElement;
      fireSwipe(pane, -60);
      await waitFor(() =>
        expect(client.getDay).toHaveBeenCalledWith('gym1', 'class', '5А', '08.09.2026'),
      );
      // The pinned notice follows the cursor.
      expect(await findByText('Расписание на 08.09.2026')).toBeTruthy();
    });
  });
});
