"""SVG comic renderer. Pure stdlib — no external deps."""
from __future__ import annotations

import html
import random
import re
import textwrap
from typing import List, Tuple

PANEL_W = 300
PANEL_H = 340
GUTTER = 12
PADDING = 14

POSES = [
    # Each pose returns SVG path/circle elements drawn relative to (cx, baseline).
    # Stick figure: head circle + body line + arms + legs.
    "standing",
    "pointing_right",
    "arms_up",
    "shrug",
    "sitting",
    "thinking",
]


def _stickman(cx: float, base_y: float, pose: str) -> str:
    head_r = 14
    head_cy = base_y - 90
    body_top = head_cy + head_r
    body_bot = body_top + 40
    parts = [
        f'<circle cx="{cx}" cy="{head_cy}" r="{head_r}" fill="none" stroke="black" stroke-width="2.2"/>',
        f'<line x1="{cx}" y1="{body_top}" x2="{cx}" y2="{body_bot}" stroke="black" stroke-width="2.2"/>',
    ]
    if pose == "standing":
        parts += [
            f'<line x1="{cx}" y1="{body_top + 12}" x2="{cx - 18}" y2="{body_top + 30}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_top + 12}" x2="{cx + 18}" y2="{body_top + 30}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot}" x2="{cx - 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot}" x2="{cx + 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
        ]
    elif pose == "pointing_right":
        parts += [
            f'<line x1="{cx}" y1="{body_top + 12}" x2="{cx + 26}" y2="{body_top + 8}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_top + 12}" x2="{cx - 16}" y2="{body_top + 30}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot}" x2="{cx - 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot}" x2="{cx + 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
        ]
    elif pose == "arms_up":
        parts += [
            f'<line x1="{cx}" y1="{body_top + 6}" x2="{cx - 22}" y2="{body_top - 18}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_top + 6}" x2="{cx + 22}" y2="{body_top - 18}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot}" x2="{cx - 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot}" x2="{cx + 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
        ]
    elif pose == "shrug":
        parts += [
            f'<line x1="{cx}" y1="{body_top + 10}" x2="{cx - 22}" y2="{body_top - 4}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx - 22}" y1="{body_top - 4}" x2="{cx - 26}" y2="{body_top + 14}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_top + 10}" x2="{cx + 22}" y2="{body_top - 4}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx + 22}" y1="{body_top - 4}" x2="{cx + 26}" y2="{body_top + 14}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot}" x2="{cx - 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot}" x2="{cx + 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
        ]
    elif pose == "sitting":
        parts = [
            f'<circle cx="{cx}" cy="{head_cy + 10}" r="{head_r}" fill="none" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_top + 10}" x2="{cx}" y2="{body_bot + 4}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_top + 22}" x2="{cx - 18}" y2="{body_top + 36}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_top + 22}" x2="{cx + 18}" y2="{body_top + 36}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot + 4}" x2="{cx + 26}" y2="{body_bot + 4}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx + 26}" y1="{body_bot + 4}" x2="{cx + 26}" y2="{body_bot + 30}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot + 4}" x2="{cx - 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
        ]
    elif pose == "thinking":
        parts += [
            f'<line x1="{cx}" y1="{body_top + 12}" x2="{cx - 18}" y2="{body_top + 30}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_top + 12}" x2="{cx + 8}" y2="{body_top - 6}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx + 8}" y1="{body_top - 6}" x2="{cx + 4}" y2="{head_cy - 4}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot}" x2="{cx - 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
            f'<line x1="{cx}" y1="{body_bot}" x2="{cx + 14}" y2="{body_bot + 28}" stroke="black" stroke-width="2.2"/>',
        ]
    return "\n    ".join(parts)


def _wrap_text(text: str, max_chars: int = 22) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return [""]
    lines: List[str] = []
    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(paragraph, width=max_chars, break_long_words=False, break_on_hyphens=False)
        lines.extend(wrapped or [""])
    return lines[:5]  # cap at 5 lines per bubble


