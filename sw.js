/**
 * Finwell AI service worker.
 *
 * Goals:
 *  - First visit: do nothing visible. Install + take control silently so the
 *    next page navigation is the one that benefits.
 *  - Repeat visits: serve /assets/* (CSS, JS, fonts, images) from the cache
 *    instantly, then revalidate in the background.
 *  - Never cache HTML, third-party scripts, or function endpoints. Those go
 *    to the network so users see the latest deploy.
 *
 * Bump VERSION whenever the asset surface changes substantially. Old caches
 * are dropped on `activate`.
 */
const VERSION = 'finwellai-v1';
const ASSET_RE = /\/assets\//;

self.addEventListener('install', (event) => {
  // Skip waiting so the SW takes control on first install.
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter((n) => n !== VERSION).map((n) => caches.delete(n)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Only cache same-origin /assets/* — everything else (HTML, third-party,
  // /.netlify/functions/*) goes to network.
  if (url.origin !== self.location.origin) return;
  if (!ASSET_RE.test(url.pathname)) return;

  event.respondWith((async () => {
    const cache = await caches.open(VERSION);
    const cached = await cache.match(req);
    // Stale-while-revalidate: serve cached, refresh cache in background.
    const networkPromise = fetch(req)
      .then((res) => {
        if (res && res.ok) cache.put(req, res.clone()).catch(() => {});
        return res;
      })
      .catch(() => null);
    return cached || (await networkPromise) || new Response('', { status: 504 });
  })());
});
