import { describe, it, expect, vi } from 'vitest';
import {
  buildShareUrl,
  shareSchedule,
  shareScheduleFor,
  type ShareNavigator,
} from './share';
import { quoteLikePython } from './route';
import { pythonBuildClassShareUrl } from '../test-helpers';

/**
 * The W16 producer is the source of truth; these cases hit the REAL Python
 * function via {@link pythonBuildClassShareUrl} rather than a JS mirror that
 * could drift (e.g. `encodeURIComponent` leaves `!'()*` literal while Python's
 * `quote(safe='')` encodes them).
 */
describe('buildShareUrl', () => {
  it.each([
    '5А (№1)',
    "5А !'* (№1) — смена",
    '5А / 6Б',
    '10 Б «инженерный»',
    'Иванов И.И.',
  ])('is byte-identical to the real Python build_class_share_url for %j', (name) => {
    const origin = 'https://rasp.example.ru';
    const school = 'school_133';
    const date = '07.09.2026';

    const python = pythonBuildClassShareUrl(origin, school, name, date);
    const frontend = buildShareUrl(origin, school, 'class', name, date);

    // Guard against a vacuous oracle that returned nothing.
    expect(python).toContain('/s/school_133/class/');
    expect(frontend).toBe(python);
  });

  it('encodes the same characters Python quote(safe="") encodes', () => {
    // `encodeURIComponent` leaves these literal; Python percent-encodes them.
    expect(quoteLikePython("!'()*")).toBe('%21%27%28%29%2A');
    expect(quoteLikePython('5А (№1)')).toBe('5%D0%90%20%28%E2%84%961%29');
  });

  it('round-trips through decodeURIComponent', () => {
    for (const name of ['5А (№1)', "5А !'* (№1) — смена", 'Иванов И.И.', '101/102']) {
      expect(decodeURIComponent(quoteLikePython(name))).toBe(name);
    }
  });

  it('strips a trailing slash on the origin and omits the date when null', () => {
    expect(buildShareUrl('https://rasp.example.ru/', 'gym1', 'teacher', 'Иванов И.И.', null)).toBe(
      'https://rasp.example.ru/s/gym1/teacher/%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2%20%D0%98.%D0%98.',
    );
  });

  it('supports an empty origin (root-relative) and a base path', () => {
    expect(buildShareUrl('', 'gym1', 'room', '101', '05.10.2026')).toBe(
      '/s/gym1/room/101?date=05.10.2026',
    );
    expect(buildShareUrl('https://x.ru/', 'gym1', 'room', '101', null, '/app/')).toBe(
      'https://x.ru/app/s/gym1/room/101',
    );
  });
});

describe('shareSchedule', () => {
  it('prefers navigator.share and reports the method', async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    const writeText = vi.fn().mockResolvedValue(undefined);
    const nav: ShareNavigator = { share, clipboard: { writeText } };

    const result = await shareSchedule('https://x.ru/s/a/class/b', { title: 'Расписание' }, nav);

    expect(result).toEqual({ ok: true, method: 'share', url: 'https://x.ru/s/a/class/b' });
    expect(share).toHaveBeenCalledWith({
      title: 'Расписание',
      text: undefined,
      url: 'https://x.ru/s/a/class/b',
    });
    expect(writeText).not.toHaveBeenCalled();
  });

  it('falls back to the clipboard when navigator.share is absent', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const nav: ShareNavigator = { clipboard: { writeText } };

    const result = await shareSchedule('https://x.ru/s/a/class/b', {}, nav);

    expect(result.method).toBe('clipboard');
    expect(writeText).toHaveBeenCalledWith('https://x.ru/s/a/class/b');
  });

  it('falls back to the clipboard when navigator.share rejects', async () => {
    const share = vi.fn().mockRejectedValue(new Error('share failed'));
    const writeText = vi.fn().mockResolvedValue(undefined);
    const nav: ShareNavigator = { share, clipboard: { writeText } };

    const result = await shareSchedule('https://x.ru/u', {}, nav);

    expect(result).toEqual({ ok: true, method: 'clipboard', url: 'https://x.ru/u' });
  });

  it('treats a user-cancelled native share (AbortError) as a no-op', async () => {
    const abort = Object.assign(new Error('cancelled'), { name: 'AbortError' });
    const share = vi.fn().mockRejectedValue(abort);
    const writeText = vi.fn().mockResolvedValue(undefined);
    const nav: ShareNavigator = { share, clipboard: { writeText } };

    const result = await shareSchedule('https://x.ru/u', {}, nav);

    expect(result).toEqual({ ok: true, method: null, url: 'https://x.ru/u' });
    expect(writeText).not.toHaveBeenCalled();
  });

  it('reports failure when neither share nor clipboard is available', async () => {
    const result = await shareSchedule('https://x.ru/u', {}, null);
    expect(result.ok).toBe(false);
    expect(result.method).toBeNull();
    expect(result.error).toBeTruthy();
  });

  it('reports a clipboard write failure', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'));
    const result = await shareSchedule('https://x.ru/u', {}, { clipboard: { writeText } });
    expect(result).toEqual({ ok: false, method: null, url: 'https://x.ru/u', error: 'denied' });
  });
});

describe('shareScheduleFor', () => {
  it('builds the URL from window.location.origin and shares it', async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    const result = await shareScheduleFor(
      { location: { origin: 'https://rasp.example.ru' } },
      { share },
      'gym1',
      'class',
      '5А',
      '05.10.2026',
    );

    expect(result.url).toBe(
      pythonBuildClassShareUrl(
        'https://rasp.example.ru',
        'gym1',
        '5А',
        '05.10.2026',
      ),
    );
    expect(share).toHaveBeenCalledWith(
      expect.objectContaining({ url: result.url, text: '5А' }),
    );
  });
});
