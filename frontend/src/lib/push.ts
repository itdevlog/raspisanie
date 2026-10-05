// frontend/src/lib/push.ts
//
// Web Push opt-in (W23) — the browser half of the public push contract.
//
// Design (verified against `web/edge_push.py`, `web/push_api.py` and the spec
// §5/§6):
//
//   * `GET /api/push/vapid-public-key` on the EDGE returns `{"key": "..."}`
//     locally (the public key is not a secret).
//   * `POST /api/push/subscribe|unsubscribe` on the EDGE proxy the raw JSON body
//     to the origin, where `web/push_api.py` checks `X-Edge-Auth`. The browser
//     **must not** send `X-Edge-Auth` — the edge injects the shared secret
//     server-side and the secret must never reach a client. The only headers the
//     browser sets here are `Content-Type: application/json`.
//
// Every browser dependency (`navigator`, `window.PushManager`, `Notification`,
// `fetch`) is injectable so the module is unit-testable under jsdom. Nothing
// throws; failures come back as a typed {@link PushResult}.
//
// MVP scope is class-only (W12/W16): the schema always carries `kind: 'class'`.

import type { ScheduleKind } from './api/types';

/** Body sent to `/api/push/subscribe`; field names mirror `web/push_api.py`. */
export interface SubscribeBody {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  school_id: string;
  kind: ScheduleKind;
  name: string;
}

/** Body sent to `/api/push/unsubscribe`; only `endpoint` is required. */
export interface UnsubscribeBody {
  endpoint: string;
}

/** Minimal `PushSubscription` surface used here. */
export interface PushSubscriptionLike {
  endpoint: string;
  toJSON(): { keys?: { p256dh?: string; auth?: string } };
  unsubscribe?: () => Promise<boolean>;
}

/** Minimal `PushSubscriptionOptionsInit`; `applicationServerKey` stays typed. */
export interface PushSubscribeOptions {
  userVisibleOnly: boolean;
  applicationServerKey: Uint8Array;
}

/** Minimal `PushManager` surface. */
export interface PushManagerLike {
  getSubscription(): Promise<PushSubscriptionLike | null>;
  subscribe(options: PushSubscribeOptions): Promise<PushSubscriptionLike>;
}

/** Minimal `ServiceWorkerRegistration` surface. */
export interface ServiceWorkerRegistrationLike {
  pushManager: PushManagerLike;
}

/** Minimal `ServiceWorkerContainer` surface. */
export interface ServiceWorkerContainerLike {
  ready: Promise<ServiceWorkerRegistrationLike>;
  register?: (scriptURL: string) => Promise<unknown>;
  getRegistration?: () => Promise<ServiceWorkerRegistrationLike | undefined>;
}

/** Minimal `Notification` constructor surface (also used for the permission API). */
export interface NotificationLike {
  permission: NotificationPermission;
  requestPermission(): Promise<NotificationPermission>;
}

/** Minimal `navigator` surface for push opt-in. */
export interface PushNavigator {
  serviceWorker?: ServiceWorkerContainerLike;
}

/** Minimal `window` surface: `PushManager`, `Notification`, `location.origin`. */
export interface PushWindow {
  PushManager?: { prototype: unknown };
  Notification?: NotificationLike;
  location: { origin: string };
}

/** Injected browser dependencies; production uses {@link defaultPushDeps}. */
export interface PushDeps {
  navigator: PushNavigator;
  window: PushWindow;
  fetch: typeof fetch;
}

/**
 * Outcome of a push opt-in attempt. `state` is `'subscribed'` when a live
 * subscription now exists, `'unsupported'` when the browser lacks Web Push,
 * `'denied'` when the user refused permission, and `'error'` otherwise.
 */
export interface PushResult {
  ok: boolean;
  state: 'subscribed' | 'unsupported' | 'denied' | 'error';
  subscription?: PushSubscriptionLike;
  error?: string;
}

