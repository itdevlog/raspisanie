// Service Worker для PWA
const CACHE_NAME = 'raspisanie-v2';
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/style.css',
  '/app.js',
  '/manifest.json'
];

// Установка — кэшируем статику
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Активация — чистим старые кэши
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
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
  if (url.pathname === '/api/me') {
    event.respondWith(fetch(request));
    return;
  }

  // Прочие API — сеть с fallback на кэш (для офлайна)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) => {
        return fetch(request)
          .then((response) => {
            if (response.ok) {
              cache.put(request, response.clone());
            }
            return response;
          })
          .catch(() => cache.match(request));
      })
    );
    return;
  }

  // Статика — stale-while-revalidate
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.match(request).then((cached) => {
        const network = fetch(request).then((response) => {
          if (response.ok) {
            cache.put(request, response.clone());
          }
          return response;
        }).catch(() => cached);
        return cached || network;
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
