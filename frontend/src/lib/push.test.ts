import { describe, it, expect, vi } from 'vitest';
import {
  buildPushRequest,
  buildSubscribeBody,
  disablePush,
  enablePush,
  fetchVapidPublicKey,
  getPermission,
  hasSubscription,
  isPushSupported,
  urlBase64ToUint8Array,
  type NotificationLike,
  type PushDeps,
  type PushManagerLike,
  type PushNavigator,
  type PushSubscriptionLike,
  type PushWindow,
  type ServiceWorkerRegistrationLike,
} from './push';

/**
 * These tests pin the browser→edge contract against `web/edge_push.py`:
 *   * the VAPID read expects `{key}`;
 *   * subscribe/unsubscribe POST a JSON body with NO `X-Edge-Auth` header (the
 *     edge injects the secret server-side, `web/edge_push.py` line ~121).
 */

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function makeSubscription(overrides: Partial<PushSubscriptionLike> = {}): PushSubscriptionLike {
  return {
    endpoint: 'https://fcm.example/ep',
    toJSON: () => ({
      keys: { p256dh: 'p256dh-value', auth: 'auth-value' },
    }),
    ...overrides,
  };
}

function makePushManager(subscription: PushSubscriptionLike | null = null): PushManagerLike {
  return {
    getSubscription: vi.fn().mockResolvedValue(subscription),
    subscribe: vi.fn().mockResolvedValue(subscription ?? makeSubscription()),
  };
}

function makeRegistration(pushManager: PushManagerLike): ServiceWorkerRegistrationLike {
  return { pushManager };
}

function makeDeps(overrides: {
  subscription?: PushSubscriptionLike | null;
  permission?: NotificationPermission;
  requestPermission?: () => Promise<NotificationPermission>;
  fetch?: typeof fetch;
  pushManager?: PushManagerLike;
} = {}): PushDeps & { fetchMock: ReturnType<typeof vi.fn> } {
  const pushManager =
    overrides.pushManager ?? makePushManager(overrides.subscription ?? makeSubscription());
  const registration = makeRegistration(pushManager);
  const notification: NotificationLike = {
    permission: overrides.permission ?? 'granted',
    requestPermission:
      overrides.requestPermission ?? vi.fn().mockResolvedValue('granted' as NotificationPermission),
  };
  const fetchMock = vi.fn(
    overrides.fetch ??
      (() => Promise.resolve(jsonResponse({ key: 'vapid-public-key' }))),
  );
  const navigatorLike: PushNavigator = {
    serviceWorker: {
      ready: Promise.resolve(registration),
    },
  };
  const windowLike: PushWindow = {
    PushManager: { prototype: {} },
    Notification: notification,
    location: { origin: 'https://rasp.example.ru' },
  };
  return {
    navigator: navigatorLike,
    window: windowLike,
    fetch: fetchMock as unknown as typeof fetch,
    fetchMock: fetchMock as unknown as ReturnType<typeof vi.fn>,
  };
}

describe('urlBase64ToUint8Array', () => {
  it('decodes base64url into bytes', () => {
    // "hello" in base64url.
    expect(Array.from(urlBase64ToUint8Array('aGVsbG8'))).toEqual([
      104, 101, 108, 108, 111,
    ]);
  });

  it('accepts standard base64 with padding', () => {
    expect(Array.from(urlBase64ToUint8Array('aGVsbG8='))).toEqual([
      104, 101, 108, 108, 111,
    ]);
  });
});

describe('isPushSupported', () => {
  it('is true when Notification, PushManager and serviceWorker exist', () => {
    expect(isPushSupported(makeDeps())).toBe(true);
  });

  it('is false without the Notification API', () => {
    const deps = makeDeps();
    deps.window.Notification = undefined;
    expect(isPushSupported(deps)).toBe(false);
  });

  it('is false without PushManager', () => {
    const deps = makeDeps();
    deps.window.PushManager = undefined;
    expect(isPushSupported(deps)).toBe(false);
  });

  it('is false without serviceWorker support', () => {
    const deps = makeDeps();
    deps.navigator = {};
    expect(isPushSupported(deps)).toBe(false);
  });
});

