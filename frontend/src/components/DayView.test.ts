import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import DayView from './DayView.svelte';
import type { Lesson } from '../lib/api/types';
import { makeDay } from '../test-helpers';

function makeLesson(overrides: Partial<Lesson> = {}): Lesson {
  return {
    num: 1,
    start: '08:00',
    end: '08:45',
    items: [
      {
        subject: 'Математика',
        teacher: 'Иванов',
        room: '101',
        class_name: '5А',
        groups: null,
        is_method_hour: false,
      },
    ],
    has_exchange: false,
    is_cancelled: false,
    ...overrides,
  };
}

describe('DayView', () => {
  it('renders lessons with subject, teacher, room and time', () => {
    const { getByText } = render(DayView, {
      props: { day: makeDay({ lessons: [makeLesson()] }), kind: 'class' },
    });
    expect(getByText('Математика')).toBeTruthy();
    expect(getByText('Иванов')).toBeTruthy();
    expect(getByText('каб. 101')).toBeTruthy();
    expect(getByText('08:00–08:45')).toBeTruthy();
  });

  it('highlights an exchange and shows its status label', () => {
    const day = makeDay({ lessons: [makeLesson({ has_exchange: true })] });
    const { getByText, container } = render(DayView, { props: { day, kind: 'class' } });
    expect(getByText('Замена')).toBeTruthy();
    expect(container.querySelector('.lesson.exchange')).toBeTruthy();
  });

  it('highlights a cancellation and strikes through the subject', () => {
    const day = makeDay({
      lessons: [makeLesson({ is_cancelled: true, has_exchange: true })],
    });
    const { getByText, container } = render(DayView, { props: { day, kind: 'class' } });
    expect(getByText('Отменён')).toBeTruthy();
    expect(container.querySelector('.lesson.cancelled')).toBeTruthy();
    expect(container.querySelector('.lesson.exchange')).toBeNull();
  });

  it('shows the vacation state with no lessons', () => {
    const { getByText } = render(DayView, {
      props: { day: makeDay({ vacation: true }), kind: 'class' },
    });
    expect(getByText('Каникулы')).toBeTruthy();
  });

  it('shows the weekend state', () => {
    const { getByText } = render(DayView, {
      props: { day: makeDay({ weekend: true }), kind: 'class' },
    });
    expect(getByText('Выходной')).toBeTruthy();
  });

  it('shows the no-period state', () => {
    const { getByText } = render(DayView, {
      props: { day: makeDay({ no_period: true }), kind: 'class' },
    });
    expect(getByText('Нет учебного периода')).toBeTruthy();
  });

  it('shows an empty state when the day has no lessons', () => {
    const { getByText } = render(DayView, { props: { day: makeDay(), kind: 'class' } });
    expect(getByText('Занятий нет')).toBeTruthy();
  });

  it('shows the academic period when present', () => {
    const day = makeDay({
      period: { b: '01.09.2026', e: '31.05.2027', name: '01.09.2026 - 31.05.2027' },
    });
    const { getByText } = render(DayView, { props: { day, kind: 'class' } });
    expect(getByText('На период: 01.09.2026 - 31.05.2027')).toBeTruthy();
  });

  it('does not show a period line when the day has none', () => {
    const { container } = render(DayView, { props: { day: makeDay(), kind: 'class' } });
    expect(container.querySelector('.period')).toBeNull();
  });

  it('shows a non-first shift indicator without assuming shift 2', () => {
    const { getByText, container } = render(DayView, {
      props: { day: makeDay({ shift: 6, lessons: [makeLesson()] }), kind: 'class' },
    });
    expect(getByText('Смена 6')).toBeTruthy();
    expect(container.querySelector('.shift')?.getAttribute('data-shift')).toBe('6');
  });

  it('hides the shift indicator for the first shift', () => {
    const { container } = render(DayView, {
      props: { day: makeDay({ shift: 1, lessons: [makeLesson()] }), kind: 'class' },
    });
    expect(container.querySelector('.shift')).toBeNull();
  });

  it('shows group names per lesson item', () => {
    const lesson = makeLesson({
      items: [
        {
          subject: 'Математика',
          teacher: 'Иванов',
          room: '101',
          class_name: '5А',
          groups: 'Группа 1',
          is_method_hour: false,
        },
        {
          subject: 'Биология',
          teacher: 'Петрова',
          room: '202',
          class_name: '5А',
          groups: 'Группа 2',
          is_method_hour: false,
        },
      ],
    });
    const { getByText } = render(DayView, {
      props: { day: makeDay({ lessons: [lesson] }), kind: 'class' },
    });
    expect(getByText('Группа 1')).toBeTruthy();
    expect(getByText('Группа 2')).toBeTruthy();
  });

  it('labels a method hour instead of its raw subject code', () => {
    const lesson = makeLesson({
      items: [
        {
          subject: 'M',
          teacher: 'Иванов',
          room: '101',
          class_name: '5А',
          groups: null,
          is_method_hour: true,
        },
      ],
    });
    const { getByText, queryByText } = render(DayView, {
      props: { day: makeDay({ lessons: [lesson] }), kind: 'class' },
    });
    expect(getByText('Метод. час')).toBeTruthy();
    expect(queryByText('M')).toBeNull();
  });

  it('strikes through a free lesson (no subject)', () => {
    const lesson = makeLesson({ items: [] });
    const { container } = render(DayView, {
      props: { day: makeDay({ lessons: [lesson] }), kind: 'class' },
    });
    expect(container.querySelector('.lesson.free')).toBeTruthy();
  });

  it('does not mark a lesson with a subject as free', () => {
    const { container } = render(DayView, {
      props: { day: makeDay({ lessons: [makeLesson()] }), kind: 'class' },
    });
    expect(container.querySelector('.lesson.free')).toBeNull();
  });
});
