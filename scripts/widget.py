#!/usr/bin/env python3
"""Push or preview a single KindleDesk widget.

Usage:
    widget.py <type> --slot <slot> --data-stdin
    widget.py <type> --slot <slot> --data-file <path>
    widget.py --clear --slot <slot>
    widget.py --clear          # clears all slots
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DAEMON = os.environ.get("KINDLEDESK_URL", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_NOTES_VAULT = Path(
    os.environ.get("KINDLEDESK_NOTES_VAULT")
    or os.environ.get("OBSIDIAN_VAULT")
    or Path.home() / "Documents" / "Obsidian"
)

# State file to avoid immediately repeating the same reflection question.
STATE_DIR = Path(os.environ.get("KINDLEDESK_STATE_DIR", Path(__file__).resolve().parent.parent))
LAST_REFLECTION_PATH = STATE_DIR / ".last_reflection.json"

TYPES = ("weather", "clock", "focus", "todo", "ai-status", "scratch", "calendar",
         "quote", "reading", "system", "countdown", "inbox", "reflection")
SLOTS = ("top-left", "top-right", "middle", "bottom", "full")


def _type_check(t: str) -> str:
    if t not in TYPES:
        raise argparse.ArgumentTypeError(f"type must be one of {TYPES}")
    return t


def _slot_check(s: str) -> str:
    if s not in SLOTS:
        raise argparse.ArgumentTypeError(f"slot must be one of {SLOTS}")
    return s


def _http(method: str, path: str, payload: dict | None = None):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else b""
    req = urllib.request.Request(
        f"{DAEMON}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        return 0, f"KindleDesk daemon unreachable: {e.reason}"


def _http_bytes(method: str, path: str, payload: dict | None = None) -> tuple[int, bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else b""
    req = urllib.request.Request(
        f"{DAEMON}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        return 0, f"KindleDesk daemon unreachable: {e.reason}".encode("utf-8")


def _get_widgets() -> list[dict]:
    status, body = _http("GET", "/widgets")
    if status != 200:
        return []
    try:
        return json.loads(body).get("widgets", [])
    except json.JSONDecodeError:
        return []


def _occupied_slots() -> set[str]:
    return {w.get("slot") for w in _get_widgets() if w.get("slot")}


def _load_last_reflection() -> dict:
    try:
        if LAST_REFLECTION_PATH.exists():
            return json.loads(LAST_REFLECTION_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_last_reflection(question: str, category: str):
    try:
        LAST_REFLECTION_PATH.write_text(
            json.dumps({"question": question, "category": category,
                        "shown_at": int(time.time())}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    except Exception:
        pass


def _parse_self_question_file(path: Path) -> list[dict]:
    """Parse 2-mainNotes/自问清单.md into {category, question} items.

    Only extracts bullets under the '## Key Points' section and its '### ' subsections.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    questions = []
    current_category = ""
    in_key_points = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_key_points = (stripped == "## Key Points")
            current_category = ""
            continue
        if not in_key_points:
            continue
        if stripped.startswith("### "):
            current_category = stripped[4:].strip()
            continue
        if stripped.startswith("- "):
            q = stripped[2:].strip()
            # Skip wiki links / notes lines that aren't actual questions.
            if q and not q.startswith("[["):
                questions.append({"category": current_category, "question": q})
    return questions


def validate_data(t: str, data: dict) -> tuple[bool, str]:
    """Lightweight structural validation; daemon is the authoritative validator."""
    if not isinstance(data, dict):
        return False, "data must be an object"
    if t == "weather":
        if "current" not in data:
            return False, "weather.data.current is required"
        if not isinstance(data["current"], dict):
            return False, "weather.data.current must be an object"
    elif t == "focus":
        if "task" not in data or not data["task"]:
            return False, "focus.data.task is required"
    elif t == "todo":
        if "items" not in data or not isinstance(data["items"], list):
            return False, "todo.data.items array is required"
    elif t == "calendar":
        if "events" not in data or not isinstance(data["events"], list):
            return False, "calendar.data.events array is required"
    elif t == "ai-status":
        if "task" not in data or not data["task"]:
            return False, "ai-status.data.task is required"
    elif t == "scratch":
        if "text" not in data:
            return False, "scratch.data.text is required"
    elif t == "clock":
        pass
    elif t == "quote":
        if "text" not in data and "quote" not in data:
            return False, "quote.data.text or quote.data.quote is required"
    elif t == "reading":
        if "title" not in data or not data["title"]:
            return False, "reading.data.title is required"
    elif t == "system":
        if data.get("cpu_pct") is None and data.get("memory_pct") is None:
            return False, "system.data.cpu_pct or memory_pct is required"
    elif t == "countdown":
        if "remaining" not in data or not data["remaining"]:
            return False, "countdown.data.remaining is required"
    elif t == "inbox":
        if "sources" not in data or not isinstance(data["sources"], list):
            return False, "inbox.data.sources array is required"
    elif t == "reflection":
        if ("question" not in data or not data["question"]) and ("text" not in data or not data["text"]):
            return False, "reflection.data.question or data.text is required"
    return True, ""


