import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Tools from './Tools.svelte';
import { makeClient, makeSelection, makeToday } from '../test-helpers';

describe('Tools screen (free rooms)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('requests free rooms for the inline-selected lesson and renders them', async () => {
    const client = makeClient({
      getFreeRooms: vi.fn().mockResolvedValue({ free_rooms: ['101', '202'] }),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');

    const { getByRole, findByText } = render(Tools, {
      props: { client, selection, today: makeToday('05.10.2026') },
    });

    await waitFor(() => expect(client.getFreeRooms).toHaveBeenCalledWith('gym1', 1, '05.10.2026'));

    await fireEvent.change(getByRole('combobox'), { target: { value: '5' } });
    await waitFor(() => expect(client.getFreeRooms).toHaveBeenCalledWith('gym1', 5, '05.10.2026'));

    expect(await findByText('101')).toBeTruthy();
    expect(await findByText('202')).toBeTruthy();
  });

  it('uses the server today, never the browser clock, for free rooms', async () => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2030-06-15T12:00:00Z'));

    const client = makeClient({
      getFreeRooms: vi.fn().mockResolvedValue({ free_rooms: [] }),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');

    render(Tools, { props: { client, selection, today: makeToday('05.10.2026') } });

    await waitFor(() => expect(client.getFreeRooms).toHaveBeenCalled());
    const call = (client.getFreeRooms as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(call[2]).toBe('05.10.2026');
    expect(call[2]).not.toContain('2030');
  });

  it('never calls window.prompt/alert/confirm while picking a lesson', async () => {
    const promptSpy = vi.spyOn(window, 'prompt').mockImplementation(() => null);
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => undefined);
    const confirmSpy = vi.spyOn(window, 'confirm').mockImplementation(() => true);

    const client = makeClient({
      getFreeRooms: vi.fn().mockResolvedValue({ free_rooms: ['101'] }),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');

    const { getByRole } = render(Tools, {
      props: { client, selection, today: makeToday('05.10.2026') },
    });

    await fireEvent.change(getByRole('combobox'), { target: { value: '4' } });
    await waitFor(() => expect(client.getFreeRooms).toHaveBeenCalled());

    expect(promptSpy).not.toHaveBeenCalled();
    expect(alertSpy).not.toHaveBeenCalled();
    expect(confirmSpy).not.toHaveBeenCalled();

    promptSpy.mockRestore();
    alertSpy.mockRestore();
    confirmSpy.mockRestore();
  });

  it('renders a «К списку» back control wired to onBack', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const onBack = vi.fn();

    const { getByRole } = render(Tools, {
      props: { client: makeClient(), selection, today: makeToday('05.10.2026'), onBack },
    });

    await fireEvent.click(getByRole('button', { name: 'К списку' }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('asks to pick a school when none is selected', () => {
    const { getByText } = render(Tools, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday() },
    });
    expect(getByText('Школа не выбрана')).toBeTruthy();
  });
});