/** Options for {@link enablePush}; `url` is the W16 share link for the class. */
export interface EnablePushOptions {
  schoolId: string;
  name: string;
  kind?: ScheduleKind;
  /**
   * Optional W16 share URL for the class. Not sent with subscribe today (the
   * origin derives the click target when a replacement is detected); accepted so
   * callers can keep the UI's share link and opt-in in one place.
   */
  url?: string;
}

/**
 * Is Web Push usable at all in this environment? Checks notification support,
 * service worker + PushManager presence, and a secure context (localhost is
 * treated as secure by browsers but jsdom has no `isSecureContext`).
 */
export function isPushSupported(deps: PushDeps = defaultPushDeps()): boolean {
  const win = deps.window;
  if (!win?.Notification || !win?.PushManager) {
    return false;
  }
  if (!deps.navigator?.serviceWorker) {
    return false;
  }
  const secure = (globalThis as { isSecureContext?: boolean }).isSecureContext;
  // `isSecureContext` is undefined outside a real browser/page; do not hard-fail
  // on that, the presence checks above are the meaningful ones in tests/jsdom.
  return secure !== false;
}

/** Fetch the VAPID public key from the edge. Accepts `{key}` (edge contract). */
export async function fetchVapidPublicKey(deps: PushDeps = defaultPushDeps()): Promise<string> {
  const response = await deps.fetch('/api/push/vapid-public-key', {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Не удалось получить VAPID-ключ (HTTP ${response.status})`);
  }
  const body = (await response.json()) as { key?: unknown };
  if (typeof body?.key !== 'string' || !body.key) {
    throw new Error('VAPID-ключ отсутствует в ответе');
  }
  return body.key;
}

/**
 * Decode a base64url VAPID public key into the `Uint8Array` that
 * `pushManager.subscribe` expects as `applicationServerKey`.
 */
export function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const normalized = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(normalized);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) {
    output[i] = raw.charCodeAt(i);
  }
  return output;
}

/**
 * Build the `/api/push/subscribe` body from a `PushSubscription`.
 *
 * Field names are exactly what `web/push_api.py` reads: `endpoint`, `keys`
 * (`p256dh`/`auth`), `school_id`, `kind`, `name`. Throws when the browser omits
 * the encryption keys (an unusable subscription must not be sent upstream).
 */
export function buildSubscribeBody(
  subscription: PushSubscriptionLike,
  schoolId: string,
  name: string,
  kind: ScheduleKind = 'class',
): SubscribeBody {
  const json = subscription.toJSON();
  const p256dh = json.keys?.p256dh;
  const auth = json.keys?.auth;
  if (!subscription.endpoint || !p256dh || !auth) {
    throw new Error('Подписка не содержит ключей шифрования');
  }
  return {
    endpoint: subscription.endpoint,
    keys: { p256dh, auth },
    school_id: schoolId,
    kind,
    name,
  };
}

/**
 * Turn a subscription into a JSON request to `/api/push/{action}`.
 *
 * No `X-Edge-Auth` is (or may be) sent from the browser; the edge adds it when
 * proxying to the origin. `Content-Type: application/json` is the only header.
 */
export function buildPushRequest(
  action: 'subscribe' | 'unsubscribe',
  body: SubscribeBody | UnsubscribeBody,
): { url: string; init: RequestInit } {
  return {
    url: `/api/push/${action}`,
    init: {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  };
}

/** POST the subscribe body to the edge; throws with the server `detail` on failure. */
export async function postSubscribe(
  body: SubscribeBody,
  deps: PushDeps = defaultPushDeps(),
): Promise<void> {
  const { url, init } = buildPushRequest('subscribe', body);
  const response = await deps.fetch(url, init);
  if (!response.ok) {
    throw new Error(await errorDetail(response, 'Не удалось сохранить подписку'));
  }
}

/** POST the unsubscribe body to the edge; throws with the server `detail` on failure. */
export async function postUnsubscribe(
  body: UnsubscribeBody,
  deps: PushDeps = defaultPushDeps(),
): Promise<void> {
  const { url, init } = buildPushRequest('unsubscribe', body);
  const response = await deps.fetch(url, init);
  if (!response.ok) {
    throw new Error(await errorDetail(response, 'Не удалось отменить подписку'));
  }
}

/** Current granted permission, or `'default'` when the Notification API is absent. */
export function getPermission(deps: PushDeps = defaultPushDeps()): NotificationPermission {
  return deps.window?.Notification?.permission ?? 'default';
}

/**
 * Full opt-in flow: request permission → fetch VAPID key → subscribe (or reuse
 * an existing subscription) → POST `/api/push/subscribe`.
 *
 * Idempotent: if a subscription already exists it is reused, but the
 * server-side `school_id`/`kind`/`name` are re-sent (the class selection may
 * have changed since the subscription was created).
 */
export async function enablePush(
  options: EnablePushOptions,
  deps: PushDeps = defaultPushDeps(),
): Promise<PushResult> {
  const { schoolId, name, kind = 'class' } = options;
  if (!isPushSupported(deps)) {
    return { ok: false, state: 'unsupported', error: 'Web Push недоступен в этом браузере' };
  }

  const notification = deps.window.Notification;
  if (notification?.permission !== 'granted') {
    const permission = await notification!.requestPermission();
    if (permission !== 'granted') {
      return { ok: false, state: 'denied', error: 'Уведомления не разрешены' };
    }
  }

  try {
    const registration = await deps.navigator.serviceWorker!.ready;
    const publicKey = await fetchVapidPublicKey(deps);
    const existing = await registration.pushManager.getSubscription();
    const subscription =
      existing ??
      (await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      }));
    await postSubscribe(buildSubscribeBody(subscription, schoolId, name, kind), deps);
    return { ok: true, state: 'subscribed', subscription };
  } catch (err) {
    return { ok: false, state: 'error', error: errorMessage(err) };
  }
}

/**
 * Undo the opt-in: unsubscribe locally (best-effort) and tell the server to drop
 * the endpoint. A missing subscription is reported as a successful no-op.
 */
export async function disablePush(deps: PushDeps = defaultPushDeps()): Promise<PushResult> {
  if (!deps.navigator?.serviceWorker) {
    return { ok: false, state: 'unsupported', error: 'Web Push недоступен в этом браузере' };
  }
  try {
    const registration = await deps.navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      return { ok: true, state: 'subscribed' };
    }
    await postUnsubscribe({ endpoint: subscription.endpoint }, deps);
    if (subscription.unsubscribe) {
      // The server record is already gone; a local failure should not surface.
      await subscription.unsubscribe().catch(() => false);
    }
    return { ok: true, state: 'subscribed' };
  } catch (err) {
    return { ok: false, state: 'error', error: errorMessage(err) };
  }
}

/** Is there already a browser subscription for this origin? */
export async function hasSubscription(deps: PushDeps = defaultPushDeps()): Promise<boolean> {
  if (!deps.navigator?.serviceWorker) {
    return false;
  }
  try {
    const registration = await deps.navigator.serviceWorker.ready;
    return (await registration.pushManager.getSubscription()) !== null;
  } catch {
    return false;
  }
}

/** Production dependencies; `navigator`/`window`/`fetch` are read lazily. */
export function defaultPushDeps(): PushDeps {
  const win = (typeof window === 'undefined' ? undefined : window) as
    | (Window & PushWindow)
    | undefined;
  return {
    navigator: (typeof navigator === 'undefined' ? {} : navigator) as unknown as PushNavigator,
    window: (win ?? { location: { origin: '' } }) as unknown as PushWindow,
    fetch: (...args: Parameters<typeof fetch>) => fetch(...args),
  };
}

/** Read the server's `detail` from a failed response, else a fallback message. */
async function errorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body?.detail === 'string' && body.detail) {
      return body.detail;
    }
  } catch {
    // Non-JSON error body — use the fallback.
  }
  return fallback;
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : 'Не удалось включить уведомления';
}
