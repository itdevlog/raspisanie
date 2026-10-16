import { describe, it, expect } from 'vitest';
import { render, within } from '@testing-library/svelte';
import ScheduleNowNext from './ScheduleNowNext.svelte';
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

describe('ScheduleNowNext', () => {
  it('renders both groups of a split hero lesson, each with its own teacher and room', () => {
    const hero = makeLesson({
      num: 1,
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

    const { container } = render(ScheduleNowNext, {
      props: { lessons: [hero], kind: 'class' },
    });

    const heroCard = container.querySelector('.hero') as HTMLElement;
    expect(heroCard).toBeTruthy();
    expect(within(heroCard).getByText('301')).toBeTruthy();
    expect(within(heroCard).getByText('405')).toBeTruthy();
    expect(within(heroCard).getByText('Петрова А.В.')).toBeTruthy();
    expect(within(heroCard).getByText('Синицына Н.П.')).toBeTruthy();
    expect(within(heroCard).getByText('Группа 1')).toBeTruthy();
    expect(within(heroCard).getByText('Группа 2')).toBeTruthy();
  });

  it('renders both groups of a split rest-list lesson, each with its own teacher and room', () => {
    const hero = makeLesson({
      num: 1,
      items: [makeItem({ subject: 'Русский язык', room: '204' })],
    });
    const rest = makeLesson({
      num: 2,
      start: '08:55',
      end: '09:40',
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

    const { container } = render(ScheduleNowNext, {
      props: { lessons: [hero, rest], kind: 'class' },
    });

    const restRow = container.querySelector('.rest-item') as HTMLElement;
    expect(restRow).toBeTruthy();
    expect(within(restRow).getByText('301')).toBeTruthy();
    expect(within(restRow).getByText('405')).toBeTruthy();
    expect(within(restRow).getByText('Петрова А.В.')).toBeTruthy();
    expect(within(restRow).getByText('Синицына Н.П.')).toBeTruthy();
  });

  it('keeps the placeholder item for an item-less lesson', () => {
    const lesson = makeLesson({ num: 1, items: [] });

    const { container } = render(ScheduleNowNext, {
      props: { lessons: [lesson], kind: 'class' },
    });

    const heroCard = container.querySelector('.hero') as HTMLElement;
    expect(heroCard).toBeTruthy();
    expect(heroCard.querySelector('.subject')?.textContent?.trim()).toBe('—');
  });
});
