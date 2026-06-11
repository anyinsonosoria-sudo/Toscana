const CACHE_NAME = 'toscana-pwa-v3';
const STATIC_ASSETS = [
  '/static/css/app.css',
  '/static/css/mobile_app.css',
  '/static/css/resident_portal.css',
  '/static/css/resident_chat.css',
  '/static/js/mobile_app.js',
  '/static/js/wizard.js',
  '/static/offline.html',
  '/static/manifest.json',
  '/static/icons/aosys-icon-72.png',
  '/static/icons/aosys-icon-96.png',
  '/static/icons/aosys-icon-128.png',
  '/static/icons/aosys-icon-144.png',
  '/static/icons/aosys-icon-180.png',
  '/static/icons/aosys-icon-192.png',
  '/static/icons/aosys-icon-512.png',
  '/static/icons/resident-toscana-logo.png',
  '/static/icons/logo_aosys.svg',
  '/static/icons/logo_toscana.svg',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

// Install: pre-cache static assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Fetch: network-first for HTML, cache-first for static assets
self.addEventListener('fetch', event => {
  // Skip non-GET and API requests
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Bypass Service Worker for PDF endpoints to fix Safari iOS PWA bug
  if (url.pathname.includes('/pdf') || url.pathname.endsWith('.pdf')) {
      return;
  }

  // Static assets: cache-first
  if (url.pathname.startsWith('/static/') || url.hostname.includes('cdn.jsdelivr.net')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        return cached || fetch(event.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
    return;
  }

  // HTML pages: network-first with fallback to offline.html
  if (event.request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => {
          return caches.match(event.request).then(cachedResponse => {
             // Return cached page if available, else return offline.html
             return cachedResponse || caches.match('/static/offline.html');
          });
        })
    );
    return;
  }
});