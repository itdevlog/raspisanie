import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import FavoriteSummary from './FavoriteSummary.svelte';
import { makeClient } from '../test-helpers';

describe('FavoriteSummary', () => {
  it("renders today's lesson when /now has one", async () => {
    const client = makeClient({
      getNow: vi.fn().mockResolvedValue({
        server_time: '2026-10-05T10:00:00+03:00',
        current: { num: 3, time: '10:00–10:45', subject: 'Физика', room: '101', in_minutes: 20 },
        next: null,
      }),
    });
    render(FavoriteSummary, {
      props: { client, schoolId: 'gym1', kind: 'room', name: '101', today: '05.10.2026' },
    });
    expect(await screen.findByText('Идёт урок')).toBeTruthy();
    expect(client.getNow).toHaveBeenCalledWith('gym1', 'room', '101', '05.10.2026');
  });
  it('falls back to tomorrow with a «Завтра» note when today is empty', async () => {
    const client = makeClient({
      getNow: vi
        .fn()
        .mockResolvedValueOnce({
          server_time: '2026-10-05T18:00:00+03:00',
          current: null,
          next: null,
        })
        .mockResolvedValueOnce({
          server_time: '2026-10-05T18:00:00+03:00',
          current: {
            num: 1,
            time: '08:00–08:45',
            subject: 'Математика',
            room: '12',
            in_minutes: 0,
          },
          next: null,
        }),
    });
    render(FavoriteSummary, {
      props: { client, schoolId: 'gym1', kind: 'class', name: '5А', today: '05.10.2026' },
    });
    expect(await screen.findByText('Завтра')).toBeTruthy();
    expect(client.getNow).toHaveBeenLastCalledWith('gym1', 'class', '5А', '06.10.2026');
  });

  it('does not show the «Завтра» note when the tomorrow request fails', async () => {
    const client = makeClient({
      getNow: vi
        .fn()
        .mockResolvedValueOnce({
          server_time: '2026-10-05T18:00:00+03:00',
          current: null,
          next: null,
        })
        .mockRejectedValueOnce(new Error('boom')),
    });
    render(FavoriteSummary, {
      props: { client, schoolId: 'gym1', kind: 'class', name: '5А', today: '05.10.2026' },
    });
    expect(await screen.findByText('Не удалось загрузить текущий урок')).toBeTruthy();
    expect(screen.queryByText('Завтра')).toBeNull();
  });
});
