import { describe, it, expect, vi } from 'vitest';
import { render, fireEvent } from '@testing-library/svelte';
import FavoriteButton from './FavoriteButton.svelte';

describe('FavoriteButton', () => {
  it('shows an inactive state and toggles on click', async () => {
    const onToggle = vi.fn();
    const { getByRole } = render(FavoriteButton, { props: { active: false, onToggle } });

    const button = getByRole('button');
    expect(button.getAttribute('aria-pressed')).toBe('false');
    expect(button.textContent).toContain('В избранное');

    await fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('shows an active state', () => {
    const { getByRole } = render(FavoriteButton, { props: { active: true, onToggle: () => {} } });
    const button = getByRole('button');
    expect(button.getAttribute('aria-pressed')).toBe('true');
    expect(button.textContent).toContain('В избранном');
  });

  it('names the entity in the accessible label when provided', () => {
    const { getByRole } = render(FavoriteButton, {
      props: { active: false, onToggle: () => {}, label: '5А' },
    });
    expect(getByRole('button', { name: /5А/ })).toBeTruthy();
  });
});
