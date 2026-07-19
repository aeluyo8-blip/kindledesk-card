"""Widget-system tests for KindleDesk daemon.

Covers the ai-desk-card-style slot layout (top-left / top-right / middle /
bottom / full) on a 600×800 canvas with a 25 px top safe area.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from socketserver import TCPServer

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "daemon"))
import serve


def _start_server() -> tuple[TCPServer, threading.Thread, int]:
    server = TCPServer(("127.0.0.1", 0), serve.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, server.server_address[1]


def _json_req(port: int, path: str, payload: dict | None = None, method: str = "POST"):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else b""
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"error": body}
        return e.code, parsed


def _png_req(port: int, path: str, payload: dict | None = None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else b""
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return Image.open(io.BytesIO(r.read()))


class WidgetRenderTests(unittest.TestCase):
    def setUp(self):
        self.server, self.thread, self.port = _start_server()
        serve._widget_cache.clear()
        self._original_push = serve.push_to_kindle
        serve.push_to_kindle = lambda *args, **kwargs: True

    def tearDown(self):
        serve.push_to_kindle = self._original_push
        serve._widget_cache.clear()
        self.server.shutdown()
        self.server.server_close()

    def test_multi_slot_image_is_grayscale_600_by_800(self):
        payload = {
            "widgets": [
                {"type": "weather", "slot": "top-left",
                 "data": {"location": "青岛", "current": {"temp": "26", "condition": "多云"}}},
                {"type": "clock", "slot": "top-right", "data": {}},
                {"type": "focus", "slot": "middle",
                 "data": {"task": "完成论文结果章节", "big_text": "专注", "subtitle": "只处理正文和图表"}},
                {"type": "todo", "slot": "bottom",
                 "data": {"title": "今天", "items": [{"text": "整理图表", "tag": "today"}]}},
            ]
        }
        img = _png_req(self.port, "/widgets/preview", payload)
        self.assertEqual((600, 800), img.size)
        self.assertEqual("L", img.mode)

    def test_top_25_rows_are_blank(self):
        payload = {
            "widgets": [
                {"type": "focus", "slot": "middle",
                 "data": {"task": " occupying middle slot", "big_text": "专注"}},
                {"type": "todo", "slot": "bottom",
                 "data": {"title": "今天", "items": [{"text": "整理图表", "tag": "today"}]}},
            ]
        }
        img = _png_req(self.port, "/widgets/preview", payload)
        for y in range(25):
            for x in range(0, 600, 50):
                self.assertEqual(255, img.getpixel((x, y)),
                                 f"pixel at ({x},{y}) should be blank")

    def test_full_covers_other_slots(self):
        full_payload = {
            "widgets": [
                {"type": "scratch", "slot": "full",
                 "data": {"title": "全屏", "text": "full-screen content"}},
                {"type": "weather", "slot": "top-left",
                 "data": {"location": "青岛", "current": {"temp": "26", "condition": "多云"}}},
            ]
        }
        img = _png_req(self.port, "/widgets/preview", full_payload)
        # Full widget starts at y=25; top-left empty dashed outline should NOT appear.
        # The top-left slot is (0,25,300,235); a dashed outline would draw at y=33.
        # With full covering, that area stays white (no dashed line).
        for y in range(33, 45):
            for x in range(8, 292, 20):
                self.assertEqual(255, img.getpixel((x, y)),
                                 f"top-left slot pixel ({x},{y}) should be blank when full is present")

    def test_invalid_type_returns_400(self):
        status, body = _json_req(self.port, "/widget", {
            "type": "unknown", "slot": "middle", "data": {"x": 1},
        })
        self.assertEqual(400, status)
        self.assertIn("error", body)

    def test_invalid_slot_returns_400(self):
        status, body = _json_req(self.port, "/widget", {
            "type": "focus", "slot": "center", "data": {"task": "x"},
        })
        self.assertEqual(400, status)
        self.assertIn("error", body)

    def test_non_object_data_returns_400(self):
        status, body = _json_req(self.port, "/widget", {
            "type": "focus", "slot": "middle", "data": "not an object",
        })
        self.assertEqual(400, status)
        self.assertIn("error", body)

    def test_preview_does_not_modify_cache(self):
        serve._widget_cache["top-left"] = {
            "slot": "top-left", "type": "weather",
            "data": {"location": "青岛", "current": {"temp": "20", "condition": "晴"}},
            "ttl": 0, "written_at": time.time(),
        }
        before = dict(serve._widget_cache)
        _png_req(self.port, "/widgets/preview", {
            "widgets": [{"type": "scratch", "slot": "middle", "data": {"title": "x", "text": "y"}}],
        })
        self.assertEqual(before, serve._widget_cache)

    def test_preview_never_calls_push(self):
        calls = []
        serve.push_to_kindle = lambda *args, **kwargs: calls.append(args) or True
        _png_req(self.port, "/widgets/preview", {
            "widgets": [{"type": "scratch", "slot": "middle", "data": {"title": "x", "text": "y"}}],
        })
        self.assertEqual([], calls)

    def test_widget_updates_slot_and_pushes_once(self):
        calls = []
        serve.push_to_kindle = lambda *args, **kwargs: calls.append(args) or True
        status, body = _json_req(self.port, "/widget", {
            "type": "todo", "slot": "bottom",
            "data": {"title": "今天", "items": [{"text": "整理图表", "tag": "today"}]},
        })
        self.assertEqual(200, status)
        self.assertEqual("bottom", body["slot"])
        self.assertEqual("todo", body["type"])
        self.assertEqual("todo", serve._widget_cache["bottom"]["type"])
        self.assertEqual(1, len(calls))

    def test_ttl_expiry_removes_widget_from_snapshot(self):
        now = time.time()
        serve._widget_cache["top-left"] = {
            "slot": "top-left", "type": "weather",
            "data": {"location": "青岛", "current": {"temp": "20", "condition": "晴"}},
            "ttl": 0.05, "written_at": now - 0.1,
        }
        status, body = _json_req(self.port, "/widgets", method="GET")
        self.assertEqual(200, status)
        self.assertEqual([], body["widgets"])
        self.assertNotIn("top-left", serve._widget_cache)

    def test_delete_clears_single_slot(self):
        serve._widget_cache["top-left"] = {
            "slot": "top-left", "type": "weather",
            "data": {"location": "青岛", "current": {"temp": "20", "condition": "晴"}},
            "ttl": 0, "written_at": time.time(),
        }
        serve._widget_cache["bottom"] = {
            "slot": "bottom", "type": "todo",
            "data": {"title": "今天", "items": []},
            "ttl": 0, "written_at": time.time(),
        }
        status, body = _json_req(self.port, "/widget?slot=top-left", method="DELETE")
        self.assertEqual(200, status)
        self.assertEqual("top-left", body["cleared"])
        self.assertNotIn("top-left", serve._widget_cache)
        self.assertIn("bottom", serve._widget_cache)

    def test_delete_clears_all_slots(self):
        serve._widget_cache["top-left"] = {
            "slot": "top-left", "type": "weather",
            "data": {"location": "青岛", "current": {"temp": "20", "condition": "晴"}},
            "ttl": 0, "written_at": time.time(),
        }
        status, body = _json_req(self.port, "/widget", method="DELETE")
        self.assertEqual(200, status)
        self.assertEqual("all", body["cleared"])
        self.assertEqual({}, serve._widget_cache)

    def test_delete_unknown_slot_returns_400(self):
        status, body = _json_req(self.port, "/widget?slot=unknown", method="DELETE")
        self.assertEqual(400, status)
        self.assertIn("error", body)


WIDGET_PY = Path(__file__).resolve().parents[1] / "scripts" / "widget.py"


class WidgetScriptTests(unittest.TestCase):
    def setUp(self):
        self.server, self.thread, self.port = _start_server()
        serve._widget_cache.clear()
        self._original_push = serve.push_to_kindle
        serve.push_to_kindle = lambda *args, **kwargs: True
        self.env = dict(os.environ, KINDLEDESK_URL=f"http://127.0.0.1:{self.port}")

    def tearDown(self):
        serve.push_to_kindle = self._original_push
        serve._widget_cache.clear()
        self.server.shutdown()
        self.server.server_close()

    def _run(self, *args, stdin: str = "") -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(WIDGET_PY), *args],
            input=stdin,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_script_dry_run_outputs_payload(self):
        result = self._run("focus", "--slot", "middle", "--data-stdin",
                           stdin='{"task":"test task"}')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('"type": "focus"', result.stdout)
        self.assertIn('"slot": "middle"', result.stdout)

    def test_script_push_updates_cache(self):
        result = self._run("todo", "--slot", "bottom", "--data-stdin", "--push",
                           stdin='{"title":"今天","items":[{"text":"x"}]}')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("todo", serve._widget_cache["bottom"]["type"])

    def test_script_push_occupied_slot_requires_force(self):
        serve._widget_cache["middle"] = {
            "slot": "middle", "type": "focus",
            "data": {"task": "existing"},
            "ttl": 0, "written_at": time.time(),
        }
        result = self._run("scratch", "--slot", "middle", "--data-stdin", "--push",
                           stdin='{"title":"x","text":"y"}')
        self.assertEqual(4, result.returncode)
        self.assertIn("occupied", result.stderr)

    def test_script_clear_all(self):
        serve._widget_cache["top-left"] = {
            "slot": "top-left", "type": "weather",
            "data": {"location": "青岛", "current": {"temp": "20"}},
            "ttl": 0, "written_at": time.time(),
        }
        result = self._run("--clear")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({}, serve._widget_cache)


if __name__ == "__main__":
    unittest.main()
