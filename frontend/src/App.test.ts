import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import App from './App.svelte';

describe('App', () => {
  it('renders the placeholder app shell', () => {
    const { getByText } = render(App);
    expect(getByText('Расписание')).toBeTruthy();
    expect(getByText('Загрузка…')).toBeTruthy();
  });
});
