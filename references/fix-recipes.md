# Fix Recipes

Short, copy-ready fixes for the most common findings. Quote the relevant one in the report's
"Fix" line; adapt names to the audited codebase. Plain JS unless noted.

## Service worker

**Fetch handler that actually responds, with navigation fallback and a response guard**

```js
const CACHE = 'app-v42';
const OFFLINE_URL = '/offline.html';

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(['/', OFFLINE_URL, '/app.css', '/app.js'])));
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
    if (self.registration.navigationPreload) await self.registration.navigationPreload.enable();
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const { request } = e;
  if (request.method !== 'GET') return;                     // let the network handle writes
  if (request.mode === 'navigate') {
    e.respondWith((async () => {
      try {
        return (await e.preloadResponse) || (await fetch(request));
      } catch {
        return (await caches.match(request)) || caches.match(OFFLINE_URL);
      }
    })());
    return;
  }
  e.respondWith(caches.match(request).then((hit) => hit || fetch(request).then((res) => {
    if (res.ok && res.type === 'basic') {                    // never cache errors or opaque responses
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(request, copy));
    }
    return res;
  })));
});
```

**Workbox equivalent (multiple strategies + expiration)**

```js
import { precacheAndRoute, cleanupOutdatedCaches, createHandlerBoundToURL } from 'workbox-precaching';
import { registerRoute, NavigationRoute } from 'workbox-routing';
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from 'workbox-strategies';
import { ExpirationPlugin } from 'workbox-expiration';
import { CacheableResponsePlugin } from 'workbox-cacheable-response';

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
registerRoute(new NavigationRoute(createHandlerBoundToURL('/index.html'), { denylist: [/^\/api\//] }));
registerRoute(({ request }) => request.destination === 'image',
  new CacheFirst({ cacheName: 'img', plugins: [
    new CacheableResponsePlugin({ statuses: [0, 200] }),
    new ExpirationPlugin({ maxEntries: 200, maxAgeSeconds: 30 * 24 * 3600 }),
  ] }));
registerRoute(({ url }) => url.pathname.startsWith('/api/'),
  new NetworkFirst({ cacheName: 'api', networkTimeoutSeconds: 4,
    plugins: [new ExpirationPlugin({ maxEntries: 100, maxAgeSeconds: 24 * 3600 })] }));
registerRoute(({ request }) => ['script', 'style'].includes(request.destination),
  new StaleWhileRevalidate({ cacheName: 'assets' }));
```

**Serve the SW uncached** (nginx): `location = /sw.js { add_header Cache-Control "no-cache"; }`

## Update UX (user-controlled, no repeat prompt)

```js
// SW
self.addEventListener('message', (e) => { if (e.data?.type === 'SKIP_WAITING') self.skipWaiting(); });

// Client
const reg = await navigator.serviceWorker.register('/sw.js');
const justUpdated = Number(localStorage.getItem('pwa-just-updated') || 0);
function offerUpdate(worker) {
  if (Date.now() - justUpdated < 30_000) return;           // suppress right after an update
  showToast('A new version is available', { action: 'Update', onAction: () => {
    localStorage.setItem('pwa-just-updated', String(Date.now()));
    worker.postMessage({ type: 'SKIP_WAITING' });
  } });
}
if (reg.waiting) offerUpdate(reg.waiting);
reg.addEventListener('updatefound', () => {
  const w = reg.installing;
  w?.addEventListener('statechange', () => {
    if (w.state === 'installed' && navigator.serviceWorker.controller) offerUpdate(w);
  });
});
let reloaded = false;
navigator.serviceWorker.addEventListener('controllerchange', () => {
  if (!reloaded) { reloaded = true; location.reload(); }
});
```

With `vite-plugin-pwa`: `registerType: 'prompt'` and `useRegisterSW({ onNeedRefresh })`.

## Install UX

```js
let deferred;
addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferred = e; installBtn.hidden = false; });
installBtn.onclick = async () => { deferred?.prompt(); await deferred?.userChoice; deferred = null; installBtn.hidden = true; };
addEventListener('appinstalled', () => { installBtn.hidden = true; });

const standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) ||
  (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
if (isIOS && !standalone) showIOSHint('Tap Share, then "Add to Home Screen"');
```

## Storage and sync

