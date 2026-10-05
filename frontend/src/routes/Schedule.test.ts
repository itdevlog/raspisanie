import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Schedule from './Schedule.svelte';
import { makeClient, makeDay, makeSelection, makeToday } from '../test-helpers';
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

  it('switches between class / teacher / room and reloads the name list', async () => {
    const client = makeClient();
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const today = makeToday('05.10.2026');

    const { getByRole, findByText } = render(Schedule, {
      props: { client, selection, today },
    });

    await waitFor(() => expect(client.getClasses).toHaveBeenCalledWith('gym1'));

    await fireEvent.click(getByRole('tab', { name: 'Учитель' }));
    await waitFor(() => expect(client.getTeachers).toHaveBeenCalledWith('gym1'));
    expect(await findByText('Иванов И.И.')).toBeTruthy();
    // Switching kind must not carry the class name over to teachers.
    expect(selection.kind).toBe('teacher');
    expect(selection.name).toBeNull();

    await fireEvent.click(getByRole('tab', { name: 'Кабинет' }));
    await waitFor(() => expect(client.getRooms).toHaveBeenCalledWith('gym1'));
    expect(await findByText('101')).toBeTruthy();
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
});
