"""SVG comic renderer in the spirit of xkcd.

Multi-character scenes, props, hand-drawn wobble, dialogue split between speakers.
Pure stdlib — no external deps.
"""
from __future__ import annotations

import html
import math
import random
import re
import textwrap
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

# ---------- Layout constants ----------

PANEL_W = 380
PANEL_H = 340
GUTTER = 14
PADDING = 16
HEADER_H = 30
STROKE = 2.0
THIN = 1.4
BG = "#f1e7cc"  # old-book parchment, must match assets/css/xkcd.css body background

# ---------- Wobble (hand-drawn feel) ----------

def _wobble_path(rng: random.Random, points: List[Tuple[float, float]], tightness: float = 1.6) -> str:
    """Cubic bezier path through points with subtle perturbation."""
    if not points:
        return ""
    out = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    for i in range(1, len(points)):
        x1, y1 = points[i - 1]
        x2, y2 = points[i]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        t1 = rng.uniform(-tightness, tightness)
        t2 = rng.uniform(-tightness, tightness)
        cx1 = x1 + dx / 3 + nx * t1
        cy1 = y1 + dy / 3 + ny * t1
        cx2 = x1 + 2 * dx / 3 + nx * t2
        cy2 = y1 + 2 * dy / 3 + ny * t2
        out.append(f"C {cx1:.2f} {cy1:.2f}, {cx2:.2f} {cy2:.2f}, {x2:.2f} {y2:.2f}")
    return " ".join(out)


def _line(rng: random.Random, x1: float, y1: float, x2: float, y2: float, stroke: float = STROKE) -> str:
    d = _wobble_path(rng, [(x1, y1), (x2, y2)], tightness=1.0)
    return f'<path d="{d}" fill="none" stroke="black" stroke-width="{stroke}" stroke-linecap="round"/>'


def _polyline(rng: random.Random, pts: List[Tuple[float, float]], stroke: float = STROKE, close: bool = False, fill: str = "none") -> str:
    if close:
        pts = pts + [pts[0]]
    d = _wobble_path(rng, pts, tightness=0.8)
    return f'<path d="{d}" fill="{fill}" stroke="black" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"/>'


def _wobbly_circle(rng: random.Random, cx: float, cy: float, r: float, stroke: float = STROKE, fill: str = "none") -> str:
    pts = []
    n = 16
    for i in range(n):
        a = 2 * math.pi * i / n
        wob = rng.uniform(-0.6, 0.6)
        pts.append((cx + (r + wob) * math.cos(a), cy + (r + wob) * math.sin(a)))
    d = _wobble_path(rng, pts + [pts[0]], tightness=0.4)
    return f'<path d="{d}" fill="{fill}" stroke="black" stroke-width="{stroke}" stroke-linecap="round"/>'


# ---------- Characters ----------