describe('fetchVapidPublicKey', () => {
  it('reads the {key} edge response', async () => {
    const deps = makeDeps();
    await expect(fetchVapidPublicKey(deps)).resolves.toBe('vapid-public-key');
    expect(deps.fetchMock).toHaveBeenCalledWith('/api/push/vapid-public-key', {
      headers: { Accept: 'application/json' },
    });
  });

  it('throws on a non-OK response', async () => {
    const deps = makeDeps({ fetch: () => Promise.resolve(jsonResponse({ detail: 'no' }, 404)) });
    await expect(fetchVapidPublicKey(deps)).rejects.toThrow('HTTP 404');
  });

  it('throws when the key is absent', async () => {
    const deps = makeDeps({ fetch: () => Promise.resolve(jsonResponse({})) });
    await expect(fetchVapidPublicKey(deps)).rejects.toThrow('VAPID-ключ отсутствует');
  });
});

describe('buildSubscribeBody', () => {
  it('maps the subscription into the exact origin field names', () => {
    expect(
      buildSubscribeBody(makeSubscription(), 'school_133', '5А', 'class'),
    ).toEqual({
      endpoint: 'https://fcm.example/ep',
      keys: { p256dh: 'p256dh-value', auth: 'auth-value' },
      school_id: 'school_133',
      kind: 'class',
      name: '5А',
    });
  });

  it('defaults kind to class', () => {
    expect(buildSubscribeBody(makeSubscription(), 's', 'n').kind).toBe('class');
  });

  it('throws when the encryption keys are missing', () => {
    const sub = makeSubscription({ toJSON: () => ({ keys: {} }) });
    expect(() => buildSubscribeBody(sub, 's', 'n')).toThrow('ключей шифрования');
  });
});

describe('buildPushRequest', () => {
  it('POSTs JSON to /api/push/subscribe with no secret header', () => {
    const body = buildSubscribeBody(makeSubscription(), 's', 'n');
    const { url, init } = buildPushRequest('subscribe', body);
    expect(url).toBe('/api/push/subscribe');
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' });
    // The edge injects X-Edge-Auth; the browser must never carry the secret.
    expect(JSON.stringify(init.headers)).not.toContain('Edge-Auth');
    expect(JSON.parse(init.body as string)).toEqual(body);
  });

  it('POSTs JSON to /api/push/unsubscribe', () => {
    const { url, init } = buildPushRequest('unsubscribe', { endpoint: 'e' });
    expect(url).toBe('/api/push/unsubscribe');
    expect(JSON.parse(init.body as string)).toEqual({ endpoint: 'e' });
  });
});

describe('getPermission', () => {
  it('reads the Notification permission', () => {
    expect(getPermission(makeDeps({ permission: 'default' }))).toBe('default');
    expect(getPermission(makeDeps({ permission: 'granted' }))).toBe('granted');
  });

  it('falls back to default without the API', () => {
    const deps = makeDeps();
    deps.window.Notification = undefined;
    expect(getPermission(deps)).toBe('default');
  });
});