def _print(text: str):
    """Print text to stdout as UTF-8, bypassing Windows console encoding."""
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


def _print_json(obj: dict):
    _print(json.dumps(obj, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description="Push or preview a KindleDesk widget")
    ap.add_argument("widget_type", nargs="?", type=_type_check)
    ap.add_argument("--slot", type=_slot_check)
    ap.add_argument("--data-file", type=argparse.FileType("r", encoding="utf-8"))
    ap.add_argument("--data-stdin", action="store_true")
    ap.add_argument("--ttl", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true",
                    help="print payload without contacting daemon (default if no --push/--preview)")
    ap.add_argument("--preview", action="store_true",
                    help="render current snapshot PNG from daemon without pushing")
    ap.add_argument("--push", action="store_true",
                    help="POST /widget to push the widget to Kindle")
    ap.add_argument("--force", action="store_true",
                    help="push even if the target slot is occupied")
    ap.add_argument("--clear", action="store_true", help="clear slot(s) instead of pushing")
    ap.add_argument("--from-notes", nargs="?", const=str(DEFAULT_NOTES_VAULT),
                    help="for reflection/todo/quote: read content from the Obsidian vault (default path if no value given)")
    ap.add_argument("--category",
                    help="for reflection --from-notes: only pick from this category (e.g. 方向类, 行动类, 觉察类)")
    args = ap.parse_args()

    if args.clear:
        if args.slot:
            status, body = _http("DELETE", f"/widget?slot={args.slot}")
        else:
            status, body = _http("DELETE", "/widget")
        _print(body)
        return 0 if 200 <= status < 300 else 2

    if not args.widget_type or not args.slot:
        ap.error("widget_type + --slot required (or use --clear)")

    if args.from_notes is not None:
        vault = Path(args.from_notes)
        if args.widget_type == "reflection":
            q_path = vault / "2-mainNotes" / "自问清单.md"
            questions = _parse_self_question_file(q_path)
            if args.category:
                questions = [q for q in questions if q["category"] == args.category]
            if not questions:
                print(f"no questions found in {q_path}"
                      f"{' for category ' + args.category if args.category else ''}",
                      file=sys.stderr)
                return 1
            # Avoid immediately repeating the last shown question.
            last = _load_last_reflection()
            candidates = [q for q in questions if q["question"] != last.get("question")]
            if not candidates:
                candidates = questions
            item = random.choice(candidates)
            data = {"question": item["question"], "category": item["category"],
                    "hint": "停下来，诚实回答"}
        else:
            ap.error(f"--from-notes is not supported for type '{args.widget_type}'")
    elif args.data_stdin:
        data = json.load(sys.stdin)
    elif args.data_file:
        data = json.load(args.data_file)
    else:
        ap.error("--data-stdin, --data-file, or --from-notes required")

    ok, err = validate_data(args.widget_type, data)
    if not ok:
        print(f"validation error: {err}", file=sys.stderr)
        return 1

    payload = {"type": args.widget_type, "slot": args.slot, "data": data, "ttl": args.ttl}

    if args.dry_run or (not args.push and not args.preview):
        _print_json(payload)
        return 0

    if args.preview:
        status, body = _http_bytes("POST", "/widgets/preview")
        if status == 200:
            png_path = os.path.join(os.getcwd(), "kindledesk-preview.png")
            with open(png_path, "wb") as f:
                f.write(body)
            _print(png_path)
            return 0
        print(f"preview failed ({status}): {body.decode('utf-8', 'replace')}", file=sys.stderr)
        return 3

    if args.push:
        occupied = _occupied_slots()
        if args.slot in occupied and not args.force:
            print(f"slot '{args.slot}' is occupied. Use --force to overwrite.", file=sys.stderr)
            _print_json(payload)
            return 4
        status, body = _http("POST", "/widget", payload)
        if 200 <= status < 300 and args.widget_type == "reflection" and args.from_notes is not None:
            _save_last_reflection(data.get("question", ""), data.get("category", ""))
        _print(body)
        return 0 if 200 <= status < 300 else 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
