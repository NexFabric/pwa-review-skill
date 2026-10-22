# PWA Review Skill

A portable [Agent Skill](https://agentskills.io) — usable by any AI coding agent that supports skills.

An evidence-based Progressive Web App audit that goes beyond Lighthouse. It scores **11 categories
(209 nominal points)**, grades only the checks that apply to your app, and backs every finding
with a file, line, header or manifest key.

Lighthouse removed its PWA category in v12 (2024). This skill fills that gap and adds what
Lighthouse never covered: iOS/Safari behaviour, update UX, storage durability, real-time
reconnection, Chromium manifest capabilities and response-header security.

## What's new in v6.2

- **Declared vs. delivered:** manifest features (share target, shortcuts, protocol handlers,
  note taking) only score when the app actually handles them, and a suppressed-but-never-offered
  install prompt is flagged.
- Multi-line and optional-chained `sync.register` / `periodicSync.register` calls are detected.

## What's new in v6.1

- **Source audit for theming and menus:** with `--source`, the collector counts Tailwind
  light/dark pairs (overlay, border, hover, gradient, surface, `text-white`) and dropdown
  positioning per line, with `file:line` samples; full-screen scrims are exempt and CSS-variable
  theming is detected. These rows no longer need manual grepping.
- **Service worker discovery for minified registrations:** workbox-window and vite-plugin-pwa
  pass the SW path through a variable; the collector now follows SW-named path literals and
  reports `registration_seen`, so these apps are no longer marked "registration not seen".
- **Collector fixes (6.0.1):** bundler chunk paths resolve against the app base (no more
  `/assets/js/assets/js/…` 404s), a reserved request budget for the SW and `robots.txt`, Firebase
  `vapidKey` push detection, and test files are skipped in source mode.
- Verified against live apps built with Vite + Workbox, vite-plugin-pwa, Angular, Next.js and a
  custom service worker, plus an unreachable host.

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

This is a portable **Agent Skill** in the open [Agent Skills](https://agentskills.io) format: a
folder with `SKILL.md`, `scripts/` and `references/`. Any AI coding agent that loads skills can
use it, and the collector is plain Python, so nothing is tied to one vendor.

**With the skills CLI** (detects your agents and installs into the right folder):

```bash
npx skills add NexFabric/pwa-review-skill
```

**Manually** — clone the folder into your agent's skills directory. Skills are directories
(`<skills-dir>/pwa-review/SKILL.md`); a loose `pwa-review.md` file is not picked up.

```bash
# Shared location read by most agents (personal, all projects)
git clone https://github.com/NexFabric/pwa-review-skill.git ~/.agents/skills/pwa-review

# Project-level
git clone https://github.com/NexFabric/pwa-review-skill.git .agents/skills/pwa-review
```

If your agent reads a different skills folder, clone there instead or symlink the folder into it.

**Agent without skill support:** point it at `SKILL.md` ("follow SKILL.md to audit
https://…"); the workflow, checklist and report template are self-contained.

Restart the agent (or start a new session). Requirements: `python3` (3.9+) for the collector; no
packages to install. Update with `git -C <skills-dir>/pwa-review pull`.

## Where it runs

The full audit needs an agent that can **run Python and reach the internet** (the collector
downloads the page, headers, manifest, service worker and bundles).

| Environment | Support |
|-------------|---------|
| Coding agents with a terminal (CLI agents, IDE agents in agent mode) | ✅ Full audit: collector, source scan, evidence-backed report |
| Chat assistants with a web tool but no shell (e.g. custom GPTs) | ⚠️ Partial: put `SKILL.md` in the instructions/knowledge; sandboxes usually have no internet, so the collector cannot run, and web tools summarise pages — header and code checks are reported as Unverifiable, not guessed |
| Models without tools | ❌ No audit; paste the page HTML, manifest and SW and ask it to apply the checklist manually |

Unverifiable checks leave the denominator, so a partial run gives a smaller but still honest score.

## Usage

```
/pwa-review https://your-pwa.com
/pwa-review https://your-pwa.com ~/code/your-app     # live site + source evidence
/pwa-review ./your-app                               # source only, before deploying
```

The agent runs the collector into a temporary evidence folder, confirms signals at `file:line`,
scores each row, and prints the report. You can also run the collector yourself:

```bash
python3 <skills-dir>/pwa-review/scripts/collect.py https://your-pwa.com --out /tmp/pwa-ev
python3 <skills-dir>/pwa-review/scripts/collect.py --source ./your-app --out /tmp/pwa-src
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

**Version:** 6.2.1 · **Author:** [@emrahub](https://github.com/emrahub)
