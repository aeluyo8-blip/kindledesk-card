"""KindleDesk card server — ai-desk-card layout adapted to Kindle Basic 3 (600x800).

Rendering and daemon concepts adapted from op7418/ai-desk-card (GPL-3.0):
https://github.com/op7418/ai-desk-card

Design (mirrors ai-desk-card v0.6 Swiss-minimalist e-ink):
  - Grid of widget slots (top-left / top-right / middle / bottom / full)
  - ONE body font size (28pt); hierarchy via bold, dividers, boxes, inverted bars
  - header_bar = UPPERCASE label + right-aligned meta + 3px black rule
  - paint_empty = dashed outline for unfilled slots
  - inverted black bottom bar: status (left) + chips (right)
  - structural divider: 3px black line between top-left / top-right
Output: 600x800 grayscale (mode L). /fb serves raw framebuffer (800x608 stride).
Weather cached 10 min (wttr.in). Agent can POST /preview or /push for a one-off card.
"""
import http.server
import socketserver
import io
import json
import os
import time
import socket
import urllib.request
import urllib.parse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ---- canvas (Kindle Basic 3) ----
CANVAS_W, CANVAS_H = 600, 800
PADDING = 20
BOTTOM_BAR_Y = 740
BOTTOM_BAR_H = 60
INK = 0
MID = 0x55
META = 0x99
DIVIDER = 0x88
BODY = 28
SYSTEM_SAFE_H = 25

# slot grid (adapted from ai-desk-card SLOT_RECTS, scaled to 600x800)
SLOT_RECTS = {
    "top-left":  (0,   0,   300, 240),
    "top-right": (300, 0,   300, 240),
    "middle":    (0,   240, 600, 280),   # 240..520
    "bottom":    (0,   520, 600, 220),   # 520..740
    "full":      (0,   0,   600, 740),
}

# Agent-composed card: Kindle system owns the first 25 px. The remaining
# 600x775 area follows ai-desk-card's 2-1-1 widget grid and has no status bar.
WIDGET_SLOT_RECTS = {
    "top-left":  (0,   25,  300, 210),
    "top-right": (300, 25,  300, 210),
    "middle":    (0,   235, 600, 285),
    "bottom":    (0,   520, 600, 280),
    "full":      (0,   25,  600, 775),
}
WIDGET_SLOTS = tuple(WIDGET_SLOT_RECTS)

CITY_ZH = "青岛"
CITY_PINYIN = "Qingdao"
WEATHER_TTL = 600
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

WEATHER_ZH = {
    113: "晴", 116: "多云", 119: "阴", 122: "阴",
    143: "雾", 248: "雾", 260: "雾",
    176: "小雨", 263: "小雨", 266: "小雨", 281: "小雨", 284: "小雨",
    293: "小雨", 296: "小雨", 299: "中雨", 302: "中雨", 305: "大雨",
    308: "大雨", 311: "暴雨", 314: "暴雨", 317: "暴雨",
    350: "阵雨", 353: "阵雨", 356: "阵雨", 359: "阵雨", 362: "阵雨", 365: "阵雨",
    179: "雨夹雪", 182: "雨夹雪", 185: "雨夹雪", 320: "雨夹雪", 374: "雨夹雪", 377: "雨夹雪",
    227: "小雪", 230: "大雪", 323: "小雪", 326: "小雪", 329: "中雪", 332: "中雪",
    335: "大雪", 338: "大雪", 368: "小雪", 371: "大雪",
    200: "雷阵雨", 386: "雷阵雨", 389: "雷阵雨", 392: "雷阵雪", 395: "雷阵雪",
}


def _wzh(code):
    try:
        return WEATHER_ZH.get(int(code), "—")
    except Exception:
        return "—"


