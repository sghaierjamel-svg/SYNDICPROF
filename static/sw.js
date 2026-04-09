// SyndicPro Service Worker — v1.1
const CACHE_NAME = 'syndicpro-v1';

// Ressources statiques mises en cache au premier chargement
const STATIC_ASSETS = [
  '/static/manifest.json',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Stratégie : Network First pour les pages, Cache First pour les assets statiques
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Ignorer les requêtes non-GET et les APIs
  if (event.request.method !== 'GET') return;
  if (url.pathname.startsWith('/api/')) return;

  // Assets statiques CDN → Cache First
  if (url.hostname.includes('jsdelivr.net') || url.hostname.includes('googleapis.com')) {
    event.respondWith(
      caches.match(event.request).then((cached) =>
        cached || fetch(event.request).then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
      )
    );
    return;
  }

  // Pages de l'application → Network First (offline fallback si nécessaire)
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// ─── Web Push ────────────────────────────────────────────────────────────────

self.addEventListener('push', (event) => {
  let payload = { title: 'SyndicPro', body: 'Nouvelle notification', url: '/dashboard', icon: '/static/icons/icon-192.png' };
  try { payload = Object.assign(payload, event.data.json()); } catch (e) {}

  event.waitUntil(
    self.registration.showNotification(payload.title, {
      body:    payload.body,
      icon:    payload.icon,
      badge:   '/static/icons/icon-192.png',
      vibrate: [200, 100, 200],
      tag:     'syndicpro-notif',
      renotify: true,
      data:    { url: payload.url },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/dashboard';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});
