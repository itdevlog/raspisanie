import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import EntityPicker from './EntityPicker.svelte';

describe('EntityPicker', () => {
  it('marks the active kind and lists names', () => {
    const { getByRole, getByText } = render(EntityPicker, {
      props: {
        kind: 'class',
        name: '5А',
        names: ['5А', '6Б'],
        onKindChange: vi.fn(),
        onNameChange: vi.fn(),
      },
    });
    expect(getByRole('tab', { name: 'Класс' }).getAttribute('aria-selected')).toBe('true');
    expect(getByRole('tab', { name: 'Учитель' }).getAttribute('aria-selected')).toBe('false');
    expect(getByText('6Б')).toBeTruthy();
  });

  it('raises onKindChange only when the kind actually changes', async () => {
    const onKindChange = vi.fn();
    const { getByRole } = render(EntityPicker, {
      props: {
        kind: 'class',
        name: null,
        names: [],
        onKindChange,
        onNameChange: vi.fn(),
      },
    });

    await fireEvent.click(getByRole('tab', { name: 'Класс' }));
    expect(onKindChange).not.toHaveBeenCalled();

    await fireEvent.click(getByRole('tab', { name: 'Кабинет' }));
    expect(onKindChange).toHaveBeenCalledWith('room');
  });

  it('raises onNameChange when a name is picked', async () => {
    const onNameChange = vi.fn();
    const { getByRole } = render(EntityPicker, {
      props: {
        kind: 'room',
        name: null,
        names: ['101', '202'],
        onKindChange: vi.fn(),
        onNameChange,
      },
    });

    const select = getByRole('combobox') as HTMLSelectElement;
    await fireEvent.change(select, { target: { value: '202' } });
    expect(onNameChange).toHaveBeenCalledWith('202');
  });
});
