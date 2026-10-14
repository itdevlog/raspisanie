import { describe, it, expect } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import ExchangeBadge from './ExchangeBadge.svelte';
import type { Lesson, LessonExchange } from '../lib/api/types';

function makeLesson(overrides: Partial<Lesson> = {}): Lesson {
  return {
    num: 1,
    start: '08:00',
    end: '08:45',
    items: [
      {
        subject: 'Биология',
        teacher: 'Петрова',
        room: '202',
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

function makeExchange(overrides: Partial<LessonExchange> = {}): LessonExchange {
  return {
    original_subject: 'Математика',
    original_teacher: 'Иванов',
    original_room: '101',
    new_subject: 'Биология',
    new_teacher: 'Петрова',
    new_room: '202',
    is_cancelled: false,
    ...overrides,
  };
}

describe('ExchangeBadge', () => {
  it('renders nothing for a normal lesson', () => {
    const { container, queryByRole } = render(ExchangeBadge, {
      props: { lesson: makeLesson() },
    });
    expect(container.textContent?.trim()).toBe('');
    expect(queryByRole('button')).toBeNull();
  });

  it('opens a «было → стало» popover when the «Замена» badge is tapped', async () => {
    const lesson = makeLesson({ has_exchange: true, exchange: makeExchange() });
    const { getByRole, findByText, queryByText } = render(ExchangeBadge, { props: { lesson } });

    const badge = getByRole('button', { name: 'Замена' });
    expect(badge.getAttribute('aria-expanded')).toBe('false');
    // Nothing is shown until the badge is tapped.
    expect(queryByText('Математика')).toBeNull();

    await fireEvent.click(badge);

    expect(badge.getAttribute('aria-expanded')).toBe('true');
    expect(await findByText('Математика')).toBeTruthy(); // было
    expect(await findByText('Биология')).toBeTruthy(); // стало
    expect(await findByText('Иванов')).toBeTruthy();
    expect(await findByText('Петрова')).toBeTruthy();
    expect(await findByText('101')).toBeTruthy();
    expect(await findByText('202')).toBeTruthy();
  });

  it('omits a field that did not change (partial exchange)', async () => {
    const lesson = makeLesson({
      has_exchange: true,
      exchange: makeExchange({ new_room: '101' }),
    });
    const { getByRole, findByText, queryByText } = render(ExchangeBadge, { props: { lesson } });

    await fireEvent.click(getByRole('button', { name: 'Замена' }));
    expect(await findByText('Петрова')).toBeTruthy();
    // Room unchanged (101 → 101): no room row is rendered.
    expect(queryByText('Кабинет')).toBeNull();
  });

  it('closes the popover on a second tap of the badge', async () => {
    const lesson = makeLesson({ has_exchange: true, exchange: makeExchange() });
    const { getByRole, findByText, queryByText } = render(ExchangeBadge, { props: { lesson } });
    const badge = getByRole('button', { name: 'Замена' });

    await fireEvent.click(badge);
    expect(await findByText('Математика')).toBeTruthy();

    await fireEvent.click(badge);
    await waitFor(() => expect(queryByText('Математика')).toBeNull());
  });

  it('shows a clear note for a cancelled lesson', async () => {
    const lesson = makeLesson({
      is_cancelled: true,
      exchange: makeExchange({
        is_cancelled: true,
        new_subject: null,
        new_teacher: null,
        new_room: null,
      }),
    });
    const { getByRole, findByText } = render(ExchangeBadge, { props: { lesson } });

    await fireEvent.click(getByRole('button', { name: 'Отменён' }));
    expect(await findByText('Урок отменён')).toBeTruthy();
  });

  it('degrades gracefully without opening when the lesson has no exchange data', async () => {
    const lesson = makeLesson({ has_exchange: true });
    const { getByText, queryByRole } = render(ExchangeBadge, { props: { lesson } });

    expect(getByText('Замена')).toBeTruthy();
    // Just the label — nothing interactive, no popover.
    expect(queryByRole('button')).toBeNull();
    expect(queryByRole('dialog')).toBeNull();
  });

  it('closes the popover on Escape', async () => {
    const lesson = makeLesson({ has_exchange: true, exchange: makeExchange() });
    const { getByRole, findByText, queryByText } = render(ExchangeBadge, { props: { lesson } });

    await fireEvent.click(getByRole('button', { name: 'Замена' }));
    expect(await findByText('Математика')).toBeTruthy();

    await fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => expect(queryByText('Математика')).toBeNull());
  });

  it('closes the popover on an outside click', async () => {
    const lesson = makeLesson({ has_exchange: true, exchange: makeExchange() });
    const { getByRole, findByText, queryByText } = render(ExchangeBadge, { props: { lesson } });

    await fireEvent.click(getByRole('button', { name: 'Замена' }));
    expect(await findByText('Математика')).toBeTruthy();

    await fireEvent.click(document.body);
    await waitFor(() => expect(queryByText('Математика')).toBeNull());
  });

  it('closes the popover through its close button', async () => {
    const lesson = makeLesson({ has_exchange: true, exchange: makeExchange() });
    const { getByRole, findByText, queryByText } = render(ExchangeBadge, { props: { lesson } });

    await fireEvent.click(getByRole('button', { name: 'Замена' }));
    expect(await findByText('Математика')).toBeTruthy();

    await fireEvent.click(getByRole('button', { name: 'Закрыть' }));
    await waitFor(() => expect(queryByText('Математика')).toBeNull());
  });
});
