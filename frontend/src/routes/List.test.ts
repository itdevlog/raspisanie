import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import List from './List.svelte';
import { makeClient, makeFavorites, makeSelection } from '../test-helpers';

describe('List screen (per-kind rows)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders one full-width row per name and opens a schedule', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const onOpenEntity = vi.fn();
    const client = makeClient({
      getClasses: vi.fn().mockResolvedValue({ classes: ['5А', '6Б'] }),
    });

    const { findByRole } = render(List, {
      props: { client, selection, favorites: makeFavorites(), onOpenEntity },
    });

    expect(await findByRole('heading', { name: 'Классы' })).toBeTruthy();
    await fireEvent.click(await findByRole('button', { name: '6Б' }));
    expect(onOpenEntity).toHaveBeenCalledWith('class', '6Б');
  });

  it('filters the list case-insensitively', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectKind('teacher');
    const client = makeClient({
      getTeachers: vi.fn().mockResolvedValue({ teachers: ['Иванов И.И.', 'Петров П.П.'] }),
    });

    const { findByRole, queryByRole } = render(List, {
      props: { client, selection, favorites: makeFavorites() },
    });

    await waitFor(() => expect(client.getTeachers).toHaveBeenCalledWith('gym1'));
    const input = await findByRole('searchbox', { name: 'Поиск' });
    expect(await findByRole('button', { name: 'Петров П.П.' })).toBeTruthy();

    await fireEvent.input(input, { target: { value: 'петров' } });
    await waitFor(() => expect(queryByRole('button', { name: 'Иванов И.И.' })).toBeNull());
  });

  it('shows the active kind favorites first and removes them', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const favorites = makeFavorites();
    favorites.add('gym1', 'class', '7В');
    favorites.add('gym1', 'teacher', 'Сидоров С.С.');
    const onOpenEntity = vi.fn();

    const { findByRole, findByText, queryByText } = render(List, {
      props: { client: makeClient(), selection, favorites, onOpenEntity },
    });

    expect(await findByText('Избранное')).toBeTruthy();
    expect(await findByText('7В')).toBeTruthy();
    // Other kinds' favorites are not shown in the «Классы» list.
    expect(queryByText('Сидоров С.С.')).toBeNull();

    await fireEvent.click(await findByRole('button', { name: '7В' }));
    expect(onOpenEntity).toHaveBeenCalledWith('class', '7В');

    await fireEvent.click(await findByRole('button', { name: 'Удалить из избранного: 7В' }));
    expect(favorites.has('gym1', 'class', '7В')).toBe(false);
  });

  it('shows the free-rooms shortcut only for the rooms kind', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const client = makeClient({
      getRooms: vi.fn().mockResolvedValue({ rooms: ['101', '202'] }),
    });

    const { findByRole, queryByRole } = render(List, {
      props: { client, selection, favorites: makeFavorites() },
    });

    expect(await findByRole('button', { name: '5А' })).toBeTruthy();
    expect(queryByRole('button', { name: 'Свободные кабинеты' })).toBeNull();

    selection.selectKind('room');
    await waitFor(() => expect(client.getRooms).toHaveBeenCalledWith('gym1'));
    expect(await findByRole('button', { name: '101' })).toBeTruthy();
    expect(await findByRole('button', { name: 'Свободные кабинеты' })).toBeTruthy();
  });

  it('surfaces deliberate error and empty states', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const client = makeClient({
      getClasses: vi.fn().mockRejectedValue(new Error('нет классов')),
    });

    const { findByText } = render(List, {
      props: { client, selection, favorites: makeFavorites() },
    });

    expect(await findByText('Ошибка загрузки классов')).toBeTruthy();
    expect(await findByText('нет классов')).toBeTruthy();
  });

  it('shows an empty state when the kind has no names', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectKind('teacher');
    const client = makeClient({
      getTeachers: vi.fn().mockResolvedValue({ teachers: [] }),
    });

    const { findByText } = render(List, {
      props: { client, selection, favorites: makeFavorites() },
    });

    expect(await findByText('Учителя не найдены')).toBeTruthy();
  });

  it('switches the active kind through the compact switcher', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const onKindChange = vi.fn();

    const { getByRole } = render(List, {
      props: { client: makeClient(), selection, favorites: makeFavorites(), onKindChange },
    });

    await fireEvent.click(getByRole('tab', { name: 'Учителя' }));
    expect(onKindChange).toHaveBeenCalledWith('teacher');
  });

  it('offers a back link to the landing', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    const onBack = vi.fn();

    const { findByRole } = render(List, {
      props: { client: makeClient(), selection, favorites: makeFavorites(), onBack },
    });

    await fireEvent.click(await findByRole('button', { name: 'На главную' }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