@dataclass
class Character:
    kind: str          # cueball | megan | hairbun | beret | hatguy
    cx: float          # head center x
    base_y: float      # ground y where feet stand
    pose: str = "standing"  # standing | sitting | pointing_left | pointing_right | arms_up | shrug | thinking
    facing: int = 1    # 1 = right, -1 = left

    @property
    def head_r(self) -> float:
        return 12.0

    @property
    def head_cy(self) -> float:
        # head center y; sitting characters sit lower (head closer to base_y)
        if self.pose == "sitting":
            return self.base_y - 60
        return self.base_y - 92

    @property
    def mouth_xy(self) -> Tuple[float, float]:
        # rough mouth point on the head — bubble tail aims here
        return (self.cx + self.facing * (self.head_r - 4), self.head_cy + 4)

    def draw(self, rng: random.Random) -> str:
        out = []
        # body geometry
        head_r = self.head_r
        hcy = self.head_cy
        body_top = hcy + head_r
        if self.pose == "sitting":
            body_bot = body_top + 28
        else:
            body_bot = body_top + 42
        # head
        out.append(_wobbly_circle(rng, self.cx, hcy, head_r))
        # hair / hat
        out.extend(self._draw_hair(rng))
        # body
        out.append(_line(rng, self.cx, body_top, self.cx, body_bot))
        # arms + legs depending on pose
        out.extend(self._draw_limbs(rng, body_top, body_bot))
        return "\n    ".join(out)

    def _draw_hair(self, rng: random.Random) -> List[str]:
        cx, cy, r = self.cx, self.head_cy, self.head_r
        if self.kind == "cueball":
            return []
        if self.kind == "megan":
            # long straight hair down past shoulders
            return [
                _line(rng, cx - r, cy - 2, cx - r - 2, cy + r + 18),
                _line(rng, cx - r + 2, cy - 4, cx - r, cy + r + 22),
                _line(rng, cx + r, cy - 2, cx + r + 2, cy + r + 18),
                _line(rng, cx - 4, cy - r, cx - 8, cy - r - 2, stroke=THIN),
                _line(rng, cx + 4, cy - r, cx + 8, cy - r - 2, stroke=THIN),
            ]
        if self.kind == "hairbun":
            return [
                _wobbly_circle(rng, cx, cy - r - 6, 6),
                _line(rng, cx - r + 1, cy + 1, cx - r - 1, cy + r),
                _line(rng, cx + r - 1, cy + 1, cx + r + 1, cy + r),
            ]
        if self.kind == "beret":
            return [
                _polyline(rng, [(cx - r - 2, cy - r + 2), (cx + r + 2, cy - r + 2),
                                (cx + r - 2, cy - r - 6), (cx - r + 2, cy - r - 6)], close=True, fill="black"),
                _wobbly_circle(rng, cx + r - 2, cy - r - 6, 2, fill="black"),
            ]
        if self.kind == "hatguy":
            # black trilby
            return [
                _polyline(rng, [(cx - r - 4, cy - r + 2), (cx + r + 4, cy - r + 2),
                                (cx + r, cy - r - 8), (cx - r, cy - r - 8)], close=True, fill="black"),
                _line(rng, cx - r - 6, cy - r + 2, cx + r + 6, cy - r + 2, stroke=STROKE),
            ]
        return []

    def _draw_limbs(self, rng: random.Random, body_top: float, body_bot: float) -> List[str]:
        cx = self.cx
        f = self.facing
        out: List[str] = []
        if self.pose == "standing":
            # arms hanging
            out += [
                _line(rng, cx, body_top + 8, cx - 16, body_top + 28),
                _line(rng, cx, body_top + 8, cx + 16, body_top + 28),
                _line(rng, cx, body_bot, cx - 12, body_bot + 26),
                _line(rng, cx, body_bot, cx + 12, body_bot + 26),
            ]
        elif self.pose == "pointing_right":
            out += [
                _line(rng, cx, body_top + 10, cx + 28, body_top + 6),
                _line(rng, cx, body_top + 10, cx - 16, body_top + 28),
                _line(rng, cx, body_bot, cx - 12, body_bot + 26),
                _line(rng, cx, body_bot, cx + 12, body_bot + 26),
            ]
        elif self.pose == "pointing_left":
            out += [
                _line(rng, cx, body_top + 10, cx - 28, body_top + 6),
                _line(rng, cx, body_top + 10, cx + 16, body_top + 28),
                _line(rng, cx, body_bot, cx - 12, body_bot + 26),
                _line(rng, cx, body_bot, cx + 12, body_bot + 26),
            ]
        elif self.pose == "arms_up":
            out += [
                _line(rng, cx, body_top + 6, cx - 22, body_top - 22),
                _line(rng, cx, body_top + 6, cx + 22, body_top - 22),
                _line(rng, cx, body_bot, cx - 12, body_bot + 26),
                _line(rng, cx, body_bot, cx + 12, body_bot + 26),
            ]
        elif self.pose == "shrug":
            out += [
                _line(rng, cx, body_top + 8, cx - 22, body_top - 4),
                _line(rng, cx - 22, body_top - 4, cx - 26, body_top + 14),
                _line(rng, cx, body_top + 8, cx + 22, body_top - 4),
                _line(rng, cx + 22, body_top - 4, cx + 26, body_top + 14),
                _line(rng, cx, body_bot, cx - 12, body_bot + 26),
                _line(rng, cx, body_bot, cx + 12, body_bot + 26),
            ]
        elif self.pose == "thinking":
            # one hand to chin
            out += [
                _line(rng, cx, body_top + 10, cx + f * 14, body_top - 4),
                _line(rng, cx + f * 14, body_top - 4, cx + f * 6, self.head_cy + 6),
                _line(rng, cx, body_top + 10, cx - f * 16, body_top + 28),
                _line(rng, cx, body_bot, cx - 12, body_bot + 26),
                _line(rng, cx, body_bot, cx + 12, body_bot + 26),
            ]
        elif self.pose == "sitting":
            # legs out front, hands resting
            out += [
                _line(rng, cx, body_top + 14, cx - 16, body_top + 26),
                _line(rng, cx, body_top + 14, cx + 16, body_top + 26),
                _line(rng, cx, body_bot, cx + 24, body_bot),
                _line(rng, cx + 24, body_bot, cx + 26, body_bot + 18),
                _line(rng, cx, body_bot, cx - 8, body_bot + 18),
            ]
        else:
            out += [
                _line(rng, cx, body_top + 8, cx - 16, body_top + 28),
                _line(rng, cx, body_top + 8, cx + 16, body_top + 28),
            ]
        return out


