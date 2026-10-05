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
    items: [{ subject: 'Математика', teacher: 'Иванов', room: '101', class_name: '5А' }],
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
});
