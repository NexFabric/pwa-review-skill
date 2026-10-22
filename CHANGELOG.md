# Changelog

## [6.1.1] - 2026-10-22

### Changed
- Documentation is agent-neutral: the skill follows the open Agent Skills format and works with
  any AI coding agent that loads skills. Installation now covers the skills CLI
  (`npx skills add`), the shared `~/.agents/skills` folder, and agents without skill support.

---

## [6.1.0] - 2026-10-22

### Added
- `summary.source_audit` (source mode): Tailwind theme-pair counts per rule (`overlay`, `border`,
  `hover`, `gradient`, `surface`, `text_white`) with unpaired totals and `file:line` samples,
  dropdown positioning (`candidates`, `mobile_safe`, samples) and `css_var_theme_tokens`.
  Full-screen scrims (`fixed inset-0`, `backdrop`) are exempt from the overlay rule.
- Service worker discovery follows SW-named path literals in client code (minified
  workbox-window / vite-plugin-pwa registrations) before probing common paths;
  `service_worker.registration_seen` records whether registration code was found.

### Changed
- SKILL.md: theme and dropdown rows score from `source_audit` and require checking samples;
  without `--source` they are Unverifiable. SW registration row uses `registration_seen`.

### Verified
- Live runs: Vite + custom SW, vite-plugin-pwa (Workbox), Next.js, Angular (SPA catch-all
  correctly rejected as SW), a redirecting host, and an unreachable host.

---

## [6.0.1] - 2026-10-22

### Fixed
- Collector resolved bare bundler chunk paths (`assets/js/x.js`, Vite preload deps) against the
  importing chunk, producing `/assets/js/assets/js/…` 404s that exhausted the request budget
  before the service worker and `robots.txt` were fetched. Bare paths now resolve against the
  app base; only `./` and `../` are module-relative.
- Bundle crawl now stops after `--max-bundles` failures and keeps 15 requests in reserve for the
  service worker, its imports, path probes and `robots.txt` (budget raised 60 → 80).

### Changed
- Web Push signal also recognises Firebase `getToken({ vapidKey })`.
- Source mode skips test directories (`tests`, `__tests__`, `e2e`, …) and `*.test.*` / `*.spec.*`
  / `*.stories.*` files.

Found by auditing a production Vite + socket.io PWA with the v6.0.0 skill.

---

## [6.0.0] - 2026-10-22

### Breaking
- **Scoring moved to 209 nominal points, graded on applicable points.** N/A groups (real-time,
  dark-mode pairs, dropdowns, touch double-fire, SRI, SPA view state, `note_taking`) and
  Unverifiable checks leave the denominator; grade = earned ÷ applicable. Scores are not
  comparable with v5 reports.
- Category totals: Manifest 20→22, Service Worker 33→35, Installability 13→15,
  Performance 17→19, UX 29→35, SEO 7→8, PWA Advanced 17→19 (Advanced Manifest 15, Offline 24,
  Security 16, iOS 1 unchanged).
- Frontmatter uses standard skill fields (`argument-hint`, `allowed-tools`); the unsupported
  `user_invocable` / `args` keys were removed.

### Added
- `scripts/collect.py` evidence collector (stdlib only): raw HTML + headers, HTTP→HTTPS and
  compression probes, manifest and icon reachability, SW discovery via registration code or
  common paths, `importScripts`, two-level same-origin bundle crawl, stylesheets, `robots.txt`,
  ~65 code signals with `file:line` snippets. Source mode (`--source`) scans a local project.
- `references/platform-notes.md` (iOS/Safari/Chromium caveats) and `references/fix-recipes.md`
  (copy-ready fixes), read on demand.
