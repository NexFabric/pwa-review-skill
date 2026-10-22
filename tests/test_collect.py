"""End-to-end tests for scripts/collect.py against a local fixture PWA.

Run: python3 -m unittest discover -s tests
"""
import contextlib
import functools
import http.server
import io
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixture"
sys.path.insert(0, str(ROOT / "scripts"))

import collect  # noqa: E402


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class CollectFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(_QuietHandler, directory=str(FIXTURE))
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}/"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / "evidence"
        with contextlib.redirect_stdout(io.StringIO()):
            rc = collect.main([cls.base, "--out", str(out), "--timeout", "5"])
        assert rc == 0
        cls.summary = json.loads((out / "summary.json").read_text())
        cls.signals = json.loads((out / "signals.json").read_text())
        cls.out = out

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_manifest_and_icons(self):
        man = self.summary["manifest"]
        self.assertEqual(man["status"], 200)
        self.assertTrue(man["valid_json"])
        self.assertEqual(man["data"]["short_name"], "Fixture")
        self.assertEqual({ic["status"] for ic in man["icons_checked"]}, {200})
        self.assertEqual(len(man["icons_checked"]), 3)

    def test_service_worker_found_via_bundle_registration(self):
        sw = self.summary["service_worker"]
        self.assertTrue(sw["url"].endswith("/sw.js"))
        self.assertTrue(sw["found_via"].startswith("bundles/"))
        self.assertTrue((self.out / "sw.js").exists())

    def test_second_level_chunk_fetched(self):
        files = [b.get("file", "") for b in self.summary["bundles"]]
        self.assertTrue(any("chunk-lazy" in f for f in files), files)
        self.assertGreater(self.summary["signals"]["badging"], 0)

    def test_bare_chunk_paths_resolve_against_app_base(self):
        urls = [b["url"] for b in self.summary["bundles"]]
        vendor = [b for b in self.summary["bundles"] if b["url"].endswith("vendor-abc123.js")]
        self.assertEqual([b["status"] for b in vendor], [200], urls)
        self.assertFalse(any("/assets/js/assets/js/" in u for u in urls), urls)
        self.assertEqual(self.summary["robots"].get("error"), None)

    def test_html_facts(self):
        html = self.summary["html"]
        self.assertEqual(html["lang"], "en")
        self.assertEqual(len(html["meta"]["theme-color"]), 2)
        self.assertEqual(html["landmarks"]["main"], 1)
        self.assertEqual(html["images"]["fetchpriority_high"], 1)
        self.assertEqual(html["images"]["modern_format_imgs"], 1)
        self.assertTrue(html["noscript"])

    def test_signals_present(self):
        for name in ("sw_register", "sw_install", "sw_activate", "sw_fetch", "cache_cleanup",
                     "navigate_fallback", "offline_page", "bip", "visibility", "safe_area",
                     "reduced_motion", "dynamic_import", "cache_version_name"):
            self.assertGreater(self.summary["signals"][name], 0, name)

    def test_signals_absent(self):
        for name in ("unsafe_zoom", "sw_push", "realtime", "skip_waiting", "unload_listener"):
            self.assertEqual(self.summary["signals"][name], 0, name)

    def test_evidence_has_file_and_line(self):
        hit = self.signals["sw_install"][0]
        self.assertEqual(hit["file"], "sw.js")
        self.assertEqual(hit["line"], 2)

    def test_http_site_reports_not_https(self):
        self.assertFalse(self.summary["https"])
        self.assertNotIn("http_redirect", self.summary)


class SourceModeTest(unittest.TestCase):
    def test_source_only_scan_skips_build_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "app"
            (src / "src").mkdir(parents=True)
            (src / "node_modules" / "x").mkdir(parents=True)
            (src / "src" / "socket.ts").write_text(
                "const s = io(url, { reconnectionAttempts: Infinity });\n"
                "document.addEventListener('visibilitychange', () => s.connect());\n")
            (src / "node_modules" / "x" / "i.js").write_text("navigator.setAppBadge(1)")
            (src / "src" / "push.ts").write_text("getToken(messaging, { vapidKey: KEY })")
            (src / "src" / "Menu.tsx").write_text(
                '<div className="bg-black/60 dark:bg-black/60 border-white/10">\n'
                '<div className="absolute right-0 mt-2 w-56">\n'
                '<div className="fixed inset-0 bg-black/50 text-[var(--text)]">\n'
                '<img className="absolute inset-0 bg-gradient-to-t from-black/80 to-transparent" />\n'
                '<div className="h-12 bg-brand-500 rounded-full\n'
                '  flex items-center text-white">\n'
                '<div className="fixed left-4 right-4 sm:absolute sm:right-0 mt-2 w-56">\n')
            (src / "src" / "socket.test.ts").write_text("navigator.share({})")
            (src / "tests").mkdir()
            (src / "tests" / "e2e.ts").write_text("navigator.share({})")
            out = Path(d) / "ev"
            with contextlib.redirect_stdout(io.StringIO()):
                collect.main(["--source", str(src), "--out", str(out)])
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual(summary["mode"], "source")
            self.assertEqual(summary["source"]["files_scanned"], 3)
            audit = summary["source_audit"]
            self.assertEqual(audit["theme_pairs"]["overlay"], {"total": 2, "unpaired": 0, "samples": []})
            self.assertEqual(audit["theme_pairs"]["border"]["unpaired"], 1)
            self.assertEqual(audit["theme_pairs"]["border"]["samples"], ["source/src/Menu.tsx:1"])
            self.assertEqual(audit["dropdowns"]["candidates"], 2)
            self.assertEqual(audit["dropdowns"]["mobile_safe"], 1)
            self.assertEqual(audit["dropdowns"]["samples"], ["source/src/Menu.tsx:2"])
            self.assertEqual(audit["theme_pairs"]["overlay"]["total"], 2)  # scrim counted, not flagged
            self.assertEqual(audit["css_var_theme_tokens"], 1)
            self.assertEqual(audit["theme_pairs"]["gradient"]["unpaired"], 0)   # image scrim
            self.assertEqual(audit["theme_pairs"]["text_white"]["unpaired"], 0)  # bg on previous line
            self.assertGreater(summary["signals"]["push_subscribe"], 0)
            self.assertEqual(summary["signals"]["web_share"], 0)
            self.assertGreater(summary["signals"]["reconnect_cfg"], 0)
            self.assertGreater(summary["signals"]["visibility"], 0)
            self.assertEqual(summary["signals"]["badging"], 0)


if __name__ == "__main__":
    unittest.main()
