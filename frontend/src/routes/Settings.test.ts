import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent, waitFor } from '@testing-library/svelte';
import Settings from './Settings.svelte';
import { makeSelection, makeSettings } from '../test-helpers';

describe('Settings screen', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-skin');
    document.documentElement.removeAttribute('data-accent');
    document.documentElement.removeAttribute('data-font');
  });

  it('renders the appearance controls', () => {
    const { getByRole } = render(Settings, { props: { settings: makeSettings() } });
    expect(getByRole('radio', { name: 'Классика' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Минимализм' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Тёмная' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Контрастная' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Молодёжный' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Синий' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Зелёный' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Фиолетовый' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Обычный' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Крупный' })).toBeTruthy();
  });

  it('persists a skin choice and applies it to <html>', async () => {
    const settings = makeSettings();
    const { getByRole } = render(Settings, { props: { settings } });

    await fireEvent.click(getByRole('radio', { name: 'Тёмная' }));

    expect(settings.skin).toBe('dark');
    await waitFor(() => expect(document.documentElement.getAttribute('data-skin')).toBe('dark'));
  });

  it('persists the «Молодёжный» skin and applies it to <html>', async () => {
    const settings = makeSettings();
    const { getByRole } = render(Settings, { props: { settings } });

    await fireEvent.click(getByRole('radio', { name: 'Молодёжный' }));

    expect(settings.skin).toBe('youth');
    await waitFor(() => expect(document.documentElement.getAttribute('data-skin')).toBe('youth'));
  });

  it('persists accent and font choices', async () => {
    const settings = makeSettings();
    const { getByRole } = render(Settings, { props: { settings } });

    await fireEvent.click(getByRole('radio', { name: 'Фиолетовый' }));
    await fireEvent.click(getByRole('radio', { name: 'Крупный' }));

    expect(settings.accent).toBe('purple');
    expect(settings.fontSize).toBe('large');
    expect(document.documentElement.getAttribute('data-accent')).toBe('purple');
    expect(document.documentElement.getAttribute('data-font')).toBe('large');
  });

  it('persists the default section', async () => {
    const settings = makeSettings();
    const { getByRole } = render(Settings, { props: { settings } });

    await fireEvent.click(getByRole('radio', { name: 'Учителя' }));
    expect(settings.defaultKind).toBe('teacher');
  });

  it('reflects the school strike-through flag and stores an explicit override', async () => {
    const settings = makeSettings();
    const { getByRole } = render(Settings, {
      props: { settings, schoolStrikeoutFreeLsn: false },
    });

    const toggle = getByRole('checkbox', {
      name: 'Зачёркивать свободные уроки',
    }) as HTMLInputElement;
    // No user override yet: the checkbox mirrors the school flag.
    expect(toggle.checked).toBe(false);
    expect(settings.strikeoutFreeLsn).toBeNull();

    await fireEvent.click(toggle);
    expect(settings.strikeoutFreeLsn).toBe(true);
  });

  it('toggles whether lesson numbers/times are shown', async () => {
    const settings = makeSettings();
    const { getByRole } = render(Settings, { props: { settings } });

    const toggle = getByRole('checkbox', {
      name: 'Показывать номер урока и время',
    }) as HTMLInputElement;
    expect(toggle.checked).toBe(true);

    await fireEvent.click(toggle);
    expect(settings.showLessonTime).toBe(false);
  });

  it('offers the four schedule views and persists the choice', async () => {
    const settings = makeSettings();
    const { getByRole } = render(Settings, { props: { settings } });

    expect(getByRole('radio', { name: 'Карточки' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Таблица' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Таймлайн' })).toBeTruthy();
    expect(getByRole('radio', { name: 'Сейчас и далее' })).toBeTruthy();
    expect(settings.scheduleView).toBe('cards');

    await fireEvent.click(getByRole('radio', { name: 'Таймлайн' }));
    expect(settings.scheduleView).toBe('timeline');
  });

  it('enables push for the saved class with the share URL', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const pushEnable = vi.fn().mockResolvedValue({ ok: true, state: 'subscribed' });

    const { getByRole, findByText } = render(Settings, {
      props: {
        settings: makeSettings(),
        selection,
        origin: 'https://rasp.example.ru',
        pushEnable,
        pushDisable: vi.fn(),
        pushSupported: true,
      },
    });

    await fireEvent.click(getByRole('button', { name: 'Включить уведомления' }));

    await waitFor(() =>
      expect(pushEnable).toHaveBeenCalledWith({
        schoolId: 'gym1',
        name: '5А',
        kind: 'class',
        url: 'https://rasp.example.ru/s/gym1/class/5%D0%90',
        quiet: true,
      }),
    );
    expect(await findByText('Выключить уведомления')).toBeTruthy();
  });

  it('shows «не беспокоить ночью» on by default and persists the toggle', async () => {
    const settings = makeSettings();
    const { getByRole } = render(Settings, {
      props: { settings, pushSupported: true },
    });

    const toggle = getByRole('checkbox', {
      name: /Не беспокоить ночью/,
    }) as HTMLInputElement;
    expect(toggle.checked).toBe(true);

    await fireEvent.click(toggle);
    expect(settings.pushQuietHours).toBe(false);
  });

  it('re-upserts the subscription with the new quiet value when push is on', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const pushEnable = vi.fn().mockResolvedValue({ ok: true, state: 'subscribed' });

    const { getByRole } = render(Settings, {
      props: {
        settings: makeSettings(),
        selection,
        origin: 'https://rasp.example.ru',
        pushEnable,
        pushDisable: vi.fn(),
        pushSupported: true,
        pushInitiallyOn: true,
      },
    });

    const toggle = getByRole('checkbox', {
      name: /Не беспокоить ночью/,
    }) as HTMLInputElement;
    expect(toggle.checked).toBe(true);

    await fireEvent.click(toggle);
    await waitFor(() =>
      expect(pushEnable).toHaveBeenCalledWith({
        schoolId: 'gym1',
        name: '5А',
        kind: 'class',
        url: 'https://rasp.example.ru/s/gym1/class/5%D0%90',
        quiet: false,
      }),
    );
  });

  it('only persists «не беспокоить ночью» when push is off', async () => {
    const settings = makeSettings();
    const pushEnable = vi.fn();
    const { getByRole } = render(Settings, {
      props: { settings, pushEnable, pushSupported: true },
    });

    const toggle = getByRole('checkbox', {
      name: /Не беспокоить ночью/,
    }) as HTMLInputElement;
    await fireEvent.click(toggle);

    expect(settings.pushQuietHours).toBe(false);
    expect(pushEnable).not.toHaveBeenCalled();
  });

  it('passes the current quiet value when enabling push', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const settings = makeSettings();
    settings.setPushQuietHours(false);
    const pushEnable = vi.fn().mockResolvedValue({ ok: true, state: 'subscribed' });

    const { getByRole } = render(Settings, {
      props: {
        settings,
        selection,
        origin: 'https://rasp.example.ru',
        pushEnable,
        pushDisable: vi.fn(),
        pushSupported: true,
      },
    });

    await fireEvent.click(getByRole('button', { name: 'Включить уведомления' }));

    await waitFor(() =>
      expect(pushEnable).toHaveBeenCalledWith({
        schoolId: 'gym1',
        name: '5А',
        kind: 'class',
        url: 'https://rasp.example.ru/s/gym1/class/5%D0%90',
        quiet: false,
      }),
    );
  });

  it('disables push through the injected handler', async () => {
    const selection = makeSelection();
    selection.selectSchool('gym1');
    selection.selectEntity('class', '5А');
    const pushDisable = vi.fn().mockResolvedValue({ ok: true, state: 'subscribed' });

    const { getByRole } = render(Settings, {
      props: {
        settings: makeSettings(),
        selection,
        pushEnable: vi.fn(),
        pushDisable,
        pushInitiallyOn: true,
        pushSupported: true,
      },
    });

    await fireEvent.click(getByRole('button', { name: 'Выключить уведомления' }));
    await waitFor(() => expect(pushDisable).toHaveBeenCalled());
  });

  it('shows a muted notice when push is unsupported', () => {
    const { getByText } = render(Settings, {
      props: { settings: makeSettings(), pushSupported: false },
    });
    expect(getByText('Уведомления недоступны')).toBeTruthy();
  });

  it('opens the schedule variants comparison from the «Прочее» section', async () => {
    const onOpenVariants = vi.fn();
    const { getByRole } = render(Settings, {
      props: { settings: makeSettings(), onOpenVariants },
    });

    await fireEvent.click(getByRole('button', { name: 'Показать варианты расписания' }));
    expect(onOpenVariants).toHaveBeenCalled();
  });

  it('resets settings and clears the schedule cache', async () => {
    const settings = makeSettings();
    settings.setSkin('dark');
    const clearCache = vi.fn().mockResolvedValue(undefined);

    const { getByRole, findByText } = render(Settings, {
      props: { settings, clearCache },
    });

    await fireEvent.click(getByRole('button', { name: 'Сбросить настройки' }));
    expect(settings.skin).toBe('classic');
    expect(await findByText('Настройки сброшены')).toBeTruthy();

    await fireEvent.click(getByRole('button', { name: 'Очистить кэш расписания' }));
    await waitFor(() => expect(clearCache).toHaveBeenCalled());
    expect(await findByText('Кэш расписания очищен')).toBeTruthy();
  });
});
