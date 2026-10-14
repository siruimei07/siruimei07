"""Render the README's section headers and link buttons as theme-aware PNGs.

They reuse the website's callout and button motifs (see scripts/rhine.py)
so every part of the profile reads as one Rhine Lab archive. Images are drawn
on a transparent background at 2x and blend into GitHub's light or dark page.
"""

import argparse
import json
import math
from pathlib import Path
import re

from rhine import THEMES, Canvas, require_glyphs


ROOT = Path(__file__).resolve().parents[1]
HEADER_SIZE = (1280, 172)
BUTTON_HEIGHT = 40
# Drawn at 4x and stored at 2x: crisp on high-density screens, smooth edges.
SUPERSAMPLE, DENSITY = 4, 2
ID_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,23}")


def ascii_text(value, name: str, limit: int) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or not all(32 <= ord(character) <= 126 for character in value)):
        raise ValueError(f"{name} must contain 1 to {limit} printable ASCII characters")
    return value


def read_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("section config must be an object")
    seen = set()
    for kind, required in (("headers", ("number", "title", "description", "code")),
                           ("buttons", ("label", "handle"))):
        items = config.get(kind)
        if not isinstance(items, list) or not items:
            raise ValueError(f"{kind} must be a non-empty list")
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) \
                    or not ID_PATTERN.fullmatch(item["id"]):
                raise ValueError(f"every entry in {kind} needs an id of lowercase letters, digits and hyphens")
            if (kind, item["id"]) in seen:
                raise ValueError(f"duplicate {kind} id: {item['id']}")
            seen.add((kind, item["id"]))
            for name in required:
                ascii_text(item.get(name), f"{kind}.{item['id']}.{name}", 40 if name == "title" else 32)
        if kind == "headers":
            for item in items:
                if not re.fullmatch(r"\d{2}", item["number"]):
                    raise ValueError(f"headers.{item['id']}.number must be two digits")
                zh = item.get("zh", "")
                if not isinstance(zh, str) or len(zh) > 16:
                    raise ValueError(f"headers.{item['id']}.zh must be a string of at most 16 characters")
                require_glyphs(zh)
        else:
            for item in items:
                if item.get("style") not in ("filled", "outline"):
                    raise ValueError(f"buttons.{item['id']}.style must be filled or outline")
    return config


def header(item: dict, theme: str) -> Canvas:
    """A home-screen callout laid flat (components.css .callout at 1.4×): bracket, SECTION tag
    with its long tail, title, leader rule ending in a dot, and the file-number box."""
    width, height = HEADER_SIZE
    k = 1.4
    c = Canvas(width, height, theme, scale=SUPERSAMPLE, background=None)
    left = 22 * k
    c.corner(0, 0, 36 * k * 0.8, 6 * k * 0.8, role="bracket")
    tag = 13 * k
    c.tag(f"SECTION {item['number']}.", left, 18, tag, 600, 0.06 * tag, pad_x=0.62 * tag,
          height=1.59 * tag, tail=2.0 * tag)
    title = 31 * k
    title_base = 18 + 1.59 * tag + 6 * k + (1.05 * title - 1.219 * title) / 2 + 0.968 * title
    c.text(item["title"], left - 1, title_base, title, 700, -0.005 * title)
    desc = 13 * k
    zh = 15 * k
    desc_base = title_base + 0.27 * title + 22
    c.text(item["description"], left, desc_base, desc, 400, 0.02 * desc, role="ink2")
    span = max(c.measure(item["title"], title, 700, -0.005 * title),
               c.measure(item["description"], desc, 400, 0.02 * desc))
    if item.get("zh"):
        offset = c.measure(item["description"], desc, 400, 0.02 * desc) + 0.9 * zh
        c.text(item["zh"], left + offset, desc_base + 1, zh, 500, 0.06 * zh, role="sub")
        span = max(span, offset + c.measure(item["zh"], zh, 500, 0.06 * zh))
    rule_y = title_base + 0.27 * title
    elbow = left + span + 26
    c.line([(left, rule_y), (elbow, rule_y), (elbow + 30, rule_y + 30)], 1.6 * k, "ink", 0.6)
    c.dot(elbow + 30, rule_y + 30, 5.5 * k, "ink")

    # right: the home screen's orange pager dots over a FILE NUMBER box with corner squares
    pitch, dot = 34 * 0.8, 4.5 * 0.8 * k
    for index in range(6):
        c.dot(width - dot - index * pitch, 22, dot, "orange")
    label = f"FILE NUMBER: {item['code']}"
    size = 17
    box_w = c.measure(label, size, 700, 0.04 * size) + 44
    x0, y0, x1, y1 = width - box_w, 52, width, 98
    for cx, cy in ((x0, y0), (x1 - 8, y0), (x0, y1 - 8), (x1 - 8, y1 - 8)):
        c.rect(cx, cy, cx + 8, cy + 8, "ink")
    c.text(label, (x0 + x1) / 2 + 0.02 * size, (y0 + y1) / 2 + 0.36 * size, size, 700, 0.04 * size,
           align="center")
    return c


def button_width(item: dict) -> int:
    probe = Canvas(10, 10, "light", scale=1, background=None)
    label = probe.measure(item["label"], 14, 700, 1.4)
    handle = probe.measure(item["handle"], 13, 500, 0.52)
    return math.ceil(13.3 + 7 + 9.8 + label + 9.8 + handle + 16.1)


def button(item: dict, theme: str) -> Canvas:
    """The website's .btn: ■ LABEL plus its handle at 70%; filled ink or a 2 px ink outline."""
    width, height = button_width(item), BUTTON_HEIGHT
    c = Canvas(width, height, theme, scale=SUPERSAMPLE, background=None)
    filled = item["style"] == "filled"
    if filled:
        c.rect(0, 0, width, height, "ink")
    c.frame(0, 0, width, height, 2, "ink")
    ink = "paper" if filled else "ink"
    baseline = height / 2 + 0.36 * 14
    c.rect(13.3, height / 2 - 3.5, 20.3, height / 2 + 3.5, ink)
    x = 13.3 + 7 + 9.8
    x += c.text(item["label"], x, baseline, 14, 700, 1.4, role=ink) + 9.8
    c.text(item["handle"], x, baseline, 13, 500, 0.52, role=ink, opacity=0.7)
    return c


def build(config: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(f"header-{item['id']}", header, item) for item in config["headers"]]
    jobs += [(f"button-{item['id']}", button, item) for item in config["buttons"]]
    outputs = []
    for name, draw, item in jobs:
        for theme in THEMES:
            path = output_dir / f"{name}-{theme}.png"
            draw(item, theme).result(DENSITY).save(path, optimize=True)
            outputs.append(path)
    print(f"Built {len(outputs)} section images in {output_dir}")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "banners" / "sections" / "config.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets" / "sections")
    args = parser.parse_args()
    try:
        build(read_config(args.config), args.output_dir)
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
