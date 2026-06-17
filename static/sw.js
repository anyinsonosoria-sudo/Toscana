// Service Worker - Toscana PWA
// This SW self-destructs all old caches and passes ALL requests through to the network.
// This fixes issues with stale caches breaking navigation and PDF downloads.

// version update to force cache clear: 102
const CACHE_NAME = 'toscana-pwa-v102';

// Install: skip waiting immediately
self.addEventListener('install', event => {
  self.skipWaiting();
});

// Activate: delete ALL old caches and claim all clients immediately
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// Fetch: pass EVERYTHING through to the network. No caching.
// This ensures no stale pages or assets can break the app.
self.addEventListener('fetch', event => {
  // Simply let the browser handle the request natively.
  // Do NOT intercept anything.
});