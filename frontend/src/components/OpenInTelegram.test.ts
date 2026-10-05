import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/svelte';
import OpenInTelegram from './OpenInTelegram.svelte';

describe('OpenInTelegram', () => {
  it('renders a deep link when the bot is configured', () => {
    const { getByRole } = render(OpenInTelegram, {
      props: {
        bot: 'raspisanie_bot',
        target: { school: 'gym1', kind: 'class', name: '5А', date: '07.09.2026' },
      },
    });
    const link = getByRole('link', { name: 'Открыть в Telegram' }) as HTMLAnchorElement;
    expect(link.getAttribute('href')).toContain('https://t.me/raspisanie_bot?start=');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('hides itself when the bot username is unset', () => {
    const { queryByRole } = render(OpenInTelegram, {
      props: { bot: '', target: { school: 'gym1', kind: 'class', name: '5А' } },
    });
    expect(queryByRole('link')).toBeNull();
  });

  it('hides itself when the target cannot be encoded', () => {
    const { queryByRole } = render(OpenInTelegram, {
      props: { bot: 'raspisanie_bot', target: { school: '', kind: 'class', name: '5А' } },
    });
    expect(queryByRole('link')).toBeNull();
  });
});
