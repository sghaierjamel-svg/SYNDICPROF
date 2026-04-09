// SyndicPro Service Worker — v1.2
const CACHE_NAME = 'syndicpro-v1';

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

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET') return;
  if (url.pathname.startsWith('/api/')) return;

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

  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// ─── Web Push ────────────────────────────────────────────────────────────────

self.addEventListener('push', (event) => {
  // Valeurs par défaut
  let title = 'SyndicPro';
  let body  = 'Vous avez une nouvelle notification';
  let url   = '/dashboard';
  let icon  = '/static/icons/icon-192.png';
  let tag   = 'syndicpro-general';

  // Lire le payload envoyé par le serveur
  if (event.data) {
    try {
      const d = event.data.json();
      if (d.title) title = d.title;
      if (d.body)  body  = d.body;
      if (d.url)   url   = d.url;
      if (d.icon)  icon  = d.icon;
      if (d.tag)   tag   = d.tag;
    } catch (e) {
      // Si ce n'est pas du JSON, afficher le texte brut
      try { body = event.data.text(); } catch (_) {}
    }
  }

  event.waitUntil(
    self.registration.showNotification(title, {
      body:      body,
      icon:      icon,
      badge:     '/static/icons/icon-192.png',
      vibrate:   [300, 100, 300],
      tag:       tag,
      renotify:  true,
      requireInteraction: false,
      data:      { url: url },
    })
  );
});

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
