#!/usr/bin/env python3
"""Collect raw PWA evidence for the pwa-review skill.

Fetches the page, response headers, manifest, icons, service worker (plus its
importScripts), same-origin JS/CSS bundles and robots.txt, then scans all of it
(and optionally a local source tree) for the code signals the checklist scores.

Raw bytes are saved so every finding can cite a file. WebFetch is not used
because it summarizes pages through a model and drops <head> tags and headers.

Usage:
  collect.py URL [--out DIR] [--source DIR] [--max-bundles N] [--timeout S]
  collect.py --source DIR --out DIR          (source-only mode)

Standard library only. Exit code 0 even when the site is not a PWA; the
summary records what is missing. Exit 2 only on bad arguments.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
import zlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36 pwa-review/6"
)
MAX_BYTES = 5 * 1024 * 1024
MAX_REQUESTS = 80
# Requests kept back for the SW, its imports, path probes and robots.txt.
RESERVED_REQUESTS = 15

SECURITY_HEADERS = [
    "content-security-policy",
    "strict-transport-security",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
    "cross-origin-opener-policy",
    "cross-origin-embedder-policy",
    "cross-origin-resource-policy",
    "x-frame-options",
    "cache-control",
    "content-type",
    "content-encoding",
    "alt-svc",
]

SW_PROBE_PATHS = [
    "/sw.js",
    "/service-worker.js",
    "/serviceworker.js",
    "/sw.mjs",
    "/ngsw-worker.js",
    "/firebase-messaging-sw.js",
]

# name -> regex. Each signal maps to one or more checklist rows in SKILL.md.
# Patterns must survive minification (string literals and API names do).
SIGNALS: dict[str, str] = {
    # Service worker lifecycle and caching
    "sw_register": r"serviceWorker\s*\.\s*register\s*\(|new\s+Workbox\s*\(|registerSW\s*\(|useRegisterSW|ServiceWorkerModule\.register|provideServiceWorker\s*\(",
    "sw_install": r"addEventListener\(\s*['\"]install['\"]|\boninstall\s*=",
    "sw_activate": r"addEventListener\(\s*['\"]activate['\"]|\bonactivate\s*=",
    "sw_fetch": r"addEventListener\(\s*['\"]fetch['\"]|\bonfetch\s*=|registerRoute\s*\(",
    "sw_respond_with": r"\.respondWith\s*\(|registerRoute\s*\(",
    "sw_sync": r"addEventListener\(\s*['\"](?:periodic)?sync['\"]|BackgroundSyncPlugin|BackgroundSyncQueue",
    "sw_push": r"addEventListener\(\s*['\"]push['\"]",
    "sw_notificationclick": r"addEventListener\(\s*['\"]notificationclick['\"]",
    "sw_message": r"addEventListener\(\s*['\"]message['\"]",
    "notif_actions": r"\bactions\s*:\s*\[|event\.action\b|\.action\s*===",
    "cache_api": r"caches\s*\.\s*(?:open|match|keys|delete|has)\s*\(|\.put\s*\(\s*\w+\s*,\s*\w+\.clone\(\)",
    "cache_version_name": r"CACHE_(?:NAME|VERSION)|cacheName\s*:|-v\d+['\"]|cacheId\s*:",
    "cache_cleanup": r"caches\.delete\s*\(|cleanupOutdatedCaches",
    "skip_waiting": r"skipWaiting\s*\(",
    "clients_claim": r"clients\.claim\s*\(|clientsClaim",
    "nav_preload": r"navigationPreload",
    "strategy_cache_first": r"CacheFirst|cache-first|cacheFirst",
    "strategy_network_first": r"NetworkFirst|network-first|networkFirst",
    "strategy_swr": r"StaleWhileRevalidate|stale-?while-?revalidate|staleWhileRevalidate",
    "expiration": r"maxEntries|maxAgeSeconds|ExpirationPlugin",
    "precache": r"precacheAndRoute|__WB_MANIFEST|\.addAll\s*\(|__precacheManifest|ngsw",
    "precache_revision": r"revision\s*:|__WB_MANIFEST|precacheAndRoute|\.[0-9a-f]{8,}\.(?:js|css)",
    "response_guard": r"\.ok\b|\.status\s*={2,3}\s*200|CacheableResponsePlugin|statuses\s*:|\.type\s*={2,3}\s*['\"]opaque|method\s*!={1,2}\s*['\"]GET",
    "navigate_fallback": r"mode\s*={2,3}\s*['\"]navigate['\"]|NavigationRoute|navigateFallback|createHandlerBoundToURL|request\.destination\s*={2,3}\s*['\"]document",
    "offline_page": r"offline\.html|['\"]/offline['\"/]|setCatchHandler|offlineFallback",
    # Offline, update and storage (client side)
    "online_offline": r"navigator\.onLine|addEventListener\(\s*['\"](?:online|offline)['\"]",
    "update_prompt": r"onNeedRefresh|needRefresh|updatefound|controllerchange|registration\.waiting|\.waiting\b|SKIP_WAITING|onupdatefound",
    "update_flag": r"just[-_]?updated|justUpdated|pwa[-_]updated|update[-_]?dismissed",
    "persist": r"storage\.persist\s*\(",
    "indexeddb": r"indexedDB\.open|['\"]idb['\"]|idb-keyval|Dexie|localforage|openDB\s*\(",
    "quota": r"storage\.estimate\s*\(",
    "sync_register": r"sync\.register\s*\(",
    "periodic_register": r"periodicSync\.register\s*\(",
    # Real-time resilience
    "realtime": r"new\s+WebSocket\s*\(|socket\.io|new\s+EventSource\s*\(|reconnectionAttempts|new\s+Pusher\s*\(|\.subscribe\(\s*['\"]realtime|supabase\.channel\s*\(",
    "visibility": r"visibilitychange",
    "reconnect_cfg": r"reconnectionAttempts|reconnectionDelayMax|reconnect_failed|reconnectInterval|maxReconnect",
    # Install experience
    "bip": r"beforeinstallprompt",
    "appinstalled": r"appinstalled",
    "display_mode": r"display-mode\s*:\s*standalone|navigator\.standalone",
    "ios_install_hint": r"(?i)add to home ?screen|ana ekrana ekle|addToHomeScreen|ios-install",
    "related_apps_api": r"getInstalledRelatedApps",
    # UX / layout
    "safe_area": r"safe-area-inset",
    "dvh": r"\d+(?:d|s|l)vh\b|\b(?:min-|max-)?h-(?:dvh|svh|lvh)\b",
    "vh100": r"100vh|\bh-screen\b|\bmin-h-screen\b",
    "reduced_motion": r"prefers-reduced-motion|motion-reduce|motion-safe",
    "dark_mode": r"prefers-color-scheme\s*:\s*dark|\.dark\s|\.dark\\:|\bdark:|data-theme|\[data-mode|light-dark\(|color-scheme\s*:[^;}]*dark",
    "color_scheme": r"color-scheme",
    "touch_manipulation": r"touch-action\s*:\s*manipulation|touch-manipulation",
    "touchend": r"onTouchEnd|['\"]touchend['\"]",
    "overscroll": r"overscroll-behavior|overscroll-(?:none|contain)",
    "cursor_pointer": r"cursor\s*:\s*pointer|cursor-pointer",
    "fixed_dropdown_mobile": r"fixed\s+sm:absolute|fixed\s+md:absolute",
    "localstorage_set": r"localStorage\.setItem\s*\(",
    "unsafe_zoom": r"user-scalable\s*=\s*(?:no|0)|maximum-scale\s*=\s*1(?:\.0)?\b",
    # Performance
    "net_info": r"navigator\.connection|effectiveType|saveData",
    "dynamic_import": r"\bimport\s*\(\s*['\"`]",
    "unload_listener": r"addEventListener\(\s*['\"]unload['\"]|\bonunload\s*=",
    "font_display": r"font-display\s*:\s*(?:swap|optional|fallback)|display=(?:swap|optional)",
    "manual_chunks": r"manualChunks|splitChunks|vendor[-.][0-9a-f]+\.js",
    "speculation_rules": r"speculationrules",
    # Advanced capabilities
    "push_subscribe": r"pushManager\.subscribe\s*\(|applicationServerKey|vapidKey",
    "notif_permission": r"Notification\.requestPermission|requestPermission\s*\(",
    "badging": r"setAppBadge|clearAppBadge",
    "web_share": r"navigator\.share\s*\(|navigator\.canShare",
    "view_transitions": r"startViewTransition|@view-transition",
    "launch_queue": r"launchQueue",
}

SW_LITERAL_RX = re.compile(
    r"""["'`]((?:\.{0,2}/)?(?:[\w.-]+/)*(?:sw|service-?worker|serviceworker|ngsw-worker|firebase-messaging-sw)\.m?js)["'`]""")
JS_REF_RX = re.compile(r"""["'`]((?:\.{0,2}/)?[\w@./-]+\.m?js)["'`]""")

SOURCE_EXT = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".astro",
    ".css", ".scss", ".sass", ".less", ".html", ".htm", ".json", ".webmanifest",
}
SOURCE_SKIP_DIRS = {
    "node_modules", ".git", ".next", ".nuxt", ".svelte-kit", ".turbo", ".cache",
    "dist", "build", "out", "coverage", ".vercel", ".output", "vendor", "__pycache__",
    "__tests__", "tests", "test", "e2e", "cypress", "playwright",
}
TEST_FILE_RX = re.compile(r"\.(?:test|spec|stories)\.[cm]?[jt]sx?$")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


