import { describe, it, expect, vi } from 'vitest';
import { render, waitFor } from '@testing-library/svelte';
import Variants from './Variants.svelte';
import type { Lesson, LessonItem } from '../lib/api/types';
import { makeClient, makeDay, makeSelection, makeToday } from '../test-helpers';

function makeItem(overrides: Partial<LessonItem> = {}): LessonItem {
  return {
    subject: 'Математика',
    teacher: 'Иванов И.И.',
    room: '101',
    class_name: '6А',
    groups: null,
    is_method_hour: false,
    ...overrides,
  };
}

function makeLesson(overrides: Partial<Lesson> = {}): Lesson {
  return {
    num: 1,
    start: '08:00',
    end: '08:45',
    items: [makeItem()],
    has_exchange: false,
    is_cancelled: false,
    ...overrides,
  };
}

describe('Variants comparison screen', () => {
  it('renders all five labelled layout sections', () => {
    const { container, getByText } = render(Variants, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday() },
    });

    expect(container.querySelectorAll('[data-variant]')).toHaveLength(5);
    expect(getByText('1. Компактный (текущий)')).toBeTruthy();
    expect(getByText('2. Карточки')).toBeTruthy();
    expect(getByText('3. Таблица')).toBeTruthy();
    expect(getByText('4. Таймлайн')).toBeTruthy();
    expect(getByText('5. Сейчас / далее')).toBeTruthy();
  });

  it('falls back to the built-in sample day when no school is selected', () => {
    const { getAllByText, getByText } = render(Variants, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday() },
    });

    // Sample subjects and the split-group / method-hour / status states render.
    expect(getAllByText('Русский язык').length).toBeGreaterThan(0);
    expect(getAllByText('Группа 1').length).toBeGreaterThan(0);
    expect(getAllByText('Группа 2').length).toBeGreaterThan(0);
    expect(getAllByText('Метод. час').length).toBeGreaterThan(0);
    expect(getAllByText('Замена').length).toBeGreaterThan(0);
    expect(getAllByText('Отменён').length).toBeGreaterThan(0);
    expect(getByText('Показан примерный день')).toBeTruthy();
  });

  it("uses the selected entity's day when one is available", async () => {
    const client = makeClient({
      getDay: vi.fn().mockResolvedValue(
        makeDay({
          lessons: [makeLesson({ items: [makeItem({ subject: 'Химия', teacher: 'Соколова М.М.' })] })],
        }),
      ),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '6А');

    const { findAllByText, queryByText } = render(Variants, {
      props: { client, selection, today: makeToday() },
    });

    await waitFor(() => expect(client.getDay).toHaveBeenCalled());
    expect((client.getDay as ReturnType<typeof vi.fn>).mock.calls[0].slice(0, 3)).toEqual([
      'gym1',
      'class',
      '6А',
    ]);
    expect((await findAllByText('Химия')).length).toBeGreaterThan(0);
    expect(queryByText('Показан примерный день')).toBeNull();
  });

  it('falls back to the sample when the selected day has no lessons', async () => {
    const client = makeClient({
      getDay: vi.fn().mockResolvedValue(makeDay({ lessons: [] })),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '6А');

    const { findAllByText, getByText } = render(Variants, {
      props: { client, selection, today: makeToday() },
    });

    await waitFor(() => expect(client.getDay).toHaveBeenCalled());
    expect((await findAllByText('Русский язык')).length).toBeGreaterThan(0);
    expect(getByText('Показан примерный день')).toBeTruthy();
    expect(
      getByText('В расписании на этот день нет уроков — показан пример для сравнения.'),
    ).toBeTruthy();
  });

  it('falls back to the sample when loading the selected day fails', async () => {
    const client = makeClient({
      getDay: vi.fn().mockRejectedValue(new Error('boom')),
    });
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '6А');

    const { findAllByText, getByText } = render(Variants, {
      props: { client, selection, today: makeToday() },
    });

    await waitFor(() => expect(client.getDay).toHaveBeenCalled());
    expect((await findAllByText('Русский язык')).length).toBeGreaterThan(0);
    expect(getByText('Показан примерный день')).toBeTruthy();
  });
});
