import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import FreeRooms from './FreeRooms.svelte';

describe('FreeRooms', () => {
  it('renders the free rooms for the selected lesson and date', () => {
    const { getByText, getByRole, getByDisplayValue } = render(FreeRooms, {
      props: {
        date: '05.10.2026',
        lesson: 3,
        rooms: ['101', '202'],
        status: 'ready',
        onLessonChange: vi.fn(),
      },
    });
    expect(getByText('101')).toBeTruthy();
    expect(getByText('202')).toBeTruthy();
    expect(getByText('05.10.2026')).toBeTruthy();
    expect((getByRole('combobox') as HTMLSelectElement).value).toBe('3');
    expect(getByDisplayValue('3')).toBeTruthy();
  });

  it('offers lessons 1..12 inline with no prompt', () => {
    const { getByRole } = render(FreeRooms, {
      props: {
        date: '05.10.2026',
        lesson: 1,
        rooms: [],
        status: 'ready',
        onLessonChange: vi.fn(),
      },
    });
    const options = Array.from((getByRole('combobox') as HTMLSelectElement).options);
    expect(options.map((o) => o.value)).toEqual(
      Array.from({ length: 12 }, (_, i) => String(i + 1)),
    );
  });

  it('raises onLessonChange with the picked lesson', async () => {
    const onLessonChange = vi.fn();
    const { getByRole } = render(FreeRooms, {
      props: {
        date: '05.10.2026',
        lesson: 1,
        rooms: [],
        status: 'ready',
        onLessonChange,
      },
    });

    await fireEvent.change(getByRole('combobox'), { target: { value: '7' } });
    expect(onLessonChange).toHaveBeenCalledWith(7);
  });

  it('shows an "all busy" message when no rooms are free', () => {
    const { getByText } = render(FreeRooms, {
      props: {
        date: '05.10.2026',
        lesson: 2,
        rooms: [],
        status: 'ready',
        onLessonChange: vi.fn(),
      },
    });
    expect(getByText('Все кабинеты заняты')).toBeTruthy();
  });

  it('shows loading and error states', () => {
    const { getByText, rerender } = render(FreeRooms, {
      props: {
        date: '05.10.2026',
        lesson: 1,
        rooms: [],
        status: 'loading',
        onLessonChange: vi.fn(),
      },
    });
    expect(getByText('Загрузка…')).toBeTruthy();

    rerender({ status: 'error', error: 'Сбой сети' });
    expect(getByText('Сбой сети')).toBeTruthy();
  });
});