class Fetcher:
    def __init__(self, timeout: float):
        self.timeout = timeout
        self.count = 0
        self.opener = build_opener()
        self.no_redirect = build_opener(_NoRedirect)
        self.log: list[dict] = []

    def get(self, url: str, *, follow: bool = True, accept_encoding: str = "gzip, deflate",
            head_only: bool = False) -> dict:
        if self.count >= MAX_REQUESTS:
            return {"url": url, "error": "request budget exhausted"}
        self.count += 1
        req = Request(url, headers={"User-Agent": UA, "Accept-Encoding": accept_encoding,
                                    "Accept": "*/*"},
                      method="HEAD" if head_only else "GET")
        opener = self.opener if follow else self.no_redirect
        try:
            with opener.open(req, timeout=self.timeout) as resp:
                status = resp.status
                final_url = resp.geturl()
                headers = {k.lower(): v for k, v in resp.headers.items()}
                raw = b"" if head_only or accept_encoding.startswith("br") else resp.read(MAX_BYTES + 1)
        except HTTPError as e:
            status = e.code
            final_url = url
            headers = {k.lower(): v for k, v in (e.headers or {}).items()}
            raw = b""
            if not head_only:
                try:
                    raw = e.read(MAX_BYTES + 1)
                except Exception:  # body of an error response is optional evidence
                    raw = b""
            e.close()
        except (URLError, TimeoutError, OSError, ValueError) as e:
            entry = {"url": url, "error": f"{type(e).__name__}: {getattr(e, 'reason', e)}"}
            self.log.append(entry)
            return entry
        truncated = len(raw) > MAX_BYTES
        body = _decode(raw[:MAX_BYTES], headers.get("content-encoding", ""))
        entry = {"url": url, "final_url": final_url, "status": status, "headers": headers,
                 "bytes": len(body), "truncated": truncated}
        self.log.append({k: v for k, v in entry.items() if k != "headers"})
        entry["body"] = body
        return entry


