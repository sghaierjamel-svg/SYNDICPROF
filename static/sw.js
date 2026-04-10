// SyndicPro Service Worker — v1.3 (PWA)
const CACHE_VERSION = 'syndicpro-v1.3';
const OFFLINE_URL   = '/static/offline.html';

// Assets statiques à mettre en cache immédiatement
const STATIC_ASSETS = [
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css',
];

// ── Install ───────────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => {
      // Mettre en cache les assets statiques (silencieux si l'un échoue)
      return Promise.allSettled(
        STATIC_ASSETS.map(url => cache.add(url).catch(() => null))
      );
    })
  );
  self.skipWaiting();
});

// ── Activate ──────────────────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_VERSION)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Ignorer les requêtes non-GET et les APIs
  if (req.method !== 'GET') return;
  if (url.pathname.startsWith('/api/')) return;
  if (url.pathname.startsWith('/konnect/') || url.pathname.startsWith('/flouci/')) return;

  // CDN (Bootstrap, icons) → Cache First
  if (url.hostname.includes('jsdelivr.net') || url.hostname.includes('googleapis.com')) {
    event.respondWith(
      caches.match(req).then((cached) =>
        cached || fetch(req).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(req, clone));
          }
          return response;
        })
      )
    );
    return;
  }

  // Assets statiques locaux (/static/) → Cache First
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((cached) =>
        cached || fetch(req).then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(req, clone));
          }
          return response;
        }).catch(() => caches.match(OFFLINE_URL))
      )
    );
    return;
  }

  // Pages HTML → Network First, fallback cache, fallback offline
  event.respondWith(
    fetch(req)
      .then((response) => {
        // Mettre en cache les pages réussies pour consultation hors-ligne
        if (response.ok && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(req, clone));
        }
        return response;
      })
      .catch(() =>
        caches.match(req).then((cached) => cached || caches.match(OFFLINE_URL))
      )
  );
});

// ── Web Push ──────────────────────────────────────────────────────────────────
self.addEventListener('push', (event) => {
  let title = 'SyndicPro';
  let body  = 'Vous avez une nouvelle notification';
  let url   = '/dashboard';
  let icon  = '/static/icons/icon-192.png';
  let badge = '/static/icons/icon-192.png';
  let tag   = 'syndicpro-general';

  if (event.data) {
    try {
      const d = event.data.json();
      if (d.title) title = d.title;
      if (d.body)  body  = d.body;
      if (d.url)   url   = d.url;
      if (d.icon)  icon  = d.icon;
      if (d.tag)   tag   = d.tag;
    } catch (e) {
      try { body = event.data.text(); } catch (_) {}
    }
  }

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon,
      badge,
      vibrate:   [300, 100, 300],
      tag,
      renotify:  true,
      requireInteraction: false,
      data: { url },
    })
  );
});

// ── Notification click ────────────────────────────────────────────────────────
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/dashboard';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      return clients.openWindow(targetUrl);
    })
  );
});