- Tests against a local fixture PWA (`python3 -m unittest discover -s tests`).
- New checks — Manifest: manifest reachable/valid (+1), icons reachable (+1). Advanced manifest:
  `start_url` inside `scope` (replaces `widgets`). Service worker: response guard before caching
  (+1), SW script not long-cached (+1), precache revisioning (replaces "Workbox bonus").
  Offline: SPA navigation fallback (+1). Installability: iOS install guidance (+1), standalone
  detection (+1). Security: HTTP→HTTPS redirect (replaces duplicate HTTPS row), strict CSP
  partial credit, clickjacking protection (COEP no longer scored). Performance: bfcache
  friendliness (+1), modern image formats (+1). UX: zoom not disabled (+2), dynamic viewport units
  (+1), reduced motion (+1), overscroll control (+1), colour-scheme signals (+1); touch double-fire
  moved here from Offline. SEO: indexability (+1). PWA Advanced: Badging API (+1), Web Share
  API (+1).
- Report: evidence on every finding, fix line, effort, N/A/Unverifiable lines, platform notes,
  machine-readable JSON block, written in the user's language.

### Changed
- Fetch handler that never calls `respondWith` scores 0 (no-op handlers slow navigation).
- Screenshots: full credit needs a `wide` and a narrow form factor.
- "Touch event handling for iOS" became "Tap reliability" (`<button>`/`cursor: pointer`,
  `touch-action: manipulation`); `onTouchEnd` backups are no longer recommended.
- Web Push: VAPID `applicationServerKey` or Declarative Web Push; `gcm_sender_id` no longer counts.
- ARIA presence 2→1 point; `handle_links` documented as experimental.
- README installation fixed: skills are directories (`<skills-dir>/pwa-review/SKILL.md`).
- Example reports rewritten in the v6 format; the failing example comes from a real run.

### Fixed
- Error handling referenced "Advanced Manifest 0/13" (category is 15 points).
- Example usage said "10 categories" (there are 11).
- Outdated platform facts: Safari storage quota (~60% of disk, not 50 MB), `persist()` exists in
  Safari 15.2+, Chrome menu install no longer needs a fetch handler (108/112), Lighthouse 12
  removed the PWA category, socket.io v4 defaults to unlimited reconnection attempts, iOS 26 opens
  every home-screen site as a web app.

---

## [5.5.0] - 2026-02-28

### Added

#### Real-Time Connection Resilience (+5 points in Offline Capability)
- **Visibility change reconnection** (+2 pts) — Detects `visibilitychange` event listener that triggers WebSocket/real-time reconnection when the page becomes visible again. Critical for mobile PWAs where backgrounding kills WebSocket connections.
- **Real-time reconnection strategy** (+2 pts) — Detects `reconnectionAttempts` configuration (should be high or `Infinity`) with progressive backoff (`reconnectionDelayMax`). Also checks for manual retry UI and `reconnect_failed` event handling.
- **Connection room re-subscribe** (+1 pt) — Detects persistent `connect` event listener that re-joins rooms/channels after reconnection, not just on initial connection. Without this, real-time events stop flowing after reconnection.

#### SPA State Persistence (+2 points in UX & Accessibility)
- **SPA view state persistence** (+2 pts) — Detects localStorage persistence of active view/tab/conversation IDs so users don't lose their position when navigating away and back. Includes graceful handling of stale IDs (e.g., 404 responses for deleted resources).

### Changed
- **Total scoring increased from 185 to 192 points**
- Offline Capability: 19 → 24 points
- UX & Accessibility: 27 → 29 points
- Updated grading scale thresholds:
  - A+: 173+ points (90%+)
  - A: 154-172 points (80-89%)
  - B: 135-153 points (70-79%)
  - C: 116-134 points (60-69%)
  - D: 77-115 points (40-59%)
  - F: <77 points (<40%)

### Notes
Based on real-world PWA mobile UX bugs discovered during OryoNex production use:
- Mobile PWA users frequently switch between apps; WebSocket connections die silently with close code 1005
- Default socket.io config (5 reconnection attempts, 5s max delay) is exhausted in ~15 seconds — user may be away for hours
- After WebSocket reconnection, server-side room memberships are lost; events stop flowing unless rooms are re-joined
- SPA navigation (back button, gesture, tab switch) unmounts components and destroys state; users return to empty views
- These patterns are universal to any PWA with real-time features (chat, collaboration, notifications)

---

## [5.4.0] - 2026-02-07

### Added