def _decode(raw: bytes, encoding: str) -> bytes:
    enc = encoding.lower().strip()
    try:
        if enc == "gzip":
            return gzip.decompress(raw)
        if enc == "deflate":
            return zlib.decompress(raw)
    except (OSError, zlib.error, EOFError):
        return raw
    return raw


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[dict] = []
        self.metas: list[dict] = []
        self.scripts: list[dict] = []
        self.imgs: list[dict] = []
        self.sources: list[dict] = []
        self.anchors: list[str] = []
        self.html_attrs: dict = {}
        self.tags: dict[str, int] = {}
        self.aria_or_role = 0
        self.title = ""
        self.noscript = False
        self.inline_styles: list[str] = []
        self._in_script: dict | None = None
        self._in_title = False
        self._in_style = False
        self._in_head = False
        self._head_scripts: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v if v is not None else "") for k, v in attrs}
        self.tags[tag] = self.tags.get(tag, 0) + 1
        if any(k == "role" or k.startswith("aria-") for k in a):
            self.aria_or_role += 1
        if tag == "html":
            self.html_attrs = a
        elif tag == "head":
            self._in_head = True
        elif tag == "body":
            self._in_head = False
        elif tag == "link":
            self.links.append(a)
        elif tag == "meta":
            self.metas.append(a)
        elif tag == "script":
            entry = dict(a, _inline="", _in_head=self._in_head)
            self.scripts.append(entry)
            self._in_script = entry
        elif tag == "img":
            self.imgs.append(a)
        elif tag == "source":
            self.sources.append(a)
        elif tag == "a" and len(self.anchors) < 5:
            self.anchors.append(a.get("href", ""))
        elif tag == "title":
            self._in_title = True
        elif tag == "style":
            self._in_style = True
            self.inline_styles.append("")
        elif tag == "noscript":
            self.noscript = True

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_script = None
        elif tag == "title":
            self._in_title = False
        elif tag == "style":
            self._in_style = False
        elif tag == "head":
            self._in_head = False

    def handle_data(self, data):
        if self._in_script is not None:
            self._in_script["_inline"] += data
        elif self._in_title:
            self.title += data
        elif self._in_style and self.inline_styles:
            self.inline_styles[-1] += data


