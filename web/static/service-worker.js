// Service Worker для PWA
const CACHE_NAME = 'raspisanie-v3-static';
// Публичные данные расписания кэшируются отдельно, чтобы их можно было чистить по TTL
const API_CACHE_NAME = 'raspisanie-v3-api';
// Свежесть кэша публичного API: 12 часов
const API_TTL_MS = 12 * 60 * 60 * 1000;
// Ограничение размера TTL-кэша, чтобы индекс не рос бесконечно
const API_CACHE_LIMIT = 100;
// Флаг ответа «из кэша» — приложение по нему показывает офлайн-индикатор
const FROM_CACHE_HEADER = 'X-SW-From-Cache';
const CACHED_AT_HEADER = 'X-SW-Cached-At';

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/style.css',
  '/app.js',
  '/manifest.json'
];

// Персональные данные — никогда не кэшируем
function isPrivateApi(pathname) {
  return pathname === '/api/me' || pathname.startsWith('/api/me/')
    || pathname === '/api/widget' || pathname.startsWith('/api/widget/');
}

// Добавляет/переопределяет заголовки, сохраняя тело и метаданные ответа
async function taggedResponse(response, headers) {
  const body = await response.blob();
  const merged = new Headers(response.headers);
  Object.entries(headers).forEach(([key, value]) => merged.set(key, value));
  return new Response(body, {
    status: response.status,
    statusText: response.statusText,
    headers: merged
  });
}

// Удаляет просроченные записи API-кэша и подрезает его до API_CACHE_LIMIT
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

// Network-first с TTL-fallback: свежий кэш отдаём с пометкой, старый — нет
async function handleApiRequest(request) {
  let cache = null;
  try {
    cache = await caches.open(API_CACHE_NAME);
  } catch (openErr) {
    // Кэш недоступен — деградируем до работы только через сеть
  }
  try {
    const response = await fetch(request);
    if (response.ok && cache) {
      try {
        const stamped = await taggedResponse(response.clone(), {
          [CACHED_AT_HEADER]: String(Date.now())
        });
        await cache.put(request, stamped);
        await pruneApiCache(cache, false);
      } catch (cacheErr) {
        // Сбой кэша (например QuotaExceededError) не должен ломать успешный ответ
      }
    }
    return response;
  } catch (err) {
    const cached = cache ? await cache.match(request).catch(() => null) : null;
    if (cached) {
      const cachedAt = Number(cached.headers.get(CACHED_AT_HEADER) || 0);
      if (cachedAt && Date.now() - cachedAt <= API_TTL_MS) {
        return taggedResponse(cached, { [FROM_CACHE_HEADER]: '1' });
      }
      await cache.delete(request).catch(() => {});
    }
    // Свежих данных нет — лучше ошибка, чем устаревшее расписание
    return new Response(
      JSON.stringify({ detail: 'Офлайн: нет свежих данных расписания' }),
      {
        status: 503,
        statusText: 'Service Unavailable',
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

// Установка — кэшируем статику
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Активация — чистим старые кэши и просроченные записи API
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(
      cacheNames
        .filter((name) => name !== CACHE_NAME && name !== API_CACHE_NAME)
        .map((name) => caches.delete(name))
    );
    const cache = await caches.open(API_CACHE_NAME);
    await pruneApiCache(cache, true);
  })());
  self.clients.claim();
});

// Запросы — сеть с fallback на кэш
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Кэшируем только GET — остальные запросы проксируем в сеть
  if (request.method !== 'GET') {
    event.respondWith(fetch(request));
    return;
  }

  // Персональные API — только сеть, без кэширования
  if (isPrivateApi(url.pathname)) {
    event.respondWith(fetch(request));
    return;
  }

  // Прочие API — network-first с fallback на свежий TTL-кэш
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request));
    return;
  }

  // Статика — stale-while-revalidate
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.match(request).then((cached) => {
        const network = fetch(request).then((response) => {
          if (!response.ok) return response;
          return cache.put(request, response.clone()).then(() => response);
        });
        if (cached) {
          // Ревалидация привязана к waitUntil, чтобы не потеряться при остановке SW
          event.waitUntil(network.catch(() => {}));
          return cached;
        }
        return network;
      });
    })
  );
});

// Background Sync для виджета (если поддерживается)
self.addEventListener('sync', (event) => {
  if (event.tag === 'widget-update') {
    event.waitUntil(updateWidgetData());
  }
});

async function updateWidgetData() {
  // Периодическое обновление данных для виджета
  // Вызывается когда приложение открыто или по background sync
  const clients = await self.clients.matchAll({ type: 'window' });
  clients.forEach((client) => {
    client.postMessage({
      type: 'WIDGET_UPDATE',
      timestamp: Date.now()
    });
  });
}

// Push уведомления (резерв на будущее)
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  const title = data.title || 'Расписание';
  const options = {
    body: data.body || 'Новое событие',
    icon: '/icon-192.png',
    badge: '/icon-192.png',
    data: data.url || '/'
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || event.notification.data || '/';
  event.waitUntil(
    self.clients.openWindow(typeof target === 'string' ? target : '/')
  );
});
