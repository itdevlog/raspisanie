// frontend/public/service-worker.js
//
// PWA service worker for the public Svelte schedule site (W23).
//
// Caching logic is adapted from the origin mini-app SW
// (`web/static/service-worker.js`): network-first for `/api/*` with a
// freshness-bounded cache, stale-while-revalidate for static assets, and a
// `X-SW-From-Cache: 1` marker that the app reads for its offline indicator.
//
// Differences from the origin SW (deliberately, for the edge/SPA setup):
//   * Vite emits hashed asset names, so static caching is runtime
//     (stale-while-revalidate) rather than a fixed `STATIC_ASSETS` precache list;
//   * `GET /api/push/*` is never cached (it is a read of a live key, not data);
//   * the `push`/`notificationclick` handlers implement the W13 payload shape
//     `{title, body, url}` and open the W16 `/s/...` share link.
//
// Hard rule: the browser never sends `X-Edge-Auth`; only schedule data (read-only
// public GETs) is cached.

const CACHE_NAME = 'raspisanie-pwa-v1-static';
// Schedule data lives in a separate cache so it can be pruned by TTL.
const API_CACHE_NAME = 'raspisanie-pwa-v1-api';
// Schedule freshness: 12 hours (mirrors the origin SW).
const API_TTL_MS = 12 * 60 * 60 * 1000;
// Keep the TTL cache bounded so the index cannot grow without limit.
const API_CACHE_LIMIT = 100;
// Response markers read by the app's offline indicator.
const FROM_CACHE_HEADER = 'X-SW-From-Cache';
const CACHED_AT_HEADER = 'X-SW-Cached-At';

// Personal widgets are Telegram-only and must never be cached (defensive: on the
// public edge these routes do not exist, but the rule keeps the two SWs aligned).
function isPrivateApi(pathname) {
  return (
    pathname === '/api/me' ||
    pathname.startsWith('/api/me/') ||
    pathname === '/api/widget' ||
    pathname.startsWith('/api/widget/')
  );
}

// Push endpoints read live state (VAPID key) or write; never serve from cache.
function isPushApi(pathname) {
  return pathname.startsWith('/api/push/');
}

// Clone a response with extra headers, preserving body/status/metadata.
async function taggedResponse(response, headers) {
  const body = await response.blob();
  const merged = new Headers(response.headers);
  Object.entries(headers).forEach(([key, value]) => merged.set(key, value));
  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers: merged,
  });
}

// Drop expired API entries and trim the cache to API_CACHE_LIMIT.
let lastPruneAt = 0;
async function pruneApiCache(cache, force) {
  const now = Date.now();
  if (!force && now - lastPruneAt < 30 * 60 * 1000) return;
  lastPruneAt = now;
  const requests = await cache.keys();
  const fresh = [];
  for (const request of requests) {
    const cached = await cache.match(request);
    const cachedAt = cached ? Number(cached.headers.get(CACHED_AT_HEADER) || 0) : 0;
    if (!cachedAt || now - cachedAt > API_TTL_MS) {
      await cache.delete(request);
    } else {
      fresh.push({ request, cachedAt });
    }
  }
  fresh.sort((a, b) => a.cachedAt - b.cachedAt);
  const excess = fresh.length - API_CACHE_LIMIT;
  for (let i = 0; i < excess; i += 1) {
    await cache.delete(fresh[i].request);
  }
}

// Network-first with TTL fallback; cached responses carry X-SW-From-Cache.
async function handleApiRequest(request) {
  let cache = null;
  try {
    cache = await caches.open(API_CACHE_NAME);
  } catch {
    // Cache unavailable — degrade to network-only.
  }
  try {
    const response = await fetch(request);
    if (response.ok && cache) {
      try {
        const stamped = await taggedResponse(response.clone(), {
          [CACHED_AT_HEADER]: String(Date.now()),
        });
        await cache.put(request, stamped);
        await pruneApiCache(cache, false);
      } catch {
        // A cache write failure must not break a successful response.
      }
    }
    return response;
  } catch {
    const cached = cache ? await cache.match(request).catch(() => null) : null;
    if (cached) {
      const cachedAt = Number(cached.headers.get(CACHED_AT_HEADER) || 0);
      if (cachedAt && Date.now() - cachedAt <= API_TTL_MS) {
        // Tell open pages the shown data came from the TTL cache so the app can
        // raise its offline/stale indicator (the JSON body itself has no header).
        notifyClients({ type: 'SCHEDULE_FROM_CACHE' });
        return taggedResponse(cached, { [FROM_CACHE_HEADER]: '1' });
      }
      await cache.delete(request).catch(() => {});
    }
    notifyClients({ type: 'SCHEDULE_OFFLINE' });
    return new Response(
      JSON.stringify({ detail: 'Офлайн: нет свежих данных расписания' }),
      {
        status: 503,
        statusText: 'Service Unavailable',
        headers: { 'Content-Type': 'application/json' },
      },
    );
  }
}

// Best-effort broadcast to open windows (used for the offline indicator).
function notifyClients(message) {
  self.clients
    .matchAll({ type: 'window', includeUncontrolled: true })
    .then((clientList) => {
      clientList.forEach((client) => client.postMessage(message));
    })
    .catch(() => {});
}

// Install — activate immediately (assets are cached at runtime).
self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});

// Activate — drop old caches, prune the API cache, take control of open pages.
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const cacheNames = await caches.keys();
      await Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME && name !== API_CACHE_NAME)
          .map((name) => caches.delete(name)),
      );
      const cache = await caches.open(API_CACHE_NAME);
      await pruneApiCache(cache, true);
    })(),
  );
  self.clients.claim();
});

// Fetch — GET only; API network-first with TTL fallback; static SWR.
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Only same-origin GETs are handled; writes pass straight through.
  if (request.method !== 'GET' || url.origin !== self.location.origin) {
    return;
  }

  if (isPrivateApi(url.pathname) || isPushApi(url.pathname)) {
    event.respondWith(fetch(request));
    return;
  }

  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request));
    return;
  }

  // Static assets — stale-while-revalidate.
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(request).then((cached) => {
        const network = fetch(request).then((response) => {
          if (!response.ok) return response;
          return cache.put(request, response.clone()).then(() => response);
        });
        if (cached) {
          event.waitUntil(network.catch(() => {}));
          return cached;
        }
        return network;
      }),
    ),
  );
});

// Push — W13 payload is `{title, body, url}`; url is the W16 `/s/...` link.
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  const title = data.title || 'Расписание';
  const options = {
    body: data.body || 'Новое событие',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    data: { url: data.url || '/' },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// Notification click — focus an existing tab on the URL, else open a new one.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const payload = event.notification.data || {};
  const target = typeof payload.url === 'string' && payload.url ? payload.url : '/';
  event.waitUntil(
    self.clients
      .matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          const clientUrl = new URL(client.url);
          if (clientUrl.origin === self.location.origin && 'focus' in client) {
            client.navigate(target);
            return client.focus();
          }
        }
        return self.clients.openWindow(target);
      }),
  );
});