def _rel(link: dict) -> set[str]:
    return set(link.get("rel", "").lower().split())


def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    return (pa.scheme, pa.netloc) == (pb.scheme, pb.netloc)


def _ctype(entry: dict) -> str:
    return (entry.get("headers") or {}).get("content-type", "").split(";")[0].strip().lower()


def _safe_name(url: str, default: str) -> str:
    path = urlparse(url).path.rstrip("/") or default
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", path.strip("/")) or default
    return name[-120:]


def _resolve_ref(ref: str, bundle_url: str, page_url: str) -> str:
    # Only "./" and "../" are module-relative. Bundlers emit bare chunk paths
    # ("assets/js/x.js", Vite preload deps) relative to the app base, not to the
    # importing chunk; resolving them against the chunk doubles the directory.
    if ref.startswith(("./", "../")):
        return urljoin(bundle_url, ref)
    return urljoin(page_url, ref)


def _text(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


# Tailwind light/dark pairing, checked per source line (class lists rarely span
# lines in JSX; cn()/clsx() splits are a known false-positive source).
# name -> (unprefixed light-mode token, dark counterpart that pairs it on the same line)
THEME_PAIR_RULES = {
    "overlay": (r"(?<![:\w-])bg-black/\d+", r"dark:bg-"),
    "border": (r"(?<![:\w-])border-white/\d+", r"dark:border-"),
    "hover": (r"(?<![:\w-])hover:bg-(?:white|black)/\d+", r"dark:hover:bg-"),
    "gradient": (r"(?<![:\w-])(?:from|via|to)-(?:white|black)/\d+", r"dark:(?:from|via|to)-"),
    "surface": (r"(?<![:\w-])bg-(?:zinc|gray|slate|neutral|stone)-(?:800|900|950)\b", r"dark:bg-"),
    "text_white": (r"(?<![:\w-])text-white\b", r"dark:text-|bg-(?:\w+-[5-9]00|gradient|primary|accent|brand|indigo|blue|red|green|emerald|violet|purple|black)"),
}
# Scrims behind modals/drawers are meant to stay dark in both themes.
SCRIM_RX = re.compile(r"\bfixed\b(?=.*\binset-0\b)|backdrop")
CSS_VAR_SURFACE_RX = re.compile(r"\b(?:bg|text|border)-\[var\(--")
DROPDOWN_RX = re.compile(r"\babsolute\b(?=.*\b(?:right-0|left-0|end-0)\b)(?=.*\b(?:mt-\d|top-full)\b)(?=.*\bw-(?:\d+|\[))")
DROPDOWN_SAFE_RX = re.compile(r"\bfixed\b|max-sm:|sm:absolute|md:absolute")
UI_EXT = {".tsx", ".jsx", ".vue", ".svelte", ".astro", ".html"}


def source_audit(corpus: dict[str, str]) -> dict:
    pairs = {k: {"total": 0, "unpaired": 0, "samples": []} for k in THEME_PAIR_RULES}
    compiled = {k: (re.compile(a), re.compile(b)) for k, (a, b) in THEME_PAIR_RULES.items()}
    dd = {"candidates": 0, "mobile_safe": 0, "samples": []}
    css_var_tokens = 0
    for fname, text in corpus.items():
        if not fname.startswith("source/") or Path(fname).suffix.lower() not in UI_EXT:
            continue
        for no, line in enumerate(text.splitlines(), 1):
            css_var_tokens += len(CSS_VAR_SURFACE_RX.findall(line))
            scrim = bool(SCRIM_RX.search(line))
            for k, (tok, pair) in compiled.items():
                n = len(tok.findall(line))
                if not n:
                    continue
                pairs[k]["total"] += n
                if k == "overlay" and scrim:
                    continue
                if not pair.search(line):
                    pairs[k]["unpaired"] += n
                    if len(pairs[k]["samples"]) < 5:
                        pairs[k]["samples"].append(f"{fname}:{no}")
            if DROPDOWN_RX.search(line):
                dd["candidates"] += 1
                if DROPDOWN_SAFE_RX.search(line):
                    dd["mobile_safe"] += 1
                elif len(dd["samples"]) < 5:
                    dd["samples"].append(f"{fname}:{no}")
    return {"theme_pairs": pairs, "dropdowns": dd, "css_var_theme_tokens": css_var_tokens}


def scan_signals(corpus: dict[str, str]) -> dict:
    compiled = {name: re.compile(rx) for name, rx in SIGNALS.items()}
    out: dict[str, list[dict]] = {name: [] for name in SIGNALS}
    for fname, text in corpus.items():
        for name, rx in compiled.items():
            matches = list(rx.finditer(text))
            if not matches:
                continue
            m = matches[0]
            start = max(0, m.start() - 60)
            snippet = text[start:m.end() + 60].replace("\n", " ")
            line = text.count("\n", 0, m.start()) + 1
            out[name].append({"file": fname, "count": len(matches), "line": line,
                              "snippet": snippet[:200]})
    return out


def collect_source(src: Path, corpus: dict[str, str], limit: int = 4000) -> int:
    n = 0
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SOURCE_SKIP_DIRS and not d.startswith(".")]
        for f in files:
            p = Path(root) / f
            if (p.suffix.lower() not in SOURCE_EXT or p.name.endswith((".min.js", ".map"))
                    or TEST_FILE_RX.search(p.name)):
                continue
            if p.name in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}:
                continue
            try:
                if p.stat().st_size > MAX_BYTES:
                    continue
                corpus[f"source/{p.relative_to(src)}"] = p.read_text("utf-8", errors="replace")
            except OSError:
                continue
            n += 1
            if n >= limit:
                return n
    return n


