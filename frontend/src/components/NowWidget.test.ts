import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import NowWidget from './NowWidget.svelte';
import type { NowResponse } from '../lib/api/types';

function nowWith(overrides: Partial<NowResponse> = {}): NowResponse {
  return { server_time: '2026-10-05T10:00:00+03:00', current: null, next: null, ...overrides };
}

const currentLesson = {
  num: 2,
  time: '09:00-09:45',
  subject: 'Физика',
  room: '202',
  in_minutes: 20,
};
const nextLesson = {
  num: 3,
  time: '10:00-10:45',
  subject: 'Математика',
  room: '101',
  in_minutes: 15,
};

describe('NowWidget', () => {
  it('renders the current lesson with subject, room and time', () => {
    const { getByText } = render(NowWidget, {
      props: { data: nowWith({ current: currentLesson }), status: 'ready', error: null },
    });
    expect(getByText('Идёт урок')).toBeTruthy();
    expect(getByText(/Физика/)).toBeTruthy();
    expect(getByText(/каб\. 202/)).toBeTruthy();
    expect(getByText(/09:00-09:45/)).toBeTruthy();
    expect(getByText(/осталось 20 мин/)).toBeTruthy();
  });

  it('renders the next lesson when none is currently running', () => {
    const { getByText } = render(NowWidget, {
      props: { data: nowWith({ next: nextLesson }), status: 'ready', error: null },
    });
    expect(getByText('До начала')).toBeTruthy();
    expect(getByText(/Математика/)).toBeTruthy();
    expect(getByText(/через 15 мин/)).toBeTruthy();
  });

  it('handles both-null gracefully', () => {
    const { getByText } = render(NowWidget, {
      props: { data: nowWith(), status: 'ready', error: null },
    });
    expect(getByText('Уроков нет')).toBeTruthy();
  });

  it('shows a loading state before the first response', () => {
    const { getByText } = render(NowWidget, {
      props: { data: null, status: 'loading', error: null },
    });
    expect(getByText('Загрузка…')).toBeTruthy();
  });

  it('surfaces a load error', () => {
    const { getByText } = render(NowWidget, {
      props: { data: null, status: 'error', error: 'Сеть недоступна' },
    });
    expect(getByText('Сеть недоступна')).toBeTruthy();
  });
});