describe('enablePush', () => {
  it('requests permission, fetches the key and subscribes + POSTs', async () => {
    const subscription = makeSubscription();
    // No existing subscription -> subscribe() must be called.
    const pushManager: PushManagerLike = {
      getSubscription: vi.fn().mockResolvedValue(null),
      subscribe: vi.fn().mockResolvedValue(subscription),
    };
    const requestPermission = vi.fn().mockResolvedValue('granted' as NotificationPermission);
    const deps = makeDeps({ pushManager, requestPermission, permission: 'default' });

    const result = await enablePush({ schoolId: 'gym1', name: '5А' }, deps);

    expect(result.ok).toBe(true);
    expect(result.state).toBe('subscribed');
    expect(requestPermission).toHaveBeenCalled();
    expect(pushManager.subscribe).toHaveBeenCalledWith({
      userVisibleOnly: true,
      applicationServerKey: expect.any(Uint8Array),
    });
    // The subscribe POST is the second fetch call (after the VAPID read).
    const [url, init] = deps.fetchMock.mock.calls[1];
    expect(url).toBe('/api/push/subscribe');
    expect(JSON.parse((init as RequestInit).body as string)).toMatchObject({
      endpoint: 'https://fcm.example/ep',
      school_id: 'gym1',
      kind: 'class',
      name: '5А',
    });
    expect(JSON.stringify((init as RequestInit).headers)).not.toContain('Edge-Auth');
  });

  it('reuses an existing subscription (idempotent) but still re-POSTs the class', async () => {
    const existing = makeSubscription();
    const pushManager = makePushManager(existing);
    const deps = makeDeps({ subscription: existing, pushManager });

    const result = await enablePush({ schoolId: 'gym1', name: '6Б' }, deps);

    expect(result.ok).toBe(true);
    expect(pushManager.subscribe).not.toHaveBeenCalled();
    expect(JSON.parse((deps.fetchMock.mock.calls[1][1] as RequestInit).body as string)).toMatchObject(
      { name: '6Б' },
    );
  });

  it('returns denied and does not subscribe when permission is refused', async () => {
    const pushManager = makePushManager();
    const deps = makeDeps({
      permission: 'default',
      pushManager,
      requestPermission: vi.fn().mockResolvedValue('denied' as NotificationPermission),
    });

    const result = await enablePush({ schoolId: 'gym1', name: '5А' }, deps);

    expect(result).toEqual({ ok: false, state: 'denied', error: 'Уведомления не разрешены' });
    expect(pushManager.subscribe).not.toHaveBeenCalled();
    expect(deps.fetchMock).not.toHaveBeenCalled();
  });

  it('skips requestPermission when already granted', async () => {
    const requestPermission = vi.fn().mockResolvedValue('granted' as NotificationPermission);
    const deps = makeDeps({ permission: 'granted', requestPermission });

    await enablePush({ schoolId: 'gym1', name: '5А' }, deps);

    expect(requestPermission).not.toHaveBeenCalled();
  });

  it('reports unsupported without touching the network', async () => {
    const deps = makeDeps();
    deps.navigator = {};

    const result = await enablePush({ schoolId: 'gym1', name: '5А' }, deps);

    expect(result.state).toBe('unsupported');
    expect(deps.fetchMock).not.toHaveBeenCalled();
  });

  it('surfaces a subscribe POST failure as an error result', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url === '/api/push/vapid-public-key') {
        return Promise.resolve(jsonResponse({ key: 'vapid-public-key' }));
      }
      return Promise.resolve(jsonResponse({ detail: 'Forbidden' }, 403));
    });
    const deps = makeDeps({ fetch: fetchMock as unknown as typeof fetch });

    const result = await enablePush({ schoolId: 'gym1', name: '5А' }, deps);

    expect(result.ok).toBe(false);
    expect(result.state).toBe('error');
    expect(result.error).toBe('Forbidden');
  });
});

describe('disablePush', () => {
  it('POSTs the endpoint to unsubscribe and drops it locally', async () => {
    const unsubscribe = vi.fn().mockResolvedValue(true);
    const subscription = makeSubscription({ unsubscribe });
    const deps = makeDeps({ subscription, pushManager: makePushManager(subscription) });

    const result = await disablePush(deps);

    expect(result.ok).toBe(true);
    const [url, init] = deps.fetchMock.mock.calls[0];
    expect(url).toBe('/api/push/unsubscribe');
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      endpoint: 'https://fcm.example/ep',
    });
    expect(unsubscribe).toHaveBeenCalled();
  });

  it('is a successful no-op when there is no subscription', async () => {
    const deps = makeDeps({ subscription: null, pushManager: makePushManager(null) });
    const result = await disablePush(deps);
    expect(result).toEqual({ ok: true, state: 'subscribed' });
    expect(deps.fetchMock).not.toHaveBeenCalled();
  });
});

describe('hasSubscription', () => {
  it('reflects whether pushManager has a subscription', async () => {
    await expect(
      hasSubscription(makeDeps({ subscription: makeSubscription() })),
    ).resolves.toBe(true);
    await expect(
      hasSubscription(makeDeps({ subscription: null, pushManager: makePushManager(null) })),
    ).resolves.toBe(false);
  });

  it('is false without serviceWorker', async () => {
    const deps = makeDeps();
    deps.navigator = {};
    await expect(hasSubscription(deps)).resolves.toBe(false);
  });
});
