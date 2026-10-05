import { describe, it, expect, vi } from 'vitest';
import { createRouteStore } from './route.svelte';
import { makeFakeEnv } from '../../test-helpers';

describe('route store', () => {
  it('parses the initial deep link on start()', () => {
    const fake = makeFakeEnv('/s/gym1/class/5%D0%90?date=07.09.2026');
    const store = createRouteStore(fake.env);

    expect(store.started).toBe(false);
    store.start();

    expect(store.route).toEqual({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: '07.09.2026',
    });
    expect(store.started).toBe(true);
  });

  it('opens Home for an unknown route', () => {
    const fake = makeFakeEnv('/nope');
    const store = createRouteStore(fake.env);
    store.start();
    expect(store.route).toEqual({ view: 'home' });
  });

  it('parses a deep link without a date as a schedule route with date=null', () => {
    const fake = makeFakeEnv('/s/gym1/teacher/%D0%98%D0%B2%D0%B0%D0%BD%D0%BE%D0%B2');
    const store = createRouteStore(fake.env);
    store.start();
    expect(store.route).toEqual({
      view: 'schedule',
      school: 'gym1',
      kind: 'teacher',
      name: 'Иванов',
      date: null,
    });
  });

  it('navigate() pushes a history entry and syncs the URL', () => {
    const fake = makeFakeEnv('/');
    const store = createRouteStore(fake.env);
    store.start();

    store.navigate({ view: 'tools' });

    expect(store.route).toEqual({ view: 'tools' });
    expect(fake.location.pathname).toBe('/tools');
  });

  it('navigate({replace}) replaces the current entry', () => {
    const fake = makeFakeEnv('/');
    const store = createRouteStore(fake.env);
    store.start();

    store.navigate({ view: 'tools' }, { replace: true });

    expect(fake.location.pathname).toBe('/tools');
  });

  it('writes a schedule share URL into the address bar', () => {
    const fake = makeFakeEnv('/');
    const store = createRouteStore(fake.env);
    store.start();

    store.navigate({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: '07.09.2026',
    });

    expect(fake.location.pathname).toBe('/s/gym1/class/5%D0%90');
    expect(fake.location.search).toBe('?date=07.09.2026');
  });

  it('back/forward replay history through popstate', () => {
    const fake = makeFakeEnv('/');
    const store = createRouteStore(fake.env);
    store.start();

    store.navigate({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: null,
    });
    store.navigate({ view: 'tools' });

    fake.back();
    expect(store.route).toEqual({
      view: 'schedule',
      school: 'gym1',
      kind: 'class',
      name: '5А',
      date: null,
    });

    fake.back();
    expect(store.route).toEqual({ view: 'home' });

    fake.forward();
    expect(store.route.view).toBe('schedule');
  });

  it('goTo() switches tabs, pressing the active tab is a no-op', () => {
    const fake = makeFakeEnv('/');
    const store = createRouteStore(fake.env);
    store.start();

    store.goTo('tools');
    expect(store.route).toEqual({ view: 'tools' });
    const spy = vi.spyOn(fake.env.history, 'pushState');

    store.goTo('tools');
    expect(spy).not.toHaveBeenCalled();
  });

  it('start() returns an unsubscribe that detaches popstate', () => {
    const fake = makeFakeEnv('/');
    const store = createRouteStore(fake.env);
    const off = store.start();

    store.navigate({ view: 'tools' });
    off();

    fake.back();
    // Listener detached: route stays on the last programmatic value.
    expect(store.route).toEqual({ view: 'tools' });
  });

  it('navigate writes the canonical URL via pushState', () => {
    const fake = makeFakeEnv('/');
    const store = createRouteStore(fake.env);
    const spy = vi.spyOn(fake.env.history, 'pushState');
    store.start();

    store.navigate({ view: 'tools' });
    expect(spy).toHaveBeenCalledWith({}, '', '/tools');
  });
});