# ---------- Props ----------

def prop_floor(rng: random.Random, x: float, y: float, w: float) -> str:
    return _line(rng, x, y, x + w, y, stroke=THIN)


def prop_tv(rng: random.Random, x: float, y: float, w: float = 80, h: float = 56) -> str:
    out = [
        # bezel
        _polyline(rng, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True),
        # screen inset
        _polyline(rng, [(x + 6, y + 6), (x + w - 6, y + 6), (x + w - 6, y + h - 6), (x + 6, y + h - 6)], close=True),
        # stand
        _line(rng, x + w / 2 - 14, y + h, x + w / 2 + 14, y + h, stroke=THIN),
        _line(rng, x + w / 2, y + h, x + w / 2, y + h + 8, stroke=THIN),
        _line(rng, x + w / 2 - 14, y + h + 10, x + w / 2 + 14, y + h + 10, stroke=THIN),
        # squiggle "showing something"
        _polyline(rng, [(x + 12, y + h - 14), (x + 22, y + 16), (x + 36, y + h - 12),
                        (x + 50, y + 18), (x + w - 14, y + h - 16)]),
    ]
    return "\n    ".join(out)


def prop_couch(rng: random.Random, x: float, y: float, w: float = 140, h: float = 36) -> str:
    # y is the seat top
    out = [
        # back rest
        _polyline(rng, [(x - 6, y - 30), (x + w + 6, y - 30), (x + w + 6, y), (x - 6, y)], close=True),
        # seat front
        _polyline(rng, [(x - 6, y), (x + w + 6, y), (x + w + 6, y + h), (x - 6, y + h)], close=True),
        # arms
        _polyline(rng, [(x - 14, y - 18), (x - 6, y - 18), (x - 6, y + h), (x - 14, y + h)], close=True),
        _polyline(rng, [(x + w + 6, y - 18), (x + w + 14, y - 18), (x + w + 14, y + h), (x + w + 6, y + h)], close=True),
        # cushion divider
        _line(rng, x + w / 2, y, x + w / 2, y + h, stroke=THIN),
    ]
    return "\n    ".join(out)


def prop_cinema_seats(rng: random.Random, x: float, y: float, w: float) -> str:
    # silhouette of seat backs in the foreground, two seats
    sw = (w - 20) / 2
    out = []
    for i in range(2):
        sx = x + 10 + i * (sw + 10)
        out.append(_polyline(rng, [
            (sx, y), (sx + sw, y),
            (sx + sw - 4, y - 30), (sx + sw - 12, y - 50),
            (sx + 12, y - 50), (sx + 4, y - 30),
        ], close=True, fill="#222"))
    return "\n    ".join(out)