# ---- fonts (module-level cache, ai-desk-card single-size rule) ----
def _cjk(size, bold=False):
    paths = (["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/msyh.ttc"]
             if bold else ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"])
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


F_BODY = _cjk(28)
F_BODY_B = _cjk(28, bold=True)
F_HEADER = _cjk(32, bold=True)
F_BAR = _cjk(22)
F_BAR_B = _cjk(22, bold=True)
F_CLOCK = _font("C:/Windows/Fonts/arialbd.ttf", 72)
F_TEMP = _font("C:/Windows/Fonts/arialbd.ttf", 64)


# ---- design primitives (borrowed from ai-desk-card) ----

def header_bar(d, rect, label, meta=""):
    """UPPERCASE label + right-aligned gray meta + 3px black underline. Returns next_y."""
    x, y, w, h = rect
    d.text((x + PADDING, y + 14), label.upper(), fill=INK, font=F_HEADER)
    if meta:
        mw = d.textlength(meta, font=F_BODY)
        d.text((x + w - PADDING - mw, y + 18), meta, fill=META, font=F_BODY)
    d.rectangle((x + PADDING, y + 50 - 3, x + w - PADDING, y + 50), fill=INK)
    return y + 50


def divider(d, x1, y, x2, weight=1, gray=DIVIDER):
    for k in range(weight):
        d.line((x1, y + k, x2, y + k), fill=gray)


def body_text(d, x, y, max_w, text, bold=False, fill=INK):
    """Single line, auto-truncate with '...'. Returns next_y."""
    if not text:
        return y
    f = F_BODY_B if bold else F_BODY
    t = text
    if d.textlength(t, font=f) > max_w:
        while t and d.textlength(t + "...", font=f) > max_w:
            t = t[:-1]
        t = t + "..."
    d.text((x, y), t, fill=fill, font=f)
    return y + BODY + 8


def wrapped_text(d, x, y, max_w, max_h, text, bold=False, fill=INK):
    """Multi-line wrap (greedy, by char). Returns next_y."""
    if not text:
        return y
    f = F_BODY_B if bold else F_BODY
    line_h = BODY + 6
    line = ""
    cy = y
    for ch in text:
        if ch == "\n":
            d.text((x, cy), line, fill=fill, font=f)
            cy += line_h
            line = ""
            continue
        if d.textlength(line + ch, font=f) > max_w:
            d.text((x, cy), line, fill=fill, font=f)
            cy += line_h
            line = ""
            if cy > y + max_h - line_h:
                break
        line += ch
    if line and cy <= y + max_h:
        d.text((x, cy), line, fill=fill, font=f)
        cy += line_h
    return cy


# ---- widget painters (à la ai-desk-card) ----

def paint_weather(d, rect, data, now):
    x, y, w, h = rect
    header_bar(d, rect, "WEATHER", data.get("location", ""))
    ny = y + 50 + PADDING
    cur = data.get("current") or {}
    if cur:
        temp = cur.get("temp")
        cond = cur.get("condition", "")
        if temp is not None:
            d.text((x + PADDING, ny), f"{temp}°", fill=INK, font=F_TEMP)
            cw = d.textlength(cond, font=F_BODY_B)
            d.text((x + w - PADDING - cw, ny + 24), cond, fill=MID, font=F_BODY_B)
            ny += 78
        ny = body_text(d, x + PADDING, ny, w - 2 * PADDING,
                       f"体感 {cur.get('feels','—')}°", fill=META)
        body_text(d, x + PADDING, ny, w - 2 * PADDING,
                  f"湿度 {cur.get('humidity','—')}%", fill=META)
    else:
        body_text(d, x + PADDING, ny, w - 2 * PADDING, "加载中…", fill=META)


def paint_clock(d, rect, data, now):
    x, y, w, h = rect
    header_bar(d, rect, "NOW", now.strftime("%a").upper())
    ny = y + 50 + PADDING
    hm = now.strftime("%H:%M")
    hm_w = d.textlength(hm, font=F_CLOCK)
    d.text((x + (w - hm_w) / 2, ny), hm, fill=INK, font=F_CLOCK)
    sec = now.strftime("%S")
    d.text((x + (w + hm_w) / 2 + 8, ny + 24), sec, fill=META, font=_font("C:/Windows/Fonts/arial.ttf", 24))
    ny += 90
    date_str = f"{now.month}-{now.day}  {WEEKDAYS[now.weekday()]}"
    dw = d.textlength(date_str, font=F_BODY)
    d.text((x + (w - dw) / 2, ny), date_str, fill=MID, font=F_BODY)


def paint_focus(d, rect, data, now):
    x, y, w, h = rect
    header_bar(d, rect, "FOCUS", data.get("tag", ""))
    ny = y + 50 + PADDING
    task = data.get("task", "")
    if task:
        ny = wrapped_text(d, x + PADDING, ny, w - 2 * PADDING, h - 80, task, bold=True)
    big = data.get("big_text", "")
    if big:
        box_w = w - 2 * PADDING
        box_h = 56
        d.rectangle((x + PADDING, ny, x + PADDING + box_w, ny + box_h), outline=INK, width=2)
        f_b = F_BODY_B
        tw = d.textlength(big, font=f_b)
        d.text((x + PADDING + (box_w - tw) / 2, ny + (box_h - 28) / 2), big, fill=INK, font=f_b)
        ny += box_h + 10
    sub = data.get("subtitle", "")
    if sub:
        body_text(d, x + PADDING, ny, w - 2 * PADDING, sub, fill=META)


def paint_todo(d, rect, data, now):
    x, y, w, h = rect
    header_bar(d, rect, "TODO", data.get("title", ""))
    ny = y + 50 + PADDING
    for it in (data.get("items") or [])[:4]:
        tag = it.get("tag", "")
        text = it.get("text", "")
        # skip completed items so stale tasks don't clutter the card
        if tag == "已完成":
            continue
        mark = "□"
        if tag:
            body_text(d, x + PADDING, ny, w - 2 * PADDING, f"{mark} {text}", fill=INK)
        else:
            body_text(d, x + PADDING, ny, w - 2 * PADDING, f"{mark} {text}", fill=MID)
        ny += BODY + 10


def paint_ai_status(d, rect, data, now):
    x, y, w, h = rect
    header_bar(d, rect, "AI", data.get("session", ""))
    ny = y + 50 + PADDING
    model = data.get("model", "")
    if model:
        body_text(d, x + PADDING, ny, w - 2 * PADDING, model, bold=True)
        ny += BODY + 8
    task = data.get("task", "")
    if task:
        ny = wrapped_text(d, x + PADDING, ny, w - 2 * PADDING, h - 120, task, fill=MID)


def paint_scratch(d, rect, data, now):
    x, y, w, h = rect
    ny = header_bar(d, rect, "NOTE", data.get("title", "")) + PADDING
    wrapped_text(d, x + PADDING, ny, w - 2 * PADDING,
                 h - (ny - y) - PADDING, data.get("text", ""))


def paint_calendar(d, rect, data, now):
    x, y, w, h = rect
    ny = header_bar(d, rect, "TODAY", data.get("title", "")) + PADDING
    time_w = 84
    for item in (data.get("events") or [])[:6]:
        at = str(item.get("time", "—"))
        title = str(item.get("title", ""))
        tw = d.textlength(at, font=F_BODY_B)
        d.text((x + PADDING + time_w - tw, ny), at, fill=INK, font=F_BODY_B)
        d.line((x + PADDING + time_w + 14, ny + 7,
                x + PADDING + time_w + 14, ny + BODY + 2), fill=DIVIDER)
        body_text(d, x + PADDING + time_w + 30, ny,
                  w - 3 * PADDING - time_w - 30, title)
        ny += BODY + 18
        if ny > y + h - PADDING - BODY:
            break


def paint_quote(d, rect, data, now):
    """Quote of the day / reading quote."""
    x, y, w, h = rect
    source = data.get("source") or data.get("book") or ""
    ny = header_bar(d, rect, "QUOTE", source) + PADDING
    text = data.get("text") or data.get("quote") or ""
    body_h = h - (ny - y) - PADDING - 40
    wrapped_text(d, x + PADDING, ny, w - 2 * PADDING, body_h, text, fill=INK)
    author = data.get("author") or ""
    if author:
        aw = d.textlength(f"— {author}", font=F_BODY_B)
        d.text((x + w - PADDING - aw, y + h - PADDING - BODY), f"— {author}",
               fill=META, font=F_BODY_B)


def paint_reading(d, rect, data, now):
    """Current book + progress + reading streak."""
    x, y, w, h = rect
    title = data.get("title") or ""
    ny = header_bar(d, rect, "READING", data.get("author", "")) + PADDING

    # Book title
    if title:
        ny = wrapped_text(d, x + PADDING, ny, w - 2 * PADDING, BODY * 2 + 8,
                          title, bold=True)
        ny += 10

    # Progress bar
    progress = data.get("progress_pct", 0)
    bar_w = w - 2 * PADDING
    bar_h = 14
    d.rectangle((x + PADDING, ny, x + PADDING + bar_w, ny + bar_h),
                outline=INK, width=1)
    fill = max(1, min(bar_w, int(bar_w * progress / 100))) if progress > 0 else 0
    if fill:
        d.rectangle((x + PADDING, ny, x + PADDING + fill, ny + bar_h), fill=INK)
    pct_text = f"{progress}%"
    pw = d.textlength(pct_text, font=F_BODY_B)
    d.text((x + PADDING + bar_w - pw, ny + bar_h + 8), pct_text,
           fill=META, font=F_BODY_B)
    ny += bar_h + 36

    # Streak / stats row
    streak = data.get("streak_days")
    today_min = data.get("today_min")
    parts = []
    if streak is not None:
        parts.append(f"连续 {streak} 天")
    if today_min is not None:
        parts.append(f"今日 {today_min} 分钟")
    if parts:
        body_text(d, x + PADDING, ny, w - 2 * PADDING, "  ·  ".join(parts), fill=META)


def paint_system(d, rect, data, now):
    """PC system stats: CPU / memory / disk / battery bars."""
    x, y, w, h = rect
    ny = header_bar(d, rect, "SYSTEM", data.get("host", "")) + PADDING

    cells = []
    if data.get("cpu_pct") is not None:
        cells.append((data["cpu_pct"], "CPU"))
    if data.get("memory_pct") is not None:
        cells.append((data["memory_pct"], "MEM"))
    if data.get("disk_pct") is not None:
        cells.append((data["disk_pct"], "DISK"))
    bp = data.get("battery_pct")
    if bp is not None:
        cells.append((bp, "BAT"))

    row_h = min(56, (h - (ny - y) - 2 * PADDING) // max(len(cells), 1))
    f_b = F_BODY_B
    f_l = F_BODY
    for pct, label in cells:
        val = f"{pct}%"
        d.text((x + PADDING, ny), val, fill=INK, font=f_b)
        d.text((x + PADDING + 80, ny + 6), label, fill=META, font=f_l)
        bar_x0 = x + PADDING + 160
        bar_x1 = x + w - PADDING
        bar_y = ny + 18
        d.rectangle((bar_x0, bar_y, bar_x1, bar_y + 10),
                    outline=INK, width=1)
        fill = max(1, min(bar_x1 - bar_x0, int((bar_x1 - bar_x0) * pct / 100))) if pct > 0 else 0
        if fill:
            d.rectangle((bar_x0, bar_y, bar_x0 + fill, bar_y + 10), fill=INK)
        ny += row_h


def paint_countdown(d, rect, data, now):
    """Countdown to a single event/deadline."""
    x, y, w, h = rect
    label = data.get("label") or data.get("title") or ""
    ny = header_bar(d, rect, "COUNTDOWN", label) + PADDING

    remaining = data.get("remaining") or ""
    if remaining:
        box_w = w - 2 * PADDING
        box_h = 64
        d.rectangle((x + PADDING, ny, x + PADDING + box_w, ny + box_h),
                    outline=INK, width=2)
        f_b = F_BODY_B
        tw = d.textlength(remaining, font=f_b)
        d.text((x + PADDING + (box_w - tw) / 2, ny + (box_h - BODY) / 2),
               remaining, fill=INK, font=f_b)
        ny += box_h + 16

    target = data.get("target") or ""
    if target:
        body_text(d, x + PADDING, ny, w - 2 * PADDING, target, fill=META)


def paint_inbox(d, rect, data, now):
    """Aggregated unread counts per source."""
    x, y, w, h = rect
    total = data.get("total", 0)
    meta = str(total) if total else ""
    ny = header_bar(d, rect, "INBOX", meta) + PADDING - 4

    sources = (data.get("sources") or [])[:4]
    if not sources:
        body_text(d, x + PADDING, ny, w - 2 * PADDING, "all caught up", fill=META)
        return
    row_h = BODY + 14
    f = F_BODY
    f_b = F_BODY_B
    for src in sources:
        name = src.get("name", "")
        cnt = src.get("count", 0)
        cnt_str = str(cnt)
        cnt_w = d.textlength(cnt_str, font=f_b)
        d.text((x + PADDING, ny), name, fill=INK, font=f)
        d.text((x + w - PADDING - cnt_w, ny), cnt_str,
               fill=INK if cnt > 0 else META, font=f_b)
        # dotted leader
        name_w = d.textlength(name, font=f)
        lx0 = x + PADDING + name_w + 12
        lx1 = x + w - PADDING - cnt_w - 12
        cx = lx0
        while cx + 2 < lx1:
            d.rectangle((cx, ny + BODY - 4, cx + 2, ny + BODY - 2), fill=DIVIDER)
            cx += 8
        ny += row_h
        if ny > y + h - PADDING:
            break


def paint_empty(d, rect):
    """Empty slot — dashed outline (ai-desk-card style)."""
    x, y, w, h = rect
    for i in range(x + 8, x + w - 8, 14):
        d.line((i, y + 8, i + 7, y + 8), fill=DIVIDER)
        d.line((i, y + h - 8, i + 7, y + h - 8), fill=DIVIDER)
    for j in range(y + 8, y + h - 8, 14):
        d.line((x + 8, j, x + 8, j + 7), fill=DIVIDER)
        d.line((x + w - 8, j, x + w - 8, j + 7), fill=DIVIDER)


def paint_bottom_bar(d, status):
    """Inverted black strip: left = status pieces, right = chips."""
    bar_y = BOTTOM_BAR_Y
    d.rectangle((0, bar_y, CANVAS_W, bar_y + BOTTOM_BAR_H), fill=INK)
    f = F_BAR
    f_b = F_BAR_B
    text_y = bar_y + (BOTTOM_BAR_H - 22) // 2 - 2
    pieces = []
    if status.get("device_alive") is False:
        pieces.append(("OFFLINE", True))
    else:
        pieces.append((status.get("transport", "PULL"), False))
    pieces.append((status.get("time", ""), False))
    cx = PADDING
    for i, (text, bold) in enumerate(pieces):
        if i > 0:
            d.line((cx, bar_y + 14, cx, bar_y + BOTTOM_BAR_H - 14), fill=140, width=1)
            cx += 14
        fnt = f_b if bold else f
        d.text((cx, text_y), text, fill=255, font=fnt)
        cx += int(d.textlength(text, font=fnt)) + 10
    # right chip: label
    label = status.get("label", "KindleDesk")
    lw = d.textlength(label, font=f_b)
    d.text((CANVAS_W - PADDING - lw, text_y), label, fill=255, font=f_b)


def paint_reflection(d, rect, data, now):
    """Self-reflection question widget — draws from 自问清单 style content."""
    x, y, w, h = rect
    category = data.get("category") or ""
    ny = header_bar(d, rect, "ASK", category) + PADDING + 8

    question = data.get("question") or data.get("text") or ""
    if question:
        # Leave room for the bottom hint.
        max_h = h - (ny - y) - PADDING - 40
        # Draw a subtle box around the question area.
        box_margin = 8
        d.rectangle((x + PADDING - box_margin, ny - box_margin,
                     x + w - PADDING + box_margin, y + h - PADDING - 28),
                    outline=DIVIDER, width=1)
        ny = wrapped_text(d, x + PADDING, ny, w - 2 * PADDING, max_h,
                          question, bold=True, fill=INK)

    hint = data.get("hint") or "停下来，诚实回答"
    if hint:
        hw = d.textlength(hint, font=F_BODY)
        d.text((x + (w - hw) / 2, y + h - PADDING - BODY),
               hint, fill=META, font=F_BODY)


PAINTERS = {
    "weather":    paint_weather,
    "clock":      paint_clock,
    "focus":      paint_focus,
    "todo":       paint_todo,
    "ai-status":  paint_ai_status,
    "scratch":    paint_scratch,
    "calendar":   paint_calendar,
    "quote":      paint_quote,
    "reading":    paint_reading,
    "system":     paint_system,
    "countdown":  paint_countdown,
    "inbox":      paint_inbox,
    "reflection": paint_reflection,
}
WIDGET_TYPES = tuple(PAINTERS)


# ---- weather (cached) ----
_weather = {"data": None, "ts": 0.0}


def fetch_weather():
    now = time.time()
    if _weather["data"] and now - _weather["ts"] < WEATHER_TTL:
        return _weather["data"]
    try:
        url = "https://wttr.in/{}?format=j1".format(urllib.parse.quote(CITY_PINYIN))
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r)
        c = d["current_condition"][0]
        data = {
            "current": {
                "temp": c["temp_C"], "feels": c["FeelsLikeC"], "humidity": c["humidity"],
                "condition": _wzh(c["weatherCode"]),
            },
            "location": CITY_ZH,
            "forecast": [],
        }
        for day in d["weather"][:3]:
            data["forecast"].append({
                "date": day["date"], "min": day["mintempC"], "max": day["maxtempC"],
                "cond": _wzh(day["hourly"][4]["weatherCode"]),
            })
        _weather["data"] = data
        _weather["ts"] = now
        print(f"[weather] {CITY_ZH} {data['current']['temp']}° {data['current']['condition']}", flush=True)
        return data
    except Exception as e:
        print(f"[weather] fetch failed: {e}", flush=True)
        return _weather["data"]


# ---- agent widget cache ----
_widget_cache = {}


def normalize_widget(data, written_at=None):
    if not isinstance(data, dict):
        raise ValueError("widget must be an object")
    widget_type = str(data.get("type", ""))
    slot = str(data.get("slot", ""))
    widget_data = data.get("data")
    if widget_type not in WIDGET_TYPES:
        raise ValueError(f"unknown widget type: {widget_type}")
    if slot not in WIDGET_SLOTS:
        raise ValueError(f"unknown widget slot: {slot}")
    if not isinstance(widget_data, dict):
        raise ValueError("widget data must be an object")
    return {
        "slot": slot,
        "type": widget_type,
        "data": widget_data,
        "ttl": max(0.0, float(data.get("ttl", 0))),
        "written_at": time.time() if written_at is None else written_at,
    }


def widget_snapshot():
    now = time.time()
    widgets = []
    for slot, widget in list(_widget_cache.items()):
        ttl = widget["ttl"]
        if ttl and now - widget["written_at"] >= ttl:
            _widget_cache.pop(slot, None)
            continue
        widgets.append(widget.copy())
    return widgets


# ---- default widget snapshot ----

def default_snapshot(now):
    w = fetch_weather() or {}
    return [
        {"slot": "top-left", "type": "weather",
         "data": {"location": CITY_ZH, "current": w.get("current", {})}},
        {"slot": "top-right", "type": "clock", "data": {}},
        {"slot": "middle", "type": "focus",
         "data": {"task": "研究生工作", "subtitle": "拔 USB 后 Kindle 自动显示 · agent 可 /push 推送", "tag": "today"}},
        {"slot": "bottom", "type": "todo",
         "data": {"title": "next", "items": [
             {"text": "确认卡片排版满意"},
             {"text": "优化 widget 内容"},
             {"text": "agent skill 端到端"},
         ]}},
    ]


# ---- top-level render ----

def render_image(widget_snapshot, status=None, slot_rects=None, bottom_bar=True):
    img = Image.new("L", (CANVAS_W, CANVAS_H), 255)
    d = ImageDraw.Draw(img)
    now = datetime.now()
    slot_rects = slot_rects or SLOT_RECTS
    widgets = list(widget_snapshot)
    full = [widget for widget in widgets if widget.get("slot") == "full"]
    if full:
        widgets = full[-1:]

    seen = set()
    for w in widgets:
        slot = w.get("slot")
        wtype = w.get("type")
        rect = slot_rects.get(slot)
        fn = PAINTERS.get(wtype)
        if rect and fn:
            seen.add(slot)
            try:
                fn(d, rect, w.get("data") or {}, now)
            except Exception as e:
                d.text((rect[0] + 16, rect[1] + 16), f"err: {e!r}", fill=INK, font=F_BODY)

    if "full" not in seen:
        for slot, rect in slot_rects.items():
            if slot == "full" or slot in seen:
                continue
            paint_empty(d, rect)
        split_x = slot_rects["top-right"][0]
        top_y = slot_rects["top-left"][1]
        mid_y = slot_rects["middle"][1]
        d.rectangle((split_x - 2, top_y + 12, split_x + 1, mid_y - 12), fill=INK)

    if bottom_bar:
        paint_bottom_bar(d, {
            "transport": status.get("transport", "PULL") if status else "PULL",
            "device_alive": status.get("device_alive") if status else None,
            "time": now.strftime("%H:%M"),
            "label": "KindleDesk",
        })
    return img


def render_widget_card(widgets):
    return render_image(widgets, slot_rects=WIDGET_SLOT_RECTS, bottom_bar=False)


def render_card():
    widgets = widget_snapshot()
    if widgets:
        return render_widget_card(widgets)
    return render_image(default_snapshot(datetime.now()))


def to_png(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def to_fb_raw(img, rotate=0):
    """Raw framebuffer bytes for direct `cat > /dev/fb0` write.
    Kindle Basic 3: 600x800 8bpp, line length 608 (600 px + 8 pad), rotation 3.
    STEP A confirmed 0deg is upright."""
    if rotate == 180:
        img = img.transpose(Image.ROTATE_180)
    w, h = img.size
    stride = 608
    pad = max(0, stride - w)
    raw = bytearray()
    px = img.load()
    for y in range(h):
        for x in range(w):
            raw.append(px[x, y])
        if pad:
            raw.extend(b"\x00" * pad)
    return bytes(raw)


def to_screensaver_png(img):
    """Render as screensaver-ready PNG (600x800 grayscale).
    linkss requires PNG, 600x800, grayscale (or color), no ICC profile."""
    if img.size != (CANVAS_W, CANVAS_H):
        img = img.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
    if img.mode != "L":
        img = img.convert("L")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ---- push to Kindle (PUSH: agent → serve.py → Kindle:9876 nc listener) ----
KINDLE_IP = os.environ.get("KINDLEDESK_KINDLE_IP", "")
PUSH_PORT = 9876
SS_PORT = 9877  # screensaver receiver on Kindle


def push_to_kindle(raw, ip=KINDLE_IP, port=PUSH_PORT):
    """Send raw framebuffer to Kindle push_recv.sh (nc listener). Immediate display."""
    if not ip:
        print("[push_to_kindle] KINDLEDESK_KINDLE_IP is not set", flush=True)
        return False
    try:
        s = socket.socket()
        s.settimeout(10)
        s.connect((ip, port))
        s.sendall(raw)
        s.close()
        return True
    except Exception as e:
        print(f"[push_to_kindle] {ip}:{port} failed: {e}", flush=True)
        return False


def push_screensaver_to_kindle(png_data, ip=KINDLE_IP, port=SS_PORT):
    """Send screensaver PNG to Kindle ss_recv.sh (nc listener).
    Kindle writes it to /mnt/us/linkss/screensavers/kindledesk_ss.png."""
    if not ip:
        print("[push_screensaver_to_kindle] KINDLEDESK_KINDLE_IP is not set", flush=True)
        return False
    try:
        s = socket.socket()
        s.settimeout(15)
        s.connect((ip, port))
        s.sendall(png_data)
        s.close()
        return True
    except Exception as e:
        print(f"[push_screensaver_to_kindle] {ip}:{port} failed: {e}", flush=True)
        return False


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, data, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, data):
        self._send(json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")

    def _read_json(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode("utf-8", "replace")
        return json.loads(body) if body else {}

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/card.png", "/test.png"):
            self._send(to_png(render_card()), "image/png")
        elif u.path == "/fb":
            rot = int(q.get("rotate", ["0"])[0])
            self._send(to_fb_raw(render_card(), rot), "application/octet-stream")
        elif u.path == "/snapshot":
            snap = widget_snapshot() or default_snapshot(datetime.now())
            self._send(json.dumps(snap, ensure_ascii=False).encode(), "application/json")
        elif u.path == "/widgets":
            self._send_json({"widgets": widget_snapshot(),
                             "types": WIDGET_TYPES, "slots": WIDGET_SLOTS})
        elif u.path == "/screensaver":
            png = to_screensaver_png(render_card())
            self._send(png, "image/png")
        else:
            self.send_error(404)

    def do_POST(self):
        from urllib.parse import urlparse
        u = urlparse(self.path)
        if u.path in ("/widget", "/widgets/preview"):
            try:
                data = self._read_json()
                raw_widgets = ([data] if u.path == "/widget"
                               else data.get("widgets", widget_snapshot()))
                if not isinstance(raw_widgets, list):
                    raise ValueError("widgets must be an array")
                widgets = [normalize_widget(item) for item in raw_widgets]
            except (TypeError, ValueError, json.JSONDecodeError) as e:
                self.send_error(400, str(e))
                return
            if u.path == "/widgets/preview":
                self._send(to_png(render_widget_card(widgets)), "image/png")
                return
            widget = widgets[0]
            _widget_cache[widget["slot"]] = widget
            img = render_card()
            pushed = push_to_kindle(to_png(img))
            self._send_json({"ok": True, "slot": widget["slot"],
                             "type": widget["type"],
                             "status": "delivered" if pushed else "queued"})
        elif u.path in ("/preview", "/push"):
            try:
                data = self._read_json()
                widget = normalize_widget({
                    "slot": "full", "type": "scratch",
                    "data": {"title": str(data.get("title", "Card"))[:80],
                             "text": str(data.get("body", ""))[:2000]},
                    "ttl": data.get("ttl", 600),
                })
            except (TypeError, ValueError, json.JSONDecodeError) as e:
                self.send_error(400, str(e))
                return
            if u.path == "/preview":
                self._send(to_png(render_widget_card([widget])), "image/png")
                return
            _widget_cache["full"] = widget
            pushed = push_to_kindle(to_png(render_card()))
            self._send_json({"ok": True, "slot": "full", "type": "scratch",
                             "status": "delivered" if pushed else "queued"})
        elif u.path == "/push/render":
            # render current default card + push (no override)
            img = render_card()
            png = to_png(img)
            pushed = push_to_kindle(png)
            msg = f"render+push: {'delivered' if pushed else 'Kindle offline'}"
            print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)
            self._send(msg.encode(), "text/plain")
        elif u.path == "/push/clear":
            _widget_cache.clear()
            # re-render default + push so screen updates immediately
            img = render_card()
            png = to_png(img)
            push_to_kindle(png)
            print(f"{datetime.now().strftime('%H:%M:%S')} PUSH cleared + re-pushed default", flush=True)
            self._send(b"cleared+pushed", "text/plain")
        elif u.path == "/screensaver/push":
            # push screensaver PNG to Kindle: write to linkss/screensavers/ via HTTP
            img = render_card()
            ss_png = to_screensaver_png(img)
            pushed = push_screensaver_to_kindle(ss_png)
            status = "delivered" if pushed else "Kindle offline"
            msg = f"screensaver push: {len(ss_png)} bytes → {status}"
            print(f"{datetime.now().strftime('%H:%M:%S')} {msg}", flush=True)
            self._send(msg.encode(), "text/plain")
        else:
            self.send_error(404)

    def do_DELETE(self):
        from urllib.parse import urlparse, parse_qs
        u = urlparse(self.path)
        if u.path != "/widget":
            self.send_error(404)
            return
        slot = parse_qs(u.query).get("slot", [""])[0]
        if slot:
            if slot not in WIDGET_SLOTS:
                self.send_error(400, f"unknown widget slot: {slot}")
                return
            _widget_cache.pop(slot, None)
        else:
            _widget_cache.clear()
        self._send_json({"ok": True, "cleared": slot or "all"})

    def log_message(self, fmt, *args):
        print(f"{datetime.now().strftime('%H:%M:%S')} {self.client_address[0]} - {fmt % args}", flush=True)


if __name__ == "__main__":
    print("warming up weather (one-time, ~10s)...", flush=True)
    fetch_weather()
    print("starting KindleDesk card server on 0.0.0.0:8000", flush=True)
    with socketserver.ThreadingTCPServer(("0.0.0.0", 8000), Handler) as s:
        s.serve_forever()
