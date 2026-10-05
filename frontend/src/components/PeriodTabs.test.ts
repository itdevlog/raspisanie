import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import PeriodTabs from './PeriodTabs.svelte';

describe('PeriodTabs', () => {
  it('renders today/tomorrow/week and marks the active one', () => {
    const { getByRole } = render(PeriodTabs, { props: { value: 'tomorrow', onChange: vi.fn() } });
    expect(getByRole('tab', { name: 'Сегодня' })).toBeTruthy();
    expect(getByRole('tab', { name: 'Завтра' }).getAttribute('aria-selected')).toBe('true');
    expect(getByRole('tab', { name: 'Неделя' })).toBeTruthy();
  });

  it('emits the chosen period', async () => {
    const onChange = vi.fn();
    const { getByRole } = render(PeriodTabs, { props: { value: 'today', onChange } });
    await fireEvent.click(getByRole('tab', { name: 'Неделя' }));
    expect(onChange).toHaveBeenCalledWith('week');
  });
});