def prop_screen(rng: random.Random, x: float, y: float, w: float, h: float) -> str:
    out = [
        _polyline(rng, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, fill="#111"),
        # subtle internal frame
        _polyline(rng, [(x + 4, y + 4), (x + w - 4, y + 4), (x + w - 4, y + h - 4), (x + 4, y + h - 4)], close=True),
    ]
    return "\n    ".join(out)


def prop_popcorn(rng: random.Random, x: float, y: float) -> str:
    w, h = 24, 32
    out = [
        # bucket
        _polyline(rng, [(x, y), (x + w, y), (x + w - 2, y + h), (x + 2, y + h)], close=True),
        # red stripes
        _line(rng, x + 6, y + 2, x + 6, y + h - 2, stroke=THIN),
        _line(rng, x + 12, y + 2, x + 12, y + h - 2, stroke=THIN),
        _line(rng, x + 18, y + 2, x + 18, y + h - 2, stroke=THIN),
        # popcorn pieces above
        _wobbly_circle(rng, x + 6, y - 2, 3),
        _wobbly_circle(rng, x + 13, y - 6, 4),
        _wobbly_circle(rng, x + 20, y - 1, 3),
    ]
    return "\n    ".join(out)


def prop_star(rng: random.Random, cx: float, cy: float, r: float = 14) -> str:
    pts: List[Tuple[float, float]] = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rad * math.cos(angle), cy + rad * math.sin(angle)))
    return _polyline(rng, pts, close=True)


def prop_clapper(rng: random.Random, x: float, y: float) -> str:
    w, h = 60, 44
    out = [
        # body
        _polyline(rng, [(x, y + 12), (x + w, y + 12), (x + w, y + h), (x, y + h)], close=True),
        # top stick
        _polyline(rng, [(x, y), (x + w, y), (x + w, y + 12), (x, y + 12)], close=True, fill=BG),
        # diagonal stripes on top stick
        _polyline(rng, [(x + 4, y + 12), (x + 16, y), (x + 24, y), (x + 12, y + 12)], close=True, fill="black"),
        _polyline(rng, [(x + 28, y + 12), (x + 40, y), (x + 48, y), (x + 36, y + 12)], close=True, fill="black"),
    ]
    return "\n    ".join(out)


def prop_thought_bubble(rng: random.Random, x: float, y: float, w: float, lines: List[str], char_head: Tuple[float, float]) -> str:
    """Cloud-shaped bubble + small puffs leading to character head."""
    line_h = 16
    h = max(line_h * len(lines), line_h) + 22
    cx = x + w / 2
    cy = y + h / 2
    bumps: List[Tuple[float, float]] = []
    n = 14
    for i in range(n):
        a = 2 * math.pi * i / n
        rx = (w / 2 + 4) + (4 if i % 2 == 0 else -2)
        ry = (h / 2 + 4) + (4 if i % 2 == 0 else -2)
        bumps.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    cloud = _polyline(rng, bumps, close=True, fill=BG)
    # trail of small circles down to head
    hx, hy = char_head
    trail = []
    for i, t in enumerate([0.55, 0.75, 0.9]):
        tx = cx + (hx - cx) * t
        ty = (y + h) + ((hy - (y + h)) * t * 0.8)
        trail.append(_wobbly_circle(rng, tx, ty, 4 - i, fill=BG))
    text = _bubble_text(x + 8, y + 18, w - 16, lines)
    return cloud + "\n    " + "\n    ".join(trail) + "\n    " + text


# ---------- Speech bubble ----------

def _bubble_text(x: float, y: float, w: float, lines: List[str]) -> str:
    line_h = 16
    cx = x + w / 2
    tspans = "".join(
        f'<tspan x="{cx:.1f}" dy="{0 if i == 0 else line_h}">{html.escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<text x="{cx:.1f}" y="{y:.1f}" text-anchor="middle" '
        f'font-family="Comic Neue, Comic Sans MS, cursive" font-size="13" fill="black">'
        f'{tspans}</text>'
    )


