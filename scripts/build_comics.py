"""Fetch a Letterboxd RSS feed and emit one Jekyll post + one SVG per review."""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Dict, List, Optional

from comic_renderer import render_comic

NS = {
    "letterboxd": "https://letterboxd.com",
    "dc": "http://purl.org/dc/elements/1.1/",
    "tmdb": "https://themoviedb.org",
}

ROOT = Path(__file__).resolve().parent.parent
COMICS_DIR = ROOT / "_comics"
SVG_DIR = ROOT / "assets" / "comics"
STATE_FILE = Path(__file__).resolve().parent / "state.json"


def fetch_rss(username: str) -> bytes:
    url = f"https://letterboxd.com/{username}/rss/"
    req = urllib.request.Request(url, headers={"User-Agent": "xkvd-builder/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def strip_html(s: str) -> str:
    s = re.sub(r"<img[^>]*>", "", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</p>\s*<p>", "\n\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return unescape(s).strip()


def rating_to_stars(rating: Optional[str]) -> str:
    if not rating:
        return ""
    try:
        r = float(rating)
    except ValueError:
        return rating
    full = int(r)
    half = (r - full) >= 0.5
    return "★" * full + ("½" if half else "")


def parse_items(xml_bytes: bytes) -> List[Dict]:
    root = ET.fromstring(xml_bytes)
    items: List[Dict] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        try:
            date = parsedate_to_datetime(pub).date().isoformat() if pub else ""
        except (TypeError, ValueError):
            date = ""
        film = (item.findtext("letterboxd:filmTitle", namespaces=NS) or "").strip()
        year = (item.findtext("letterboxd:filmYear", namespaces=NS) or "").strip()
        rating = (item.findtext("letterboxd:memberRating", namespaces=NS) or "").strip()
        watched = (item.findtext("letterboxd:watchedDate", namespaces=NS) or "").strip()
        description_html = (item.findtext("description") or "")
        review_text = strip_html(description_html)
        if not film:
            # diary entries sometimes use the title field instead
            m = re.match(r"^(.+?),\s*\d{4}", title)
            if m:
                film = m.group(1)
        items.append({
            "title": title,
            "link": link,
            "guid": guid,
            "pub_date": date,
            "watched_date": watched,
            "film": film,
            "year": year,
            "rating": rating,
            "review_text": review_text,
        })
    # RSS gives newest-first; reverse so older reviews get smaller IDs.
    items.reverse()
    return items


def has_review(item: Dict) -> bool:
    return bool(item["review_text"]) and len(item["review_text"]) >= 12


def load_state() -> Dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"by_guid": {}, "next_id": 1}


def save_state(state: Dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "comic"


def write_comic(item: Dict, comic_id: int) -> None:
    rating_stars = rating_to_stars(item["rating"])
    title = f"#{comic_id:03d} — {item['film']}" + (f" ({item['year']})" if item["year"] else "")
    svg, alt = render_comic(
        comic_id=comic_id,
        title=title,
        film=item["film"],
        year=item["year"],
        rating_stars=rating_stars,
        review_text=item["review_text"],
    )

    SVG_DIR.mkdir(parents=True, exist_ok=True)
    COMICS_DIR.mkdir(parents=True, exist_ok=True)

    svg_path = SVG_DIR / f"{comic_id:03d}.svg"
    svg_path.write_text(svg, encoding="utf-8")

    slug = f"{comic_id:03d}-{slugify(item['film'])}"
    md_path = COMICS_DIR / f"{slug}.md"
    date = item["watched_date"] or item["pub_date"] or datetime.utcnow().date().isoformat()

    front_matter = {
        "id": comic_id,
        "title": title,
        "film": item["film"],
        "year": item["year"],
        "rating": rating_stars,
        "alt": alt,
        "letterboxd_url": item["link"],
        "date": date,
        "guid": item["guid"],
        "svg": f"/assets/comics/{comic_id:03d}.svg",
        "permalink": f"/comics/{comic_id:03d}/",
    }

    def yaml_escape(v: str) -> str:
        v = str(v).replace('"', '\\"')
        return f'"{v}"'

    fm_lines = ["---"]
    for k, v in front_matter.items():
        if isinstance(v, int):
            fm_lines.append(f"{k}: {v}")
        else:
            fm_lines.append(f"{k}: {yaml_escape(v)}")
    fm_lines.append("---")
    md_path.write_text("\n".join(fm_lines) + "\n", encoding="utf-8")


def _force_utf8_stdout() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")  # type: ignore[assignment]


def main() -> int:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", help="Letterboxd username", default=None)
    parser.add_argument("--force", action="store_true", help="Regenerate every comic, ignoring state.")
    args = parser.parse_args()

    username = args.user
    if not username:
        cfg_path = ROOT / "_config.yml"
        if cfg_path.exists():
            m = re.search(r'^letterboxd_username:\s*"?([^"\n]+)"?\s*$', cfg_path.read_text(encoding="utf-8"), re.M)
            if m:
                username = m.group(1).strip().strip('"')
    if not username:
        print("error: no Letterboxd username provided (use --user or set letterboxd_username in _config.yml)", file=sys.stderr)
        return 2

    print(f"Fetching https://letterboxd.com/{username}/rss/ …")
    xml_bytes = fetch_rss(username)
    items = parse_items(xml_bytes)
    print(f"  {len(items)} entries in feed")

    state = load_state()
    by_guid = state["by_guid"]
    next_id = state["next_id"]
    if args.force:
        by_guid = {}
        next_id = 1

    new_count = 0
    regen_count = 0
    for item in items:
        if not has_review(item):
            continue
        if item["guid"] in by_guid:
            if args.force:
                comic_id = by_guid[item["guid"]]
                write_comic(item, comic_id)
                regen_count += 1
            continue
        comic_id = next_id
        next_id += 1
        by_guid[item["guid"]] = comic_id
        write_comic(item, comic_id)
        new_count += 1
        print(f"  + #{comic_id:03d} {item['film']}")

    state["by_guid"] = by_guid
    state["next_id"] = next_id
    save_state(state)

    if regen_count:
        print(f"Regenerated {regen_count} comic(s).")
    print(f"Done. {new_count} new comic(s); {len(by_guid)} total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
