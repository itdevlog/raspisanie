import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import SearchPanel from './SearchPanel.svelte';

describe('SearchPanel', () => {
  it('renders teacher and room results grouped', () => {
    const { getByText, getByRole } = render(SearchPanel, {
      props: {
        teachers: ['Иванов И.И.'],
        rooms: ['101'],
        status: 'ready',
        hasQuery: true,
        onQueryChange: vi.fn(),
        onSelect: vi.fn(),
      },
    });
    expect(getByText('Учителя')).toBeTruthy();
    expect(getByText('Кабинеты')).toBeTruthy();
    expect(getByRole('button', { name: 'Иванов И.И.' })).toBeTruthy();
    expect(getByRole('button', { name: '101' })).toBeTruthy();
  });

  it('renders class results and selects them as a class (W37 fix)', async () => {
    const onSelect = vi.fn();
    const { getByText, getByRole } = render(SearchPanel, {
      props: {
        classes: ['5А'],
        teachers: [],
        rooms: [],
        status: 'ready',
        hasQuery: true,
        onQueryChange: vi.fn(),
        onSelect,
      },
    });
    expect(getByText('Классы')).toBeTruthy();
    await fireEvent.click(getByRole('button', { name: '5А' }));
    expect(onSelect).toHaveBeenCalledWith('class', '5А');
  });

  it('does not show "nothing found" when only classes match', () => {
    const { queryByText, getByText } = render(SearchPanel, {
      props: {
        classes: ['5А'],
        teachers: [],
        rooms: [],
        status: 'ready',
        hasQuery: true,
        onQueryChange: vi.fn(),
        onSelect: vi.fn(),
      },
    });
    expect(queryByText('Ничего не найдено')).toBeNull();
    expect(getByText('5А')).toBeTruthy();
  });

  it('does not render a phantom «Классы» group when there are no class results', () => {
    const { queryByText, getByText } = render(SearchPanel, {
      props: {
        teachers: ['Иванов И.И.'],
        rooms: [],
        status: 'ready',
        hasQuery: true,
        onQueryChange: vi.fn(),
        onSelect: vi.fn(),
      },
    });
    expect(queryByText('Классы')).toBeNull();
    expect(getByText('Учителя')).toBeTruthy();
  });

  it('raises onSelect with the kind and name when a result is clicked', async () => {
    const onSelect = vi.fn();
    const { getByRole } = render(SearchPanel, {
      props: {
        teachers: ['Иванов И.И.'],
        rooms: ['101'],
        status: 'ready',
        hasQuery: true,
        onQueryChange: vi.fn(),
        onSelect,
      },
    });

    await fireEvent.click(getByRole('button', { name: 'Иванов И.И.' }));
    expect(onSelect).toHaveBeenCalledWith('teacher', 'Иванов И.И.');

    await fireEvent.click(getByRole('button', { name: '101' }));
    expect(onSelect).toHaveBeenCalledWith('room', '101');
  });

  it('reports query text changes', async () => {
    const onQueryChange = vi.fn();
    const { getByRole } = render(SearchPanel, {
      props: {
        teachers: [],
        rooms: [],
        status: 'idle',
        hasQuery: false,
        onQueryChange,
        onSelect: vi.fn(),
      },
    });

    await fireEvent.input(getByRole('searchbox'), { target: { value: 'ив' } });
    expect(onQueryChange).toHaveBeenCalledWith('ив');
  });

  it('shows a "nothing found" message only when a query returned no results', () => {
    const { getByText } = render(SearchPanel, {
      props: {
        teachers: [],
        rooms: [],
        status: 'ready',
        hasQuery: true,
        onQueryChange: vi.fn(),
        onSelect: vi.fn(),
      },
    });
    expect(getByText('Ничего не найдено')).toBeTruthy();
  });

  it('shows errors and loading states', () => {
    const { getByText, rerender } = render(SearchPanel, {
      props: {
        teachers: [],
        rooms: [],
        status: 'loading',
        hasQuery: true,
        onQueryChange: vi.fn(),
        onSelect: vi.fn(),
      },
    });
    expect(getByText('Поиск…')).toBeTruthy();

    rerender({ status: 'error', error: 'Сбой сети', hasQuery: true });
    expect(getByText('Сбой сети')).toBeTruthy();
  });
});
