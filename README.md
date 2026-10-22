# PWA Review Skill for Claude Code

An evidence-based Progressive Web App audit that goes beyond Lighthouse. It scores **11 categories
(209 nominal points)**, grades only the checks that apply to your app, and backs every finding
with a file, line, header or manifest key.

Lighthouse removed its PWA category in v12 (2024). This skill fills that gap and adds what
Lighthouse never covered: iOS/Safari behaviour, update UX, storage durability, real-time
reconnection, Chromium manifest capabilities and response-header security.

## What's new in v6.0.0

- **Evidence collector** (`scripts/collect.py`, Python stdlib only): raw HTML + response headers,
  HTTP→HTTPS redirect and compression probes, manifest + icon reachability, service worker
  discovery (registration code, then common paths) with `importScripts`, up to 25 JS bundles and
  10 stylesheets, `robots.txt`, and ~65 code signals with `file:line` evidence. Security headers
  are now verified instead of "not detectable from HTML".
- **Three modes:** live URL, local source tree (`--source`), or both.
- **Fair scoring:** N/A rules (no dark mode, no real-time, no third-party scripts, …) and
  Unverifiable checks leave the denominator; the grade is the percentage of applicable points.
- **20+ new checks:** zoom not disabled (WCAG 1.4.4), `dvh` units, reduced motion, overscroll,
  bfcache, modern image formats, no-op fetch handler detection, response guard before caching,
  SW `Cache-Control`, SPA navigation fallback, iOS install guidance, standalone detection,
  HTTP→HTTPS redirect, strict CSP, clickjacking protection, indexability, Badging and Web Share.
- **Corrected platform facts:** Chrome no longer needs a fetch handler for menu install, Safari
  storage quota is ~60% of disk (not 50 MB), `persist()` exists in Safari, Declarative Web Push
  (Safari 18.4), iOS 26 home-screen behaviour, `gcm_sender_id` is obsolete, COEP is not a default
  recommendation, `onTouchEnd` backups cause double-fire.
- **Report:** evidence on every finding, fix line, effort estimate, platform notes, and a JSON
  block for tracking scores over time. Written in the user's language.

See [CHANGELOG.md](CHANGELOG.md) for the full list.

## Categories

| Category | Points | What it checks |
|----------|-------:|----------------|
| Manifest Compliance | 22 | Required fields, manifest and icons actually reachable |
| Advanced Manifest | 15 | Screenshots with form factors, shortcuts, id, scope, maskable icon, iOS splash |
| Service Worker & Caching | 35 | Lifecycle, real fetch handling, strategies, expiration, cache hygiene |
| Offline Capability | 24 | Offline + navigation fallback, update UX, storage, sync, real-time resilience |
| Installability | 15 | Chromium criteria, install prompt UI, iOS install guidance |
| Security | 16 | HTTPS redirect, CSP strictness, HSTS, nosniff, Referrer/Permissions-Policy, COOP, framing |
| Performance Signals | 19 | Render blocking, LCP/INP/CLS signals, compression, bfcache, image formats |
| UX & Accessibility | 35 | Viewport, zoom, safe areas, a11y, `dvh`, motion, dropdowns, theming, view state |
| SEO & Discoverability | 8 | Title, description, Open Graph, canonical, JSON-LD, indexability |
| PWA Advanced | 19 | launch/file/protocol handlers, share target, push, badging, Web Share |
| iOS Compatibility | 1 | Bonus for the complete iOS meta set |

**Grade** = earned ÷ applicable points: A+ ≥ 90% · A 80–89% · B 70–79% · C 60–69% · D 40–59% · F < 40%.
With every check applicable: A+ 189+, A 168–188, B 147–167, C 126–146, D 84–125, F < 84.

## Installation

Claude Code loads skills from **directories** (`<skills-dir>/<name>/SKILL.md`). A loose
`pwa-review.md` file in `~/.claude/skills/` is not picked up.

```bash
# Personal (all projects)
git clone https://github.com/NexFabric/pwa-review-skill.git ~/.claude/skills/pwa-review

# Project-level
git clone https://github.com/NexFabric/pwa-review-skill.git .claude/skills/pwa-review
```