def _speech_bubble(x: float, y: float, w: float, lines: List[str], tail_to: Tuple[float, float]) -> str:
    line_h = 16
    text_h = max(line_h * len(lines), line_h)
    h = text_h + 22
    rx = 12
    bubble = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
        f'fill="white" stroke="black" stroke-width="1.6"/>'
    )
    # tail: small triangle from bubble bottom-center toward tail_to
    tx, ty = tail_to
    bx = x + w / 2
    by = y + h
    tail = (
        f'<polygon points="{bx - 8},{by - 1} {bx + 8},{by - 1} {tx},{ty}" '
        f'fill="white" stroke="black" stroke-width="1.6"/>'
    )
    # Cover the seam where tail meets bubble
    seam = f'<line x1="{bx - 7}" y1="{by}" x2="{bx + 7}" y2="{by}" stroke="white" stroke-width="2.2"/>'
    text_y_start = y + 18
    tspans = "".join(
        f'<tspan x="{x + w / 2}" dy="{0 if i == 0 else line_h}">{html.escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    text_el = (
        f'<text x="{x + w / 2}" y="{text_y_start}" text-anchor="middle" '
        f'font-family="Comic Neue, Comic Sans MS, cursive" font-size="13" fill="black">'
        f'{tspans}</text>'
    )
    return f"{bubble}\n    {tail}\n    {seam}\n    {text_el}"


def _split_into_panels(review: str, max_panels: int = 3) -> List[str]:
    review = re.sub(r"\s+", " ", review).strip()
    if not review:
        return [""]
    sentences = re.split(r"(?<=[.!?…])\s+(?=[A-Z\"'(])|\n+", review)
    sentences = [s.strip() for s in sentences if s and s.strip()]
    if not sentences:
        return [review[:200]]
    panels: List[str] = []
    current = ""
    target = 80
    for s in sentences:
        if len(s) > 160:
            s = s[:157].rsplit(" ", 1)[0] + "…"
        if not current:
            current = s
        elif len(current) + len(s) + 1 <= target:
            current = f"{current} {s}"
        else:
            panels.append(current)
            current = s
        if len(panels) >= max_panels:
            break
    if current and len(panels) < max_panels:
        panels.append(current)
    return panels[:max_panels] or [review[:200]]


def render_comic(
    *,
    comic_id: int,
    title: str,
    film: str,
    year: str,
    rating_stars: str,
    review_text: str,
) -> Tuple[str, str]:
    """Return (svg_string, alt_text)."""
    rng = random.Random(comic_id * 9973 + 17)

    panels = _split_into_panels(review_text)
    n = max(1, min(3, len(panels)))
    panels = panels[:n]

    width = PANEL_W * n + GUTTER * (n - 1) + PADDING * 2
    height = PANEL_H + PADDING * 2 + 30  # extra for header strip

    # Header strip with rating
    header_y = PADDING
    header = (
        f'<text x="{width / 2}" y="{header_y + 18}" text-anchor="middle" '
        f'font-family="Comic Neue, Comic Sans MS, cursive" font-size="15" font-weight="700" fill="black">'
        f'#{comic_id:03d} — {html.escape(film)}{(" (" + year + ")") if year else ""} {html.escape(rating_stars)}'
        f'</text>'
    )

    panel_svgs: List[str] = []
    for i, line in enumerate(panels):
        x = PADDING + i * (PANEL_W + GUTTER)
        y = PADDING + 30
        pose = rng.choice(POSES)
        cx = x + PANEL_W / 2 + rng.uniform(-30, 30)
        base_y = y + PANEL_H - 40
        bubble_w = PANEL_W - 30
        bubble_x = x + 15
        bubble_lines = _wrap_text(line)
        bubble_y = y + 14
        # tail aims at the head
        head_cx = cx
        head_cy = base_y - 90 - 14
        panel_svgs.append(
            f'<g class="panel">\n'
            f'    <rect x="{x}" y="{y}" width="{PANEL_W}" height="{PANEL_H}" '
            f'fill="white" stroke="black" stroke-width="2"/>\n'
            f'    {_speech_bubble(bubble_x, bubble_y, bubble_w, bubble_lines, (head_cx, head_cy))}\n'
            f'    {_stickman(cx, base_y, pose)}\n'
            f'    <line x1="{x + 20}" y1="{base_y + 6}" x2="{x + PANEL_W - 20}" y2="{base_y + 6}" '
            f'stroke="black" stroke-width="1.5"/>\n'
            f'</g>'
        )

    # Alt text: longest sentence ≤ 140 chars, falling back to first.
    sentences = re.split(r"(?<=[.!?…])\s+", re.sub(r"\s+", " ", review_text).strip())
    qualifying = [s for s in sentences if 0 < len(s) <= 140]
    alt = max(qualifying, key=len) if qualifying else (sentences[0] if sentences else title)
    alt = alt.strip()
    if len(alt) > 200:
        alt = alt[:197].rsplit(" ", 1)[0] + "…"

    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="{html.escape(title)}">\n'
        f'  <rect width="100%" height="100%" fill="white"/>\n'
        f'  {header}\n'
        f'  {chr(10).join("  " + p for p in panel_svgs)}\n'
        f'</svg>\n'
    )
    return svg, alt
