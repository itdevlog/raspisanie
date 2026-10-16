import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import ScheduleTable from './ScheduleTable.svelte';
import type { Lesson, LessonItem } from '../../lib/api/types';

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

function headers(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll('thead th')).map((th) =>
    (th.textContent ?? '').trim(),
  );
}

describe('ScheduleTable', () => {
  it('renders three columns: merged number/time, subject and room (no teacher column)', () => {
    const { container } = render(ScheduleTable, {
      props: { lessons: [makeLesson()], kind: 'class' },
    });

    expect(headers(container)).toEqual(['№ Время', 'Предмет', 'Кабинет']);
    expect(headers(container)).not.toContain('Учитель');
  });

  it('merges the number/time cell across a split lesson and nests the teacher under the subject', () => {
    const lesson = makeLesson({
      num: 3,
      start: '09:50',
      end: '10:35',
      items: [
        makeItem({
          subject: 'Английский язык',
          teacher: 'Петрова А.В.',
          room: '301',
          groups: 'Группа 1',
        }),
        makeItem({
          subject: 'Немецкий язык',
          teacher: 'Синицына Н.П.',
          room: '405',
          groups: 'Группа 2',
        }),
      ],
    });

    const { container } = render(ScheduleTable, {
      props: { lessons: [lesson], kind: 'class' },
    });

    const rows = container.querySelectorAll('tbody tr');
    expect(rows).toHaveLength(2);

    // One shared number/time cell on the first row, spanning both items.
    expect(rows[0].querySelector('td.num-time')?.getAttribute('rowspan')).toBe('2');
    expect(rows[1].querySelector('td.num-time')).toBeNull();

    // Each item keeps its own teacher and room.
    const firstCells = rows[0].querySelectorAll('td');
    const secondCells = rows[1].querySelectorAll('td');
    expect(firstCells[1].textContent).toContain('Английский язык');
    expect(firstCells[1].textContent).toContain('Петрова А.В.');
    expect(firstCells[2].textContent).toContain('301');
    expect(secondCells[0].textContent).toContain('Немецкий язык');
    expect(secondCells[0].textContent).toContain('Синицына Н.П.');
    expect(secondCells[1].textContent).toContain('405');
  });

  it('drops the room column for room-kind schedules', () => {
    const { container } = render(ScheduleTable, {
      props: { lessons: [makeLesson()], kind: 'room' },
    });

    expect(headers(container)).toEqual(['№ Время', 'Предмет']);
  });

  it('hides the time inside the merged cell when showLessonTime is false', () => {
    const { container, queryByText } = render(ScheduleTable, {
      props: { lessons: [makeLesson()], kind: 'class', showLessonTime: false },
    });

    expect(queryByText('08:00–08:45')).toBeNull();
    expect(container.querySelector('td.num-time .num')?.textContent?.trim()).toBe('1');
  });

  it('keeps the is-now highlight and eyebrow on the shared lesson rows', () => {
    const { container } = render(ScheduleTable, {
      props: {
        lessons: [makeLesson({ num: 2 })],
        kind: 'class',
        heroNum: 2,
        heroIsCurrent: true,
      },
    });

    const nowRow = container.querySelector('tr.is-now');
    expect(nowRow).toBeTruthy();
    expect(nowRow?.querySelector('.now-eyebrow')?.textContent).toBe('Сейчас');
  });
});