def speech_bubble(rng: random.Random, x: float, y: float, w: float, lines: List[str], tail_to: Tuple[float, float]) -> str:
    line_h = 16
    h = max(line_h * len(lines), line_h) + 22
    # rounded rectangle as wobbly polyline
    rx = 10
    pts = [
        (x + rx, y), (x + w - rx, y),
        (x + w, y + rx), (x + w, y + h - rx),
        (x + w - rx, y + h), (x + rx, y + h),
        (x, y + h - rx), (x, y + rx),
    ]
    rect = _polyline(rng, pts, close=True, fill=BG)

    # tail: from bubble edge nearest the target, to target point
    tx, ty = tail_to
    bx = max(x + 12, min(x + w - 12, tx))
    by = y + h
    if ty < y:  # target above bubble (rare)
        by = y
    seam_y = by
    tail = _polyline(rng, [(bx - 7, by), (tx, ty), (bx + 7, by)], close=False, fill=BG)
    # cover the seam where tail meets bubble
    seam_cover = (
        f'<line x1="{bx - 6}" y1="{seam_y}" x2="{bx + 6}" y2="{seam_y}" '
        f'stroke="{BG}" stroke-width="2.4"/>'
    )
    return rect + "\n    " + tail + "\n    " + seam_cover + "\n    " + _bubble_text(x + 8, y + 18, w - 16, lines)


# ---------- Text utilities ----------

def _wrap(text: str, max_chars: int) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return [""]
    return textwrap.wrap(text, width=max_chars, break_long_words=False, break_on_hyphens=False)[:5] or [text[:max_chars]]


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?…])\s+(?=[A-Z\"'(])", text)
    return [p.strip() for p in parts if p and p.strip()]


def _truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0]
    return cut + "…"