```js
if (navigator.storage?.persist && !(await navigator.storage.persisted())) await navigator.storage.persist();
const { usage, quota } = await navigator.storage.estimate();
if (quota && usage / quota > 0.8) warnStorageAlmostFull();

addEventListener('online', async () => {
  const reg = await navigator.serviceWorker.ready;
  if ('sync' in reg) await reg.sync.register('sync-pending');      // Chromium; else flush queue now
  else flushPendingQueue();
});

const reg = await navigator.serviceWorker.ready;
if ('periodicSync' in reg) {
  const { state } = await navigator.permissions.query({ name: 'periodic-background-sync' });
  if (state === 'granted') await reg.periodicSync.register('refresh-content', { minInterval: 12 * 3600 * 1000 });
}
```

## Real-time resilience (socket.io; same idea for raw WebSocket / SSE)

```js
const socket = io(URL, { reconnectionAttempts: Infinity, reconnectionDelay: 1000, reconnectionDelayMax: 30000 });

socket.on('connect', () => {                 // persistent: runs on first connect AND every reconnect
  socket.emit('join', { room: currentRoomId() });
});

function resume() {
  if (document.visibilityState === 'visible' && !socket.connected) socket.connect();
}
document.addEventListener('visibilitychange', resume);
addEventListener('pageshow', (e) => { if (e.persisted) resume(); });   // bfcache restore
addEventListener('online', resume);
// Show "Disconnected — tap to retry" bound to socket.connect() after a few failed attempts.
```

## SPA view-state persistence

```js
const key = `chat-active-${workspaceId}`;
const saved = localStorage.getItem(key);
if (saved) openConversation(saved).catch((err) => {
  if (err.status === 404) localStorage.removeItem(key);   // stale id: fall back to default view
});
function onSelect(id) { localStorage.setItem(key, id); openConversation(id); }
```

Prefer the URL (`/chat/:id`) when the router allows it; use localStorage only for state the URL
cannot carry.

## Layout (iOS)

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
```

```css
.app { min-height: 100vh; min-height: 100dvh; }
header.fixed { padding-top: env(safe-area-inset-top); }
nav.bottom { padding-bottom: max(12px, env(safe-area-inset-bottom)); }
html, body { overscroll-behavior: none; }
button, [role="button"] { cursor: pointer; touch-action: manipulation; }
input, select, textarea { font-size: 16px; }              /* prevents focus zoom on iOS */
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
```

**Mobile dropdown (Tailwind)**

```html
<div class="fixed left-4 right-4 top-16 sm:absolute sm:left-auto sm:right-0 sm:top-full sm:w-64"
     style="margin-right: env(safe-area-inset-right); margin-left: env(safe-area-inset-left)">
```

**Theme pairs (Tailwind)** — every alpha colour gets its light counterpart:
`bg-white/60 dark:bg-black/60` · `border-zinc-200 dark:border-white/10` ·
`hover:bg-zinc-100 dark:hover:bg-white/10` · `from-white/80 dark:from-black/80` ·
`text-zinc-900 dark:text-white`.

**Toast above a `backdrop-blur` header (iOS Safari)**

```css
.toast { position: fixed; z-index: 9999; transform: translate3d(0, 0, 0); }
```

## Security headers (example, adjust CSP sources)

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-{random}'; worker-src 'self'; img-src 'self' data: https:; connect-src 'self' https://api.example.com wss://rt.example.com; frame-ancestors 'none'; base-uri 'self'; object-src 'none'
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Cross-Origin-Opener-Policy: same-origin
```

## Performance

- LCP image: `<img src="hero.avif" fetchpriority="high" width="1200" height="600" alt="…">` (never `loading="lazy"` on it).
- bfcache: replace `unload` with `pagehide`; avoid `Cache-Control: no-store` on HTML unless the page holds sensitive data.
- Fonts: `font-display: swap` and `<link rel="preload" as="font" type="font/woff2" crossorigin href="…">`.
- Adaptive loading: `if (navigator.connection?.saveData || /2g/.test(navigator.connection?.effectiveType)) useLowQuality();`

## Manifest snippets

```json
{
  "id": "/",
  "screenshots": [
    { "src": "/s/wide.png", "sizes": "1280x720", "type": "image/png", "form_factor": "wide" },
    { "src": "/s/narrow.png", "sizes": "720x1280", "type": "image/png" }
  ],
  "icons": [
    { "src": "/i/192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/i/512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/i/512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ],
  "launch_handler": { "client_mode": ["navigate-existing", "auto"] },
  "share_target": { "action": "/share", "method": "GET", "params": { "title": "title", "text": "text", "url": "url" } }
}
```