#### Service Worker & Caching Enhancements (+4 points)
- **Multiple caching strategies** (+2 pts) — Detects usage of different strategies (CacheFirst, NetworkFirst, StaleWhileRevalidate) for different resource types
- **Cache expiration config** (+1 pt) — Detects `maxEntries` or `maxAgeSeconds` for cache pruning
- **SW message handler** (+1 pt) — Detects `addEventListener('message', ...)` for client-SW communication

#### Offline Capability Enhancements (+2 points)
- **Background sync client trigger** (+1 pt) — Detects `registration.sync.register()` call when coming back online
- **Periodic sync registration** (+1 pt) — Detects `registration.periodicSync.register()` on app initialization

#### Performance Signals Enhancement (+1 point)
- **Network Information API usage** (+1 pt) — Detects `navigator.connection` for adaptive behavior on slow networks

### Changed
- **Total scoring increased from 178 to 185 points**
- Service Worker & Caching: 29 → 33 points
- Offline Capability: 17 → 19 points
- Performance Signals: 16 → 17 points
- Updated grading scale thresholds:
  - A+: 167+ points (90%+)
  - A: 148-166 points (80-89%)
  - B: 130-147 points (70-79%)
  - C: 111-129 points (60-69%)
  - D: 74-110 points (40-59%)
  - F: <74 points (<40%)

### Notes
Based on LookNex PWA deep dive analysis and real-world implementation gaps:
- Many PWAs have sync handlers in SW but never trigger sync from client
- Periodic sync requires explicit client-side registration with permission check
- Network Information API enables adaptive UX on 2G/3G/saveData connections
- Production PWAs need different caching strategies per resource type
- Cache expiration prevents unbounded storage growth

---

## [5.3.0] - 2026-02-07

### Added

#### Offline Storage Enhancements (+3 points in Offline Capability)
- **Persistent storage request** (+1 pt) — Detects `navigator.storage.persist()` for iOS data persistence prevention
- **IndexedDB offline storage** (+1 pt) — Detects `indexedDB.open()` or `idb` library for structured offline data management
- **Storage quota monitoring** (+1 pt) — Detects `navigator.storage.estimate()` for storage health checks and warnings

#### Performance Optimizations (+2 points in Performance Signals)
- **Compression headers** (+1 pt) — Note about `Content-Encoding: gzip/br` verification via DevTools
- **Bundle chunking strategy** (+1 pt) — Detects `manualChunks`, vendor splitting, or runtime chunk patterns

### Changed
- **Total scoring increased from 173 to 178 points**
- Offline Capability: 14 → 17 points
- Performance Signals: 14 → 16 points
- Updated grading scale thresholds:
  - A+: 161+ points (90%+)
  - A: 143-160 points (80-89%)
  - B: 125-142 points (70-79%)
  - C: 107-124 points (60-69%)
  - D: 72-106 points (40-59%)
  - F: <72 points (<40%)

### Notes
Based on Flutter PWA optimization article and LookNex production implementation:
- `navigator.storage.persist()` prevents iOS from evicting PWA data after 7 days of inactivity
- IndexedDB enables offline storage for images, generation history, and complex data structures
- `navigator.storage.estimate()` helps warn users before storage quota is exceeded
- Gzip/Brotli compression can reduce bundle sizes by 60-80%
- Vendor chunking improves caching efficiency and parallel loading

---

## [5.2.0] - 2026-02-06

### Added

#### Extended Theme Pattern Checks (+5 points in UX & Accessibility)
- **Dark overlay theme pairs** (+1 pt) — Detects `bg-black/X` patterns that need `dark:` prefix (e.g., `bg-white/60 dark:bg-black/60`)
- **Border visibility pairs** (+1 pt) — Detects `border-white/X` that needs light alternative (e.g., `border-zinc-200 dark:border-white/10`)
- **Hover state theme pairs** (+1 pt) — Detects hover backgrounds missing dual variants (e.g., `hover:bg-zinc-100 dark:hover:bg-white/10`)
- **Gradient theme support** (+1 pt) — Detects gradient stops without theme variants (e.g., `from-white/80 dark:from-black/80`)
- **Contextual text-white** (+1 pt) — Detects white text on non-colored/transparent backgrounds

