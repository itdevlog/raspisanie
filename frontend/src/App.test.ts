import { describe, it, expect, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import App from './App.svelte';
import { makeClient, makeSelection, makeToday } from './test-helpers';

describe('App shell', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders the home screen with navigation by default', async () => {
    const { getByRole, findByText } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday() },
    });
    expect(getByRole('navigation', { name: 'Разделы' })).toBeTruthy();
    expect(getByRole('button', { name: 'Главная' })).toBeTruthy();
    expect(await findByText('Гимназия №1')).toBeTruthy();
  });

  it('switches to the schedule screen', async () => {
    const { getByRole, findByText } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday() },
    });
    await waitFor(() => expect(getByRole('button', { name: 'Расписание' })).toBeTruthy());

    await fireEvent.click(getByRole('button', { name: 'Расписание' }));

    expect(await findByText('Школа не выбрана')).toBeTruthy();
  });

  it('switches to the search & free-rooms screen', async () => {
    const { getByRole, findByText } = render(App, {
      props: { client: makeClient(), selection: makeSelection(), today: makeToday() },
    });
    await waitFor(() => expect(getByRole('button', { name: 'Поиск' })).toBeTruthy());

    await fireEvent.click(getByRole('button', { name: 'Поиск' }));

    expect(await findByText('Поиск и кабинеты')).toBeTruthy();
  });
});