Restart Claude Code (or start a new session). Requirements: `python3` (3.9+) for the collector;
no packages to install. Update with `git -C ~/.claude/skills/pwa-review pull`.

## Usage

```
/pwa-review https://your-pwa.com
/pwa-review https://your-pwa.com ~/code/your-app     # live site + source evidence
/pwa-review ./your-app                               # source only, before deploying
```

Claude runs the collector into a temporary evidence folder, confirms signals at `file:line`,
scores each row, and prints the report. You can also run the collector yourself:

```bash
python3 ~/.claude/skills/pwa-review/scripts/collect.py https://your-pwa.com --out /tmp/pwa-ev
python3 ~/.claude/skills/pwa-review/scripts/collect.py --source ./your-app --out /tmp/pwa-src
```

## Sample output

- [Well-built PWA (A+)](examples/sample_report.md) — illustrative, url+source mode
- [Static page, not a PWA (F)](examples/sample_report_bad.md) — from a real run against example.com

```markdown
**Score:** 186/206 applicable points (90.3%) — **Grade: A+**
**Nominal:** 186/209 · N/A: 3 pts · Unverifiable: 0 pts

- **[UX] Zoom disabled** — `index.html:6` `maximum-scale=1, user-scalable=no`
  **Fix:** `width=device-width, initial-scale=1, viewport-fit=cover`
```

## What this covers that Lighthouse does not

| Area | Lighthouse 12+ | PWA Review Skill |
|------|:--------------:|:----------------:|
| PWA category / installability audit | removed | ✅ |
| Manifest + icon reachability, `id`, screenshots form factors | ❌ | ✅ |
| `launch_handler`, `file_handlers`, `protocol_handlers`, `share_target`, `handle_links` | ❌ | ✅ |
| SW lifecycle, no-op fetch handler, strategies, expiration, response guard | ❌ | ✅ |
| Update UX (prompt, `SKIP_WAITING`, no repeat prompt) | ❌ | ✅ |
| Offline + SPA navigation fallback | ❌ | ✅ |
| Storage durability (`persist`, `estimate`, IndexedDB) | ❌ | ✅ |
| Real-time reconnection (visibility, backoff, room re-join) | ❌ | ✅ |
| iOS: safe areas, splash, install guidance, tap reliability, `dvh` | ❌ | ✅ |
| Response-header security (HSTS, CSP strictness, COOP, framing) | partial | ✅ |
| Lab performance metrics (LCP/INP/CLS numbers) | ✅ | signals only — run Lighthouse/CrUX for numbers |

The skill does not execute JavaScript or measure runtime performance. Pair it with Lighthouse or
PageSpeed Insights for lab/field metrics and with Chrome DevTools → Application for a live check.

## Repository layout

```
SKILL.md                     workflow, scoring checklist, report template
scripts/collect.py           evidence collector (stdlib only)
references/platform-notes.md iOS / Safari / Chromium caveats (read on demand)
references/fix-recipes.md    copy-ready fixes for common findings
examples/                    sample reports
tests/                       collector tests against a local fixture PWA
```

Run the tests: `python3 -m unittest discover -s tests`

## Contributing

Issues and PRs welcome. When adding a check: add the row to `SKILL.md` (keep the category totals
in the overview table in sync), add a signal to `scripts/collect.py` if it is detectable from code,
cover it in `tests/`, and record it in `CHANGELOG.md`.

## License

MIT — see [LICENSE](LICENSE).

## Resources

- [Learn PWA | web.dev](https://web.dev/learn/pwa/)
- [Progressive web apps | MDN](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps)
- [Web app manifest | MDN](https://developer.mozilla.org/en-US/docs/Web/Manifest)
- [Service Worker API | MDN](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [Workbox](https://developer.chrome.com/docs/workbox/)
- [Revisiting Chrome's installability criteria](https://developer.chrome.com/blog/update-install-criteria)
- [Updates to Storage Policy | WebKit](https://webkit.org/blog/14403/updates-to-storage-policy/)
- [Meet Declarative Web Push | WebKit](https://webkit.org/blog/16535/meet-declarative-web-push/)

---

**Version:** 6.0.0 · **Author:** [@emrahub](https://github.com/emrahub)