### Changed
- **Total scoring increased from 168 to 173 points**
- UX & Accessibility: 22 → 27 points
- Updated grading scale thresholds:
  - A+: 156+ points (90%+)
  - A: 139-155 points (80-89%)
  - B: 122-138 points (70-79%)
  - C: 104-121 points (60-69%)
  - D: 70-103 points (40-59%)
  - F: <70 points (<40%)

### Notes
These additions are based on real-world theme issues discovered during LookNex PWA production testing:
- `bg-black/60` overlays invisible/wrong in light mode
- `border-white/10` borders invisible in light mode
- `hover:bg-black/10` hover states not visible in light mode
- `from-black/80` gradients incorrect in light mode
- `text-white` on transparent overlays unreadable in light mode

Alpha/opacity colors are commonly used for dark mode but require explicit light mode counterparts.

---

## [5.1.0] - 2026-02-05

### Added

#### Mobile Dropdown Positioning (+3 points in UX & Accessibility)
- **Mobile dropdown positioning** (+2 pts) — Detects `fixed sm:absolute` pattern for dropdowns that break out of positioning context on mobile
- **Dropdown safe area handling** (+1 pt) — Detects `safe-area-inset-right/left` application for notch devices

#### Update State Management (+2 points in Offline Capability)
- **Update state persistence** (+1 pt) — Detects localStorage flags (e.g., `pwa-just-updated`) to prevent update prompt re-appearing immediately after update
- **Touch event double-fire prevention** (+1 pt) — Detects guards against duplicate execution from onClick + onTouchEnd

#### Theme Consistency (+2 points in UX & Accessibility)
- **Light/dark theme consistency** (+2 pts) — Verifies UI elements have both light and `dark:` variants in Tailwind CSS

### Changed
- **Total scoring increased from 161 to 168 points**
- Offline Capability: 12 → 14 points
- UX & Accessibility: 17 → 22 points

### Notes
These additions are based on real-world iOS PWA issues discovered during production app testing:
- Dropdown positioning with `absolute` relative to narrow containers causes viewport overflow on mobile
- Update prompts re-appearing after user clicks "Update" due to missing state persistence
- Hardcoded dark colors appearing incorrectly in light theme

---

## [5.0.2] - 2026-02-05

### Added
- **Notification action buttons** (+1 pt) — Detects push notifications with actionable buttons (`actions` array) or `event.action` handling in notificationclick. Enables richer user interactions directly from notifications.

### Changed
- **Total scoring increased from 160 to 161 points**
- Service Worker & Caching: 28 → 29 points

---

## [5.0.1] - 2026-02-05

### Added
- **cursor: pointer best practice** — Added to Touch Events & Interactions section. iOS Safari requires `cursor: pointer` CSS on interactive elements to recognize them as clickable. Without this, click/touch events may not fire reliably in PWA mode.

---

## [5.0.0] - 2026-02-04

### Added

#### iOS Safe Area Support (+4 points in UX & Accessibility)
- **viewport-fit=cover check** (+2 pts) — Required for iPhone notch/Dynamic Island safe area access
- **Safe area CSS usage** (+2 pts) — Detects `env(safe-area-inset-*)` usage for fixed elements

#### iOS Splash Screens (+2 points in Advanced Manifest)
- **apple-touch-startup-image detection** (+2 pts) — iOS requires separate splash images for each device size

#### Touch Event Handling (+1 point in UX & Accessibility)
- **Touch event handlers** (+1 pt) — Detects `onTouchEnd` handlers and `touch-manipulation` CSS for iOS compatibility

#### Update UX (+2 points in Offline Capability)
- **Update prompt shown to user** (+1 pt) — Detects SW update notification patterns
- **Graceful update flow** (+1 pt) — Detects user-controlled update implementation

#### iOS Compatibility Bonus (+1 point, new category)
- **Complete iOS meta tag set** (+1 pt) — Bonus for having all iOS-specific meta tags

#### Enhanced iOS/Safari Documentation
- Comprehensive safe area handling guidance
- Touch event best practices for iOS PWA mode
- Splash screen requirements and media query patterns
- **backdrop-filter stacking context warning** — iOS Safari creates isolated stacking contexts for elements with backdrop-blur, causing z-index issues. Solution: use `transform: translate3d(0,0,0)` to force GPU layer

