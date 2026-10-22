# Platform Notes (iOS / Safari / Chromium)

Read this when writing the report's "Platform Notes" section. Include only notes that are
relevant to the audited app. Facts reviewed 2026-10; re-check version numbers when in doubt.

## Lighthouse context

- Lighthouse 12 (2024) removed the PWA category. Lighthouse 11 had already dropped the
  service-worker check from installability. Chrome DevTools → Application → Manifest still shows
  installability errors, which is the quickest manual cross-check.

## Installation

- **Chromium:** install from the menu needs HTTPS + a valid manifest (name/short_name, 192 and
  512 icons, start_url, standalone-type display, `prefer_related_applications` not true). A fetch
  handler stopped being required for menu install in Chrome 108 (Android) / 112 (desktop); the
  automatic install prompt (and `beforeinstallprompt` timing) still uses it as a signal.
- **iOS / iPadOS:** no `beforeinstallprompt`. Users install via Share → Add to Home Screen, so
  the app must show its own instructions. Since iOS / iPadOS 26, every site added to the home
  screen opens as a web app by default (users can untoggle "Open as Web App"); the manifest still
  controls display mode, name and scope.
- **iOS home-screen icon** comes from `<link rel="apple-touch-icon">` (180×180 recommended);
  manifest icons are a fallback only on recent versions.
- **Desktop Safari (macOS Sonoma+):** File → Add to Dock creates a web app from any site.

## Push notifications

- iOS / iPadOS 16.4+: Web Push works **only for home-screen web apps**, after a permission
  request triggered by a user gesture.
- Safari 18.4 (iOS/iPadOS) and 18.5 (macOS) add **Declarative Web Push**: the push payload
  describes the notification, so a service worker is optional and a failed SW cannot drop it.
- `gcm_sender_id` in the manifest is a legacy Firebase/GCM field and does nothing for standard
  Web Push; VAPID keys (`applicationServerKey`) are used client-side, never in the manifest.

## Storage

- Safari 17+: an origin may use up to ~60% of disk in a browser app (overall cap ~80%); a
  home-screen web app has the same quota as in the browser. The old "50 MB" figure is outdated.
- Safari deletes script-writable storage (IndexedDB, localStorage, Cache API, SW registrations)
  of sites without user interaction for 7 days in the browser. Home-screen web apps are exempt
  from that 7-day rule but can still be evicted under storage pressure.
- `navigator.storage.persist()` exists in Safari 15.2+; Safari decides automatically (no
  prompt) and has been reported to return `false` in many cases, so treat it as best effort and
  keep server-side backup for important data. Chromium grants it more readily to installed or
  engaged sites.
- `navigator.storage.estimate()` works in all modern engines; use it to warn before quota runs out.

## Background capabilities

- Background Sync and Periodic Background Sync: **Chromium only**. Periodic sync additionally
  requires an installed app and site engagement; the browser decides the real interval.
- Background Fetch: Chromium only.
- iOS freezes backgrounded web apps: timers stop, WebSockets close (often code 1005/1006), and
  nothing runs until the user returns. Design for "resume", not for "keep alive".

## Real-time connections

- After backgrounding, the socket is dead but the client may not know yet. Listen for
  `visibilitychange` (and `pageshow` for bfcache restores) and reconnect if disconnected.
- socket.io defaults to unlimited attempts in v4, but many apps set `reconnectionAttempts: 5`
  and a short `reconnectionDelayMax`, which are exhausted long before the user returns.
- Server-side room/channel membership is lost on reconnect; re-join inside a persistent
  `connect` listener, not only once on mount.
- SPA navigation unmounts components; persist the identifier of the active view (conversation,
  tab) and reload its data instead of caching the data in localStorage.

## Safe areas and viewport (standalone mode has no browser chrome)

- `env(safe-area-inset-*)` returns 0 unless the viewport meta includes `viewport-fit=cover`.
- Fixed headers: `padding-top: env(safe-area-inset-top)`. Bottom bars:
  `padding-bottom: env(safe-area-inset-bottom)` (home indicator).
- `apple-mobile-web-app-status-bar-style`: `default`, `black`, or `black-translucent` (content
  extends under the status bar — requires the safe-area padding above).
- `100vh` on iOS Safari includes the area under the collapsing toolbar; use `100dvh` (or `svh`)
  with `100vh` as the fallback line before it.
- Disabling zoom (`maximum-scale=1`, `user-scalable=no`) is ignored by iOS Safari since iOS 10
  but honoured by Android browsers and fails WCAG 1.4.4. Prevent focus-zoom on iOS by using
  input font-size ≥ 16px instead.
- `overscroll-behavior: none` (or `contain` on scroll containers) prevents rubber-band and
  pull-to-refresh fighting app gestures in standalone mode.

## Touch and tap

- iOS Safari only dispatches `click` on non-interactive elements (`div`, `span`) when they
  have `cursor: pointer` or an `onclick`; prefer real `<button>` / `<a>` elements.
- The 300 ms tap delay is gone on pages with `width=device-width`; `touch-action:
  manipulation` still removes double-tap-zoom on controls.
- Binding both `onClick` and `onTouchEnd` runs the handler twice unless `touchend` calls
  `preventDefault()` or a guard flag is used. Prefer one handler on a real button.
- `-webkit-tap-highlight-color: transparent` removes the grey flash; provide your own
  `:active` feedback instead.

## Splash screens (iOS)

- iOS does not generate splash screens from the manifest. Without
  `<link rel="apple-touch-startup-image" media="…">` per device size (portrait and landscape),
  launch shows a blank screen in `background_color`-less white. Tools such as
  `pwa-asset-generator` emit the full link set.

## Stacking context (iOS Safari)

- `backdrop-filter` (Tailwind `backdrop-blur-*`) creates a stacking context; fixed toasts or
  dropdowns with a higher `z-index` can still render behind a blurred header in Safari.
- Fix: give the overlay its own compositing layer (`transform: translate3d(0,0,0)`) and a high
  `z-index`, or render it in a portal at the end of `<body>`.

## Chromium-only manifest features (never fail an iOS-only app for these)

`launch_handler`, `file_handlers`, `protocol_handlers`, `share_target`, `handle_links`
(experimental), `scope_extensions` (origin trial), `edge_side_panel` (Edge), `note_taking`
(ChromeOS), `widgets` (Windows 11, experimental), Window Controls Overlay, Badging API on desktop.
Safari supports the Badging API for home-screen apps since iOS 16.4 (with notification permission)
and the Web Share API widely.

## Security headers

- `Cross-Origin-Embedder-Policy: require-corp` is only needed for `SharedArrayBuffer` / high
  resolution timers and breaks third-party embeds; do not recommend it by default.
- The service worker must be served same-origin with a JavaScript MIME type; a CSP that sets
  `worker-src` (or falls back to `script-src`) must allow it.
- Browsers re-check the SW script at most every 24 h regardless of `Cache-Control`, but serving
  `sw.js` with `Cache-Control: no-cache` makes updates immediate on navigation.
