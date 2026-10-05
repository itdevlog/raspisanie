import { describe, it, expect } from 'vitest';
import {
  HOME_ROUTE,
  buildSharePath,
  buildViewPath,
  isScheduleKind,
  parseLocation,
  parsePath,
  type Route,
} from './route';

/**
 * Round-trip against W16's producer.
 *
 * `core/background_updater.py::build_class_share_url` builds exactly:
 *   f"{base}/s/{quote(school, safe='')}/class/{quote(name, safe='')}?date={dd.mm.YYYY}"
 * `quote(x, safe='')` is percent-encoding equivalent to `encodeURIComponent`,
 * so mirroring it here proves the parser/builder agree with push notifications.
 */
function w16BuildClassSharePath(school: string, name: string, date: string): string {
  const quote = (value: string) => encodeURIComponent(value);
  return `/s/${quote(school)}/class/${quote(name)}?date=${date}`;
}

describe('route parsing (W16 round-trip)', () => {
  it('parses a URL built the way W16 builds it, with Cyrillic and № in the name', () => {
    const school = 'school_133';
    const name = '5А (№1) — смена';
    const date = '07.09.2026';
    const path = w16BuildClassSharePath(school, name, date);

    // The producer percent-encodes the name.
    expect(path).toContain('%D0%90');
    expect(parsePath(path)).toEqual({
      view: 'schedule',
      school,
      kind: 'class',
      name,
      date,
    });
  });

  it('round-trips buildSharePath → parsePath for every kind and tricky names', () => {
    const cases: Array<{ school: string; kind: 'class' | 'teacher' | 'room'; name: string }> = [
      { school: 'gym1', kind: 'class', name: '5А' },
      { school: 'school_133', kind: 'teacher', name: 'Иванов И.И.' },
      { school: 'school_133', kind: 'room', name: 'Кабинет №12' },
      { school: 's p a c e', kind: 'class', name: '10 Б «инженерный»' },
      { school: 'a/b?c#d', kind: 'room', name: '101/102' },
    ];
    for (const { school, kind, name } of cases) {
      const path = buildSharePath(school, kind, name, '05.10.2026');
      expect(parsePath(path)).toEqual({ view: 'schedule', school, kind, name, date: '05.10.2026' });
    }
  });

  it('accepts the W16 path shape when given as a full URL / Location', () => {
    const path = w16BuildClassSharePath('gym1', '5А', '07.09.2026');
    expect(parseLocation(`https://rasp.example.ru${path}`)).toEqual({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: '07.09.2026',
    });
    expect(parseLocation({ pathname: '/s/gym1/class/5%D0%90', search: '?date=07.09.2026' })).toEqual({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: '07.09.2026',
    });
  });

  it('handles a share link without a date (server today is used later)', () => {
    expect(parsePath('/s/gym1/class/5%D0%90')).toEqual({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: null,
    });
  });

  it('ignores an invalid date rather than failing the whole route', () => {
    expect(parsePath('/s/gym1/class/5%D0%90?date=2026-09-07')).toEqual({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: null,
    });
    expect(parsePath('/s/gym1/class/5%D0%90?date=31.02.2026')).toEqual({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: null,
    });
  });

  it('tolerates a malformed percent-encoded name (no throw)', () => {
    expect(parsePath('/s/gym1/class/100%')).toEqual({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '100%',
      date: null,
    });
  });

  it('keeps a percent-encoded slash inside one name segment', () => {
    // W16 encodes `/` as %2F, so it must stay part of the name, not split paths.
    const path = buildSharePath('gym1', 'class', '101/102');
    expect(path).toBe('/s/gym1/class/101%2F102');
    expect(parsePath(path)).toEqual({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '101/102',
      date: null,
    });
  });
});

describe('route parsing (unknown / absent → Home)', () => {
  it.each([
    '/',
    '',
    '/unknown',
    '/s',
    '/s/gym1',
    '/s/gym1/class',
    '/s/gym1/class/5А/extra',
    '/s/gym1/magic/5А',
    '/s//class/5А',
    '/s/gym1/class/',
    '/not/a/schedule/path',
  ])('maps %j to Home', (path) => {
    expect(parsePath(path)).toEqual(HOME_ROUTE);
  });

  it('recognizes the tools and bare schedule views', () => {
    expect(parsePath('/tools')).toEqual({ view: 'tools' });
    expect(parsePath('/tools/')).toEqual({ view: 'tools' });
    // Bare schedule view (nav tab without a chosen entity).
    expect(parsePath('/schedule')).toEqual({
      view: 'schedule',
      school: null,
      kind: 'class',
      name: null,
      date: null,
    });
    expect(parsePath('/nope')).toEqual(HOME_ROUTE);
  });

  it('validates kinds', () => {
    expect(isScheduleKind('class')).toBe(true);
    expect(isScheduleKind('teacher')).toBe(true);
    expect(isScheduleKind('room')).toBe(true);
    expect(isScheduleKind('CLASS')).toBe(false);
    expect(isScheduleKind('other')).toBe(false);
  });
});

describe('buildViewPath / buildSharePath', () => {
  it('builds in-app paths for each view', () => {
    expect(buildViewPath({ view: 'home' })).toBe('/');
    expect(buildViewPath({ view: 'tools' })).toBe('/tools');
    const schedule: Route = {
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: '07.09.2026',
    };
    expect(buildViewPath(schedule)).toBe('/s/gym1/class/5%D0%90?date=07.09.2026');
  });

  it('omits the date when none is pinned', () => {
    expect(buildSharePath('gym1', 'teacher', 'Иванов И.И.')).toBe(
      '/s/gym1/teacher/%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2%20%D0%98.%D0%98.',
    );
  });

  it('encodes the date segment too', () => {
    expect(buildSharePath('gym1', 'class', '5А', '05.10.2026')).toBe(
      '/s/gym1/class/5%D0%90?date=05.10.2026',
    );
  });
});