### Changed
- **BREAKING**: Total scoring increased from 150 to **160 points**
- UX & Accessibility: 12 → 17 points
- Advanced Manifest: 13 → 15 points
- Offline Capability: 10 → 12 points
- Added new Category 11: iOS Compatibility (1 point bonus)
- Updated grading scale thresholds:
  - A+: 144+ points (90%+)
  - A: 128-143 points (80-89%)
  - B: 112-127 points (70-79%)
  - C: 96-111 points (60-69%)
  - D: 64-95 points (40-59%)
  - F: <64 points (<40%)
- Expanded iOS/Safari limitations section with practical implementation guidance
- Added warnings for missing safe area handling and iOS splash screens

### Why This Version

This release focuses on iOS and mobile compatibility, addressing real-world issues discovered during PWA development:

1. **iPhone Notch/Dynamic Island**: Without proper safe area handling, content is obscured in PWA mode
2. **Touch Events**: `onClick` handlers don't always fire on iOS PWAs — `onTouchEnd` is essential
3. **Splash Screens**: iOS shows blank white screen without proper startup images
4. **Update UX**: Users should be notified of updates and control when they're applied

These checks ensure PWAs work correctly on iPhones, which represent a significant portion of mobile users.

---

## [4.0.0] - 2026-02-04

### Added

#### Service Worker & Caching (+6 points, now 28 total)
- **skipWaiting() usage** (+1 pt) — Detects `self.skipWaiting()` for instant SW activation
- **clients.claim() usage** (+1 pt) — Detects `clients.claim()` for immediate control
- **Navigation preload** (+1 pt) — Detects `navigationPreload.enable()` usage
- **Stale-while-revalidate pattern** (+1 pt) — Detects SWR caching strategy
- **Push event handler** (+1 pt) — Detects `addEventListener('push', ...)`
- **notificationclick handler** (+1 pt) — Detects `addEventListener('notificationclick', ...)`

#### Installability (+3 points, now 13 total)
- **beforeinstallprompt handled** (+2 pts) — Detects install prompt event listener
- **Custom install UI** (+1 pt) — Detects custom install button implementation

#### Security (+4 points, now 16 total)
- **HSTS header** (+1 pt) — Strict-Transport-Security check (note only, not detectable from HTML)
- **X-Content-Type-Options** (+1 pt) — nosniff header check
- **Referrer-Policy** (+1 pt) — Appropriate referrer policy
- **Permissions-Policy** (+1 pt) — Feature policy definition

#### Performance Signals (+4 points, now 14 total)
- **LCP optimization signals** (+1 pt) — Hero image preload, above-fold prioritization
- **INP optimization signals** (+1 pt) — Event handler optimization indicators
- **CLS prevention** (+1 pt) — Image dimensions, layout shift prevention
- **Critical CSS inlined** (+1 pt) — Critical styles in head or preloaded

#### UX & Accessibility (+2 points, now 12 total)
- **Focus indicators visible** (+1 pt) — :focus styles not removed
- **Skip to main content link** (+1 pt) — Skip link for keyboard navigation

#### Advanced Manifest (+2 points, now 13 total)
- **note_taking object** (+1 pt) — ChromeOS lock screen notes integration
- **widgets array** (+1 pt) — Windows 11 Widgets Board integration

#### PWA Advanced (+2 points, now 17 total)
- **Web Push configured** (+1 pt) — VAPID or gcm_sender_id in manifest
- **Notification permission UX** (+1 pt) — Permission timing best practice

### Changed
- **BREAKING**: Total scoring increased from 127 to **150 points**
- Updated grading scale thresholds:
  - A+: 135+ points (90%+)
  - A: 120-134 points (80-89%)
  - B: 105-119 points (70-79%)
  - C: 90-104 points (60-69%)
  - D: 60-89 points (40-59%)
  - F: <60 points (<40%)
- Report template updated for new category point totals
- Error handling updated for new SW category total (0/28)
- Issue classification expanded with new warning items

