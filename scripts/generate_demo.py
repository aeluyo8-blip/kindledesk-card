"""Generate demo screenshots with fake data for README showcase.

Usage: PYTHONUTF8=1 python generate_demo.py
Output: examples/demo_*.png
"""
import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "daemon"))

import serve

OUT = ROOT / "examples"
OUT.mkdir(parents=True, exist_ok=True)

# ── Demo 1: Default layout (weather + ai-status + focus + todo) ──
serve._widget_cache.clear()
serve._widget_cache["top-left"] = serve.normalize_widget({
    "type": "weather", "slot": "top-left",
    "data": {"location": "北京", "current": {"temp": "22", "feels": "20", "humidity": "45", "condition": "晴"}},
})
serve._widget_cache["top-right"] = serve.normalize_widget({
    "type": "ai-status", "slot": "top-right",
    "data": {"session": "Demo", "model": "Claude", "task": "生成演示截图"},
})
serve._widget_cache["middle"] = serve.normalize_widget({
    "type": "focus", "slot": "middle",
    "data": {"task": "完成演示文稿", "big_text": "专注", "subtitle": "只处理正文和图表", "tag": "demo"},
})
serve._widget_cache["bottom"] = serve.normalize_widget({
    "type": "todo", "slot": "bottom",
    "data": {"title": "示例待办", "items": [
        {"text": "整理图表", "tag": "demo"},
        {"text": "写文档", "tag": "demo"},
        {"text": "已完成项", "tag": "已完成"},
    ]},
})
img = serve.render_widget_card(serve.widget_snapshot())
img.save(str(OUT / "demo_default.png"))
print("Saved demo_default.png")

# ── Demo 2: Full screen reflection ──
serve._widget_cache.clear()
serve._widget_cache["full"] = serve.normalize_widget({
    "type": "reflection", "slot": "full",
    "data": {"question": "今天做的最有意义的一件事是什么？", "category": "方向类", "hint": "停下来，诚实回答"},
})
img = serve.render_widget_card(serve.widget_snapshot())
img.save(str(OUT / "demo_reflection.png"))
print("Saved demo_reflection.png")

# ── Demo 3: Scratch + weather + system ──
serve._widget_cache.clear()
serve._widget_cache["top-left"] = serve.normalize_widget({
    "type": "weather", "slot": "top-left",
    "data": {"location": "上海", "current": {"temp": "28", "feels": "30", "humidity": "65", "condition": "多云"}},
})
serve._widget_cache["top-right"] = serve.normalize_widget({
    "type": "system", "slot": "top-right",
    "data": {"cpu_pct": 42, "memory_pct": 63, "disk_pct": 81, "battery_pct": 88},
})
serve._widget_cache["middle"] = serve.normalize_widget({
    "type": "scratch", "slot": "middle",
    "data": {"title": "便签", "text": "3pm 见 Bob — 带上昨天那张设计稿"},
})
serve._widget_cache["bottom"] = serve.normalize_widget({
    "type": "calendar", "slot": "bottom",
    "data": {"title": "今天", "events": [
        {"time": "09:30", "title": "项目同步"},
        {"time": "14:00", "title": "设计评审"},
        {"time": "16:00", "title": "周会"},
    ]},
})
img = serve.render_widget_card(serve.widget_snapshot())
img.save(str(OUT / "demo_scratch_calendar.png"))
print("Saved demo_scratch_calendar.png")

print("\nDone! All demo images saved to examples/")