def _split_dialogue(review: str, n_panels: int) -> List[List[str]]:
    """Return one list of utterances per panel (1 or 2 utterances each)."""
    sentences = _split_sentences(review) or [review]
    # collapse very short consecutive sentences
    merged: List[str] = []
    for s in sentences:
        if merged and len(merged[-1]) + len(s) < 60:
            merged[-1] = merged[-1] + " " + s
        else:
            merged.append(s)
    sentences = merged
    # pack into panels round-robin so panels stay roughly balanced
    panels: List[List[str]] = [[] for _ in range(n_panels)]
    target_chars = max(60, sum(len(s) for s in sentences) // n_panels)
    pi = 0
    for s in sentences:
        s = _truncate(s, 110)
        if pi >= n_panels:
            panels[-1].append(s)
            continue
        panels[pi].append(s)
        if sum(len(x) for x in panels[pi]) >= target_chars or len(panels[pi]) >= 2:
            pi += 1
    # ensure no empty panels
    for i, p in enumerate(panels):
        if not p:
            panels[i] = [_truncate(sentences[i % len(sentences)], 80) if sentences else ""]
    return panels


# ---------- Scenes ----------

CHARACTERS = ["cueball", "megan", "hairbun", "beret", "hatguy"]


@dataclass
class PanelDraw:
    body: str
    bubbles: List[Tuple[Tuple[float, float, float], List[str], Tuple[float, float]]] = field(default_factory=list)


def scene_couch_tv(rng: random.Random, panel_x: float, panel_y: float, dialogue: List[str], char_a: str, char_b: str) -> PanelDraw:
    floor_y = panel_y + PANEL_H - 30
    couch_x = panel_x + 100
    couch_y = floor_y - 26
    body_parts = [
        prop_floor(rng, panel_x + 10, floor_y, PANEL_W - 20),
        prop_tv(rng, panel_x + 14, floor_y - 76),
        prop_couch(rng, couch_x, couch_y),
    ]
    a = Character(kind=char_a, cx=couch_x + 30, base_y=couch_y + 30, pose="sitting", facing=-1)
    b = Character(kind=char_b, cx=couch_x + 110, base_y=couch_y + 30, pose="sitting", facing=-1)
    body_parts += [a.draw(rng), b.draw(rng)]
    bubbles: List[Tuple[Tuple[float, float, float], List[str], Tuple[float, float]]] = []
    if dialogue:
        bubbles.append(_bubble_for(panel_x, panel_y, dialogue[0], a.mouth_xy, side="left"))
    if len(dialogue) > 1:
        bubbles.append(_bubble_for(panel_x, panel_y, dialogue[1], b.mouth_xy, side="right"))
    return PanelDraw("\n    ".join(body_parts), bubbles)


def scene_cinema(rng: random.Random, panel_x: float, panel_y: float, dialogue: List[str], char_a: str, char_b: str) -> PanelDraw:
    floor_y = panel_y + PANEL_H - 16
    screen_y = panel_y + 36
    screen_h = 80
    body_parts = [
        prop_screen(rng, panel_x + 30, screen_y, PANEL_W - 60, screen_h),
    ]
    # two cinema seats foreground
    seats_y = floor_y - 8
    body_parts.append(prop_cinema_seats(rng, panel_x + 40, seats_y, PANEL_W - 80))
    # two heads peeking above seats
    head_y = seats_y - 60
    a = Character(kind=char_a, cx=panel_x + PANEL_W * 0.32, base_y=head_y + 90, pose="sitting", facing=1)
    b = Character(kind=char_b, cx=panel_x + PANEL_W * 0.68, base_y=head_y + 90, pose="sitting", facing=-1)
    # only render heads + a bit of body (cinema seat hides legs)
    body_parts.append(_wobbly_circle(rng, a.cx, a.head_cy, a.head_r))
    body_parts.append(_wobbly_circle(rng, b.cx, b.head_cy, b.head_r))
    body_parts += a._draw_hair(rng) + b._draw_hair(rng)
    bubbles = []
    if dialogue:
        bubbles.append(_bubble_for(panel_x, panel_y, dialogue[0], a.mouth_xy, side="left"))
    if len(dialogue) > 1:
        bubbles.append(_bubble_for(panel_x, panel_y, dialogue[1], b.mouth_xy, side="right"))
    return PanelDraw("\n    ".join(body_parts), bubbles)


def scene_standing_chat(rng: random.Random, panel_x: float, panel_y: float, dialogue: List[str], char_a: str, char_b: str) -> PanelDraw:
    floor_y = panel_y + PANEL_H - 24
    a = Character(kind=char_a, cx=panel_x + PANEL_W * 0.32, base_y=floor_y, pose=rng.choice(["standing", "shrug", "pointing_right"]), facing=1)
    b = Character(kind=char_b, cx=panel_x + PANEL_W * 0.68, base_y=floor_y, pose=rng.choice(["standing", "shrug", "pointing_left"]), facing=-1)
    body_parts = [
        prop_floor(rng, panel_x + 10, floor_y, PANEL_W - 20),
        a.draw(rng),
        b.draw(rng),
    ]
    bubbles = []
    if dialogue:
        bubbles.append(_bubble_for(panel_x, panel_y, dialogue[0], a.mouth_xy, side="left"))
    if len(dialogue) > 1:
        bubbles.append(_bubble_for(panel_x, panel_y, dialogue[1], b.mouth_xy, side="right"))
    return PanelDraw("\n    ".join(body_parts), bubbles)


def scene_thinking_alone(rng: random.Random, panel_x: float, panel_y: float, dialogue: List[str], char_a: str, char_b: str) -> PanelDraw:
    floor_y = panel_y + PANEL_H - 24
    a = Character(kind=char_a, cx=panel_x + PANEL_W * 0.4, base_y=floor_y, pose="thinking", facing=1)
    body_parts = [prop_floor(rng, panel_x + 10, floor_y, PANEL_W - 20), a.draw(rng)]
    text = " ".join(dialogue) if dialogue else ""
    lines = _wrap(text, 24)
    # cloud bubble in upper right
    bw = 200
    bh = max(16 * len(lines), 16) + 22
    bx = panel_x + PANEL_W - bw - 14
    by = panel_y + 14
    body_parts.append(prop_thought_bubble(rng, bx, by, bw, lines, (a.cx + 10, a.head_cy - 10)))
    return PanelDraw("\n    ".join(body_parts), [])


def scene_excited_with_star(rng: random.Random, panel_x: float, panel_y: float, dialogue: List[str], char_a: str, char_b: str) -> PanelDraw:
    floor_y = panel_y + PANEL_H - 24
    a = Character(kind=char_a, cx=panel_x + PANEL_W * 0.45, base_y=floor_y, pose="arms_up", facing=1)
    body_parts = [
        prop_floor(rng, panel_x + 10, floor_y, PANEL_W - 20),
        prop_star(rng, panel_x + PANEL_W * 0.78, panel_y + 80, 18),
        prop_star(rng, panel_x + PANEL_W * 0.22, panel_y + 60, 12),
        a.draw(rng),
    ]
    bubbles = []
    if dialogue:
        bubbles.append(_bubble_for(panel_x, panel_y, dialogue[0], a.mouth_xy, side="left"))
    return PanelDraw("\n    ".join(body_parts), bubbles)


def scene_popcorn_aside(rng: random.Random, panel_x: float, panel_y: float, dialogue: List[str], char_a: str, char_b: str) -> PanelDraw:
    floor_y = panel_y + PANEL_H - 24
    a = Character(kind=char_a, cx=panel_x + PANEL_W * 0.32, base_y=floor_y, pose="standing", facing=1)
    b = Character(kind=char_b, cx=panel_x + PANEL_W * 0.68, base_y=floor_y, pose="pointing_left", facing=-1)
    body_parts = [
        prop_floor(rng, panel_x + 10, floor_y, PANEL_W - 20),
        prop_popcorn(rng, a.cx + 14, floor_y - 36),
        a.draw(rng),
        b.draw(rng),
    ]
    bubbles = []
    if dialogue:
        bubbles.append(_bubble_for(panel_x, panel_y, dialogue[0], a.mouth_xy, side="left"))
    if len(dialogue) > 1:
        bubbles.append(_bubble_for(panel_x, panel_y, dialogue[1], b.mouth_xy, side="right"))
    return PanelDraw("\n    ".join(body_parts), bubbles)


def scene_clapperboard(rng: random.Random, panel_x: float, panel_y: float, dialogue: List[str], char_a: str, char_b: str) -> PanelDraw:
    floor_y = panel_y + PANEL_H - 24
    a = Character(kind=char_a, cx=panel_x + PANEL_W * 0.66, base_y=floor_y, pose="pointing_left", facing=-1)
    body_parts = [
        prop_floor(rng, panel_x + 10, floor_y, PANEL_W - 20),
        prop_clapper(rng, panel_x + PANEL_W * 0.18, floor_y - 60),
        a.draw(rng),
    ]
    bubbles = []
    if dialogue:
        bubbles.append(_bubble_for(panel_x, panel_y, dialogue[0], a.mouth_xy, side="right"))
    return PanelDraw("\n    ".join(body_parts), bubbles)


SCENE_LIBRARY: List[Tuple[str, Callable, float]] = [
    ("couch_tv", scene_couch_tv, 1.4),
    ("cinema", scene_cinema, 1.0),
    ("standing_chat", scene_standing_chat, 1.4),
    ("thinking", scene_thinking_alone, 0.7),
    ("excited", scene_excited_with_star, 0.7),
    ("popcorn", scene_popcorn_aside, 0.8),
    ("clapper", scene_clapperboard, 0.6),
]


def _bubble_for(panel_x: float, panel_y: float, text: str, mouth: Tuple[float, float], side: str) -> Tuple[Tuple[float, float, float], List[str], Tuple[float, float]]:
    lines = _wrap(text, 22)
    bw = min(170, max(110, max(len(line) for line in lines) * 8 + 24))
    if side == "left":
        bx = panel_x + 10
    else:
        bx = panel_x + PANEL_W - bw - 10
    by = panel_y + 14
    return ((bx, by, bw), lines, mouth)


# ---------- Public API ----------

def render_comic(
    *,
    comic_id: int,
    title: str,
    film: str,
    year: str,
    rating_stars: str,
    review_text: str,
) -> Tuple[str, str]:
    rng = random.Random(comic_id * 9973 + 17)

    # decide panel count based on review length
    sentences = _split_sentences(review_text) or [review_text]
    if len(sentences) <= 1 and len(review_text) < 80:
        n_panels = 1
    elif len(sentences) <= 3:
        n_panels = 2
    else:
        n_panels = 3
    n_panels = max(1, min(3, n_panels))

    dialogue_per_panel = _split_dialogue(review_text, n_panels)

    # pick scene per panel (bias: panel 0 sets scene; panels 1-2 vary)
    weights = [w for _, _, w in SCENE_LIBRARY]
    total = sum(weights)
    scenes_picked: List[Tuple[str, Callable]] = []
    for _ in range(n_panels):
        roll = rng.uniform(0, total)
        acc = 0.0
        for name, fn, w in SCENE_LIBRARY:
            acc += w
            if roll <= acc:
                scenes_picked.append((name, fn))
                break

    # cast: two distinct characters, stable per comic
    cast = rng.sample(CHARACTERS, 2)
    char_a, char_b = cast[0], cast[1]

    # layout
    width = PANEL_W * n_panels + GUTTER * (n_panels - 1) + PADDING * 2
    height = PANEL_H + PADDING * 2 + HEADER_H

    # header
    rating_part = f" {html.escape(rating_stars)}" if rating_stars else ""
    year_part = f" ({year})" if year else ""
    header = (
        f'<text x="{width / 2:.1f}" y="{PADDING + 18}" text-anchor="middle" '
        f'font-family="Comic Neue, Comic Sans MS, cursive" font-size="16" font-weight="700" fill="black">'
        f'#{comic_id:03d} — {html.escape(film)}{year_part}{rating_part}</text>'
    )

    panel_blocks: List[str] = []
    for i in range(n_panels):
        px = PADDING + i * (PANEL_W + GUTTER)
        py = PADDING + HEADER_H
        scene_name, scene_fn = scenes_picked[i]
        # alternate which character "leads" so dialogue feels back-and-forth
        if i % 2 == 0:
            cA, cB = char_a, char_b
        else:
            cA, cB = char_b, char_a
        drawn = scene_fn(rng, px, py, dialogue_per_panel[i], cA, cB)
        # frame
        frame = _polyline(
            rng,
            [(px, py), (px + PANEL_W, py), (px + PANEL_W, py + PANEL_H), (px, py + PANEL_H)],
            close=True,
        )
        # bubbles drawn last so they layer above figures
        bubble_svg = []
        for (bx, by, bw), lines, mouth in drawn.bubbles:
            bubble_svg.append(speech_bubble(rng, bx, by, bw, lines, mouth))
        panel_blocks.append(
            f'<g class="panel">\n    {frame}\n    {drawn.body}\n    '
            + "\n    ".join(bubble_svg)
            + "\n  </g>"
        )

    # alt-text: most punchy sentence
    alt_candidates = [s for s in _split_sentences(review_text) if 0 < len(s) <= 140]
    alt = max(alt_candidates, key=len) if alt_candidates else (sentences[0] if sentences else title)
    alt = alt.strip()
    if len(alt) > 200:
        alt = _truncate(alt, 200)

    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{html.escape(title)}">\n'
        f'  <rect width="100%" height="100%" fill="{BG}"/>\n'
        f'  {header}\n  '
        + "\n  ".join(panel_blocks)
        + "\n</svg>\n"
    )
    return svg, alt