def collect_url(url: str, out: Path, fetcher: Fetcher, max_bundles: int,
                corpus: dict[str, str]) -> dict:
    summary: dict = {"url": url}
    page = fetcher.get(url)
    if "error" in page:
        summary["error"] = page["error"]
        return summary
    base = page["final_url"]
    html = _text(page["body"])
    (out / "index.html").write_text(html, "utf-8")
    corpus["index.html"] = html
    summary.update(final_url=base, status=page["status"], https=base.startswith("https://"),
                   headers={h: page["headers"].get(h) for h in SECURITY_HEADERS if h in page["headers"]})
    (out / "headers.json").write_text(json.dumps(page["headers"], indent=2), "utf-8")

    # Compression: ask for br/gzip without decoding the body.
    comp = fetcher.get(base, accept_encoding="br, gzip", head_only=False)
    summary["compression"] = (comp.get("headers") or {}).get("content-encoding") if "error" not in comp else None

    # HTTP -> HTTPS redirect
    p = urlparse(base)
    if p.scheme == "https":
        plain = fetcher.get(f"http://{p.netloc}{p.path or '/'}", follow=False, head_only=True)
        loc = (plain.get("headers") or {}).get("location", "")
        summary["http_redirect"] = {"status": plain.get("status"), "location": loc,
                                    "error": plain.get("error"),
                                    "to_https": loc.startswith("https://")}

    parser = PageParser()
    parser.feed(html)
    metas = {}
    for m in parser.metas:
        key = (m.get("name") or m.get("property") or m.get("http-equiv") or "").lower()
        if key:
            metas.setdefault(key, []).append({k: v for k, v in m.items() if k in ("content", "media")})
    links_by_rel: dict[str, list[dict]] = {}
    for link in parser.links:
        for r in _rel(link):
            links_by_rel.setdefault(r, []).append(
                {k: v for k, v in link.items() if k in ("href", "sizes", "media", "type", "as",
                                                        "crossorigin", "integrity", "fetchpriority")})
    head_blocking = [s.get("src") for s in parser.scripts
                     if s["_in_head"] and s.get("src") and "async" not in s and "defer" not in s
                     and s.get("type", "").lower() != "module"]
    scripts_external = [s for s in parser.scripts if s.get("src")]
    third_party = [s.get("src") for s in scripts_external
                   if urlparse(urljoin(base, s["src"])).netloc not in ("", p.netloc)]
    imgs = parser.imgs
    summary["html"] = {
        "title": parser.title.strip()[:200],
        "lang": parser.html_attrs.get("lang"),
        "dir": parser.html_attrs.get("dir"),
        "meta": metas,
        "links": links_by_rel,
        "landmarks": {t: parser.tags.get(t, 0) for t in ("main", "nav", "header", "footer")},
        "aria_or_role_elements": parser.aria_or_role,
        "first_anchor_hrefs": parser.anchors,
        "noscript": parser.noscript,
        "json_ld": sum(1 for s in parser.scripts if s.get("type", "").lower() == "application/ld+json"),
        "speculation_rules": sum(1 for s in parser.scripts if s.get("type", "").lower() == "speculationrules"),
        "scripts": {
            "external": len(scripts_external),
            "render_blocking_in_head": head_blocking,
            "module": sum(1 for s in scripts_external if s.get("type", "").lower() == "module"),
            "third_party": third_party,
            "third_party_with_sri": sum(1 for s in scripts_external
                                        if s.get("src") in third_party and s.get("integrity")),
        },
        "images": {
            "count": len(imgs),
            "lazy": sum(1 for i in imgs if i.get("loading") == "lazy"),
            "with_dimensions": sum(1 for i in imgs if i.get("width") and i.get("height")),
            "fetchpriority_high": sum(1 for i in imgs if i.get("fetchpriority") == "high"),
            "srcset": sum(1 for i in imgs if i.get("srcset")),
            "modern_format_sources": sum(1 for s in parser.sources
                                         if any(f in (s.get("type", "") + s.get("srcset", ""))
                                                for f in ("avif", "webp"))),
            "modern_format_imgs": sum(1 for i in imgs
                                      if re.search(r"\.(?:avif|webp)\b", i.get("src", "") + i.get("srcset", ""))),
        },
        "mixed_content": sorted({u for u in re.findall(r"""(?:src|href)\s*=\s*["'](http://[^"']+)""", html)})[:20]
        if base.startswith("https://") else [],
        "inline_style_bytes": sum(len(s) for s in parser.inline_styles),
    }
    for i, s in enumerate(parser.scripts):
        if s["_inline"].strip():
            corpus[f"inline-script-{i}.js"] = s["_inline"]
    for i, s in enumerate(parser.inline_styles):
        if s.strip():
            corpus[f"inline-style-{i}.css"] = s

    # Manifest
    man_links = links_by_rel.get("manifest", [])
    summary["manifest"] = None
    if man_links:
        murl = urljoin(base, man_links[0]["href"])
        m = fetcher.get(murl)
        info = {"url": murl, "status": m.get("status"), "content_type": _ctype(m), "error": m.get("error"),
                "crossorigin": man_links[0].get("crossorigin")}
        if "body" in m:
            mtxt = _text(m["body"])
            (out / "manifest.json").write_text(mtxt, "utf-8")
            corpus["manifest.json"] = mtxt
            try:
                data = json.loads(mtxt)
                info["valid_json"] = isinstance(data, dict)
                info["data"] = data
            except json.JSONDecodeError as e:
                info["valid_json"] = False
                info["json_error"] = str(e)
        data = info.get("data") or {}
        icons_checked = []
        icons = [ic for ic in data.get("icons", []) if isinstance(ic, dict)] if isinstance(data, dict) else []
        wanted = [ic for ic in icons if any(s in str(ic.get("sizes", "")) for s in ("192x192", "512x512"))
                  or "maskable" in str(ic.get("purpose", ""))][:6]
        for ic in wanted:
            iurl = urljoin(murl, str(ic.get("src", "")))
            r = fetcher.get(iurl, head_only=True)
            if r.get("status") in (405, 501) or "error" in r:
                r = fetcher.get(iurl)
            icons_checked.append({"src": ic.get("src"), "sizes": ic.get("sizes"), "purpose": ic.get("purpose"),
                                  "status": r.get("status"), "content_type": _ctype(r), "error": r.get("error")})
        info["icons_checked"] = icons_checked
        summary["manifest"] = info

    # Bundles: same-origin scripts, modulepreload and stylesheets (two levels for JS).
    queue: list[str] = []
    for s in scripts_external:
        queue.append(urljoin(base, s["src"]))
    for r in ("modulepreload", "preload"):
        for link in links_by_rel.get(r, []):
            if r == "modulepreload" or link.get("as") == "script":
                queue.append(urljoin(base, link.get("href", "")))
    # Loaders that inject the entry chunk from an inline script (e.g. squoosh.app).
    for s in parser.scripts:
        for ref in JS_REF_RX.findall(s["_inline"])[:50]:
            queue.append(urljoin(base, ref))
    css_urls = [urljoin(base, link.get("href", "")) for link in links_by_rel.get("stylesheet", [])]
    bundles: list[dict] = []
    seen: set[str] = set()
    bdir = out / "bundles"
    bdir.mkdir(exist_ok=True)
    js_fetched = failures = 0
    crawl_budget = MAX_REQUESTS - RESERVED_REQUESTS
    while queue and js_fetched < max_bundles and failures < max_bundles and fetcher.count < crawl_budget:
        u = queue.pop(0)
        if u in seen or not _same_origin(u, base):
            continue
        seen.add(u)
        r = fetcher.get(u)
        if "body" not in r or r.get("status") != 200:
            failures += 1
            bundles.append({"url": u, "status": r.get("status"), "error": r.get("error")})
            continue
        js_fetched += 1
        txt = _text(r["body"])
        name = f"bundles/{js_fetched:02d}-{_safe_name(u, 'bundle.js')}"
        (out / name).write_text(txt, "utf-8")
        corpus[name] = txt
        bundles.append({"url": u, "status": 200, "bytes": r["bytes"], "file": name,
                        "cache_control": r["headers"].get("cache-control"),
                        "content_encoding": r["headers"].get("content-encoding")})
        for ref in JS_REF_RX.findall(txt)[:200]:
            ref_url = _resolve_ref(ref, u, base)
            if ref_url not in seen and _same_origin(ref_url, base) and "/node_modules/" not in ref_url:
                queue.append(ref_url)
    for i, u in enumerate(css_urls[:10]):
        if not _same_origin(u, base) or fetcher.count >= crawl_budget:
            continue
        r = fetcher.get(u)
        if "body" in r and r.get("status") == 200:
            txt = _text(r["body"])
            name = f"bundles/css-{i:02d}-{_safe_name(u, 'style.css')}"
            (out / name).write_text(txt, "utf-8")
            corpus[name] = txt
            bundles.append({"url": u, "status": 200, "bytes": r["bytes"], "file": name})
    summary["bundles"] = bundles

    # Service worker: from registration code, else probe common paths.
    sw_url, sw_source = None, None
    reg_rx = re.compile(r"""serviceWorker\s*\.\s*register\s*\(\s*(?:new\s+URL\s*\(\s*)?["'`]([^"'`]+)["'`]""")
    wb_rx = re.compile(r"""(?:new\s+Workbox|ServiceWorkerModule\.register|provideServiceWorker)\s*\(\s*["'`]([^"'`]+)["'`]""")
    for fname, text in corpus.items():
        m = reg_rx.search(text) or wb_rx.search(text)
        if m and not m.group(1).startswith("$"):
            sw_url, sw_source = urljoin(base, m.group(1)), fname
            break
    # Minified registrations pass the path through a variable (workbox-window,
    # vite-plugin-pwa), so also try SW-named path literals found in client code.
    registration_seen = any(re.search(SIGNALS["sw_register"], text) for text in corpus.values())
    probes = []

    def _try_sw(u: str, via: str) -> bool:
        r = fetcher.get(u)
        body = r.get("body", b"")
        ok = (r.get("status") == 200 and "html" not in _ctype(r)
              and (b"addEventListener" in body or b"importScripts" in body or b"workbox" in body))
        probes.append({"url": u, "via": via, "status": r.get("status"), "content_type": _ctype(r),
                       "looks_like_sw": ok})
        return ok

    if not sw_url:
        tried: set[str] = set()
        for fname, text in corpus.items():
            for lit in SW_LITERAL_RX.findall(text):
                u = urljoin(base, lit)
                if u in tried or not _same_origin(u, base) or len(tried) >= 3:
                    continue
                tried.add(u)
                if _try_sw(u, fname):
                    sw_url, sw_source = u, f"{fname} (path literal)"
                    break
            if sw_url or len(tried) >= 3:
                break
        for path in SW_PROBE_PATHS:
            if sw_url:
                break
            u = urljoin(base, path)
            if u not in tried and _try_sw(u, "probe"):
                sw_url, sw_source = u, "probe"
    summary["service_worker"] = None
    if sw_url:
        # The bundle crawler may have picked up the SW file by its string reference;
        # keep it only as sw.js so SW-side and client-side signals stay separable.
        for b in bundles:
            if b.get("url") == sw_url and b.get("file"):
                corpus.pop(b["file"], None)
                b["is_service_worker"] = True
        r = fetcher.get(sw_url)
        info = {"url": sw_url, "found_via": sw_source, "registration_seen": registration_seen,
                "status": r.get("status"), "content_type": _ctype(r),
                "cache_control": (r.get("headers") or {}).get("cache-control"),
                "service_worker_allowed": (r.get("headers") or {}).get("service-worker-allowed"),
                "error": r.get("error"), "imports": []}
        if "body" in r and r.get("status") == 200:
            txt = _text(r["body"])
            (out / "sw.js").write_text(txt, "utf-8")
            corpus["sw.js"] = txt
            refs = re.findall(r"""importScripts\s*\(([^)]*)\)""", txt)
            refs = [x for group in refs for x in re.findall(r"""["'`]([^"'`]+)["'`]""", group)]
            refs += re.findall(r"""(?:^|[;\s])import\s*(?:[\w{},*\s]+from\s*)?["']([^"']+)["']""", txt)
            for i, ref in enumerate(refs[:6]):
                iu = urljoin(sw_url, ref)
                ir = fetcher.get(iu)
                entry = {"url": iu, "status": ir.get("status")}
                if "body" in ir and ir.get("status") == 200:
                    name = f"sw-import-{i}-{_safe_name(iu, 'import.js')}"
                    itxt = _text(ir["body"])
                    (out / name).write_text(itxt, "utf-8")
                    corpus[name] = itxt
                    entry["file"] = name
                info["imports"].append(entry)
        summary["service_worker"] = info
    summary["sw_probes"] = probes

    # robots.txt for indexability
    rb = fetcher.get(urljoin(base, "/robots.txt"))
    if rb.get("status") == 200 and "body" in rb:
        rtxt = _text(rb["body"])
        (out / "robots.txt").write_text(rtxt, "utf-8")
        summary["robots"] = {"status": 200,
                             "disallow_all": bool(re.search(r"(?im)^\s*disallow:\s*/\s*$", rtxt))}
    else:
        summary["robots"] = {"status": rb.get("status"), "error": rb.get("error")}
    return summary


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", nargs="?")
    ap.add_argument("--out", default="pwa-audit-evidence")
    ap.add_argument("--source", help="local project directory to scan as well")
    ap.add_argument("--max-bundles", type=int, default=25)
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args(argv)
    if not args.url and not args.source:
        ap.error("give a URL, --source DIR, or both")
    if args.url and not re.match(r"^https?://", args.url):
        args.url = "https://" + args.url

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    corpus: dict[str, str] = {}
    fetcher = Fetcher(args.timeout)
    summary: dict = {"mode": "url+source" if args.url and args.source else ("url" if args.url else "source")}
    if args.url:
        summary.update(collect_url(args.url, out, fetcher, args.max_bundles, corpus))
    if args.source:
        src = Path(args.source).expanduser().resolve()
        if not src.is_dir():
            ap.error(f"--source is not a directory: {src}")
        summary["source"] = {"path": str(src), "files_scanned": collect_source(src, corpus)}

    if args.source:
        summary["source_audit"] = source_audit(corpus)
    signals = scan_signals(corpus)
    summary["signals"] = {k: sum(h["count"] for h in v) for k, v in signals.items()}
    summary["requests"] = fetcher.count
    summary["fetch_log"] = fetcher.log
    (out / "signals.json").write_text(json.dumps(signals, indent=2), "utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), "utf-8")

    hits = sorted(k for k, v in summary["signals"].items() if v)
    misses = sorted(k for k, v in summary["signals"].items() if not v)
    print(f"evidence: {out.resolve()}")
    print(f"mode={summary['mode']} status={summary.get('status')} https={summary.get('https')} "
          f"requests={fetcher.count} files_scanned={len(corpus)}")
    if summary.get("error"):
        print(f"FETCH ERROR: {summary['error']}")
    man = summary.get("manifest")
    print(f"manifest: {man['url'] + ' ' + str(man.get('status')) if man else 'NOT LINKED'}")
    sw = summary.get("service_worker")
    print(f"service_worker: {sw['url'] + ' via ' + str(sw['found_via']) if sw else 'NOT FOUND'}")
    print(f"signals present ({len(hits)}): {', '.join(hits)}")
    print(f"signals absent ({len(misses)}): {', '.join(misses)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