### Migration Notes
- Existing scores cannot be directly compared to v4.0.0 scores
- A "good" PWA that scored 112/127 (88%) might score ~130/150 (87%) with new checks
- New checks are additive — existing functionality still earns the same points

---

## [3.1.1] - 2026-02-04

### Fixed
- Critical Blocker text: "0/20" → "0/22" for Service Worker category (2 places)
- Background Sync check now includes `periodicsync` event detection

---

## [3.1.0] - 2026-02-04

### Added
- **Background Sync check** in Service Worker category (+2 pts) — detects `sync` event listener for offline queue processing
- **COOP/COEP check** in Security category (+2 pts) — Cross-Origin Isolation headers required for SharedArrayBuffer

### Changed
- Total scoring increased from 123 to **127 points**
- Service Worker & Caching: 20 → 22 points
- Security Measures: 10 → 12 points
- Updated grading scale thresholds for new point total
- Synchronized version numbers across all files (was showing v2.3 in some places)

### Fixed
- Version consistency: All files now show v3.1.0
- Updated sample reports to reflect new scoring structure

---

## [3.0.0] - 2026-02-04

### Changed
- **BREAKING**: Converted from Python scripts to a native agent skill format
- Embedded complete 123-point checklist directly in SKILL.md
- Added YAML frontmatter for proper skill registration (`user_invocable: true`)
- Added executable workflow instructions for the agent (WebFetch-based)
- Updated README with new installation and usage instructions
- Expanded to 10 categories (123 total points)

### Added
- Detailed error handling documentation
- iOS/Safari limitation notes
- Report template with exact output format
- Category-by-category scoring tables

### Removed
- Python scripts (`discover_pwa.py`, `analyze_pwa.py`, `generate_report.py`) — no longer needed
- Separate `references/pwa-checklist.md` — now embedded in SKILL.md

### Why This Change
- Zero dependencies: Works directly in the agent without Python
- Single command: Just run `/pwa-review <url>`
- Better CORS handling: the agent's web fetch tool handles cross-origin requests
- Self-contained: All checklist items and instructions in one file

---

## [2.1.0] - 2026-02-04

### Added
- **How-to-Fix code snippets** for every finding — actionable fix instructions in report
- **Quick Wins section** — top 5 easiest fixes highlighted
- **Reference Links** — MDN, web.dev links per category
- **prefer_related_applications check** — CRITICAL installability blocker
- **Push/BackgroundSync detection** — push, notificationclick, sync, periodicsync
- **skipWaiting/clients.claim** — SW update lifecycle detection
- **Sensitive data warning** — token/auth/password keywords in SW
- **Navigation preload** detection
- **launch_handler, scope_extensions** manifest fields
- **Window Controls Overlay** specific display_override detection
- **apple-mobile-web-app-capable** scoring in installability

### Fixed
- discover_pwa.py: eliminated redundant double function calls
- README.md: "6 categories" → "8 categories"
- Font swap: now catches `display=swap` in Google Fonts URLs
- CSP note: clearer about HTTP header CSP being preferred

## [2.0.0] - 2025-02-04

### Added
- 🔒 **Security category** (10 pts) — CSP, SRI, mixed content, SW scope restriction, error handling
- 🧩 **Advanced Manifest category** (10 pts) — screenshots, shortcuts, categories, display_override, share_target, protocol_handlers, file_handlers
- beforeinstallprompt detection
- Workbox library detection
- Theme color meta tag check (separate from manifest)
- Maskable icon detail messaging

### Changed
- Rebalanced scoring to 100 pts across 8 categories (was 6)
- Removed free points for compression and touch-friendliness (can't verify from static HTML)
- More realistic scoring — good PWAs now score ~80-90 instead of inflated 99
- Improved cache strategy detection with Workbox support
- Better SRI checking with external resource ratio analysis
- Enhanced CSP analysis (unsafe-inline, unsafe-eval detection)

### Fixed
- Performance category no longer awards points for unverifiable checks
- UX category scoring proportional to actual detectable features

## [1.0.0] - 2025-02-04

### Added
- Initial release with 6 categories
