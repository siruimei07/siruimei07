"""Shared drawing kit for the profile's Rhine Lab images.

The palette, type and the ∞± mark follow the owner's website
(siruimei07/siruimei07.github.io, src/styles/tokens.css and src/markup.ts), so
the README reads as the same archive. Only Pillow and the bundled OFL fonts are
required; see banners/fonts/README.md for sources and checksums.
"""

from functools import lru_cache
import math
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "banners" / "fonts"

# Website tokens (tokens.css). "paper" is the website background; "page" is the
# GitHub page colour that transparent images sit on.
THEMES = {
    "light": {
        "paper": (232, 229, 225), "paper_hi": (241, 239, 236), "paper_lo": (220, 216, 210),
        "ink": (11, 12, 11), "ink2": (47, 48, 45), "sub": (95, 93, 86), "line": (170, 165, 154),
        "tile": (14, 15, 14), "tile_ink": (243, 242, 239),
        "tag": (11, 12, 11), "tag_ink": (246, 245, 242),
        "card": (250, 249, 247), "ghost": (255, 255, 255),
        "orange": (238, 125, 31), "lime": (196, 232, 76), "lime_ink": (143, 189, 28),
        "page": (255, 255, 255), "bracket": (170, 165, 154),
    },
    "dark": {
        "paper": (17, 24, 27), "paper_hi": (24, 33, 37), "paper_lo": (11, 16, 18),
        "ink": (224, 227, 220), "ink2": (196, 201, 194), "sub": (166, 176, 177), "line": (83, 97, 102),
        "tile": (5, 7, 8), "tile_ink": (233, 235, 230),
        "tag": (224, 227, 220), "tag_ink": (13, 18, 20),
        "card": (27, 36, 40), "ghost": (224, 227, 220),
        "orange": (232, 138, 58), "lime": (182, 220, 69), "lime_ink": (182, 220, 69),
        "page": (13, 17, 23), "bracket": (119, 123, 121),
    },
}

FONTS = {
    "sans": "Montserrat[wght].ttf",
    "mono": "JetBrainsMono[wght].ttf",
    "zh-500": "noto-sans-sc-500.woff2",
    "zh-700": "noto-sans-sc-700.woff2",
}

# ∞ with + and −, in the website's 310 × 145 mark space (src/markup.ts, adapted
# from LBEILC/RhineLabUI src/brand.ts, MIT).
MARK_LOOPS = ("M156 75C127 48 103 15 70 15C37 15 15 39 15 70S38 128 70 128C103 128 127 96 176 52"
              "M155 75C182 99 208 128 240 128C273 128 295 105 295 73S273 15 240 15C221 15 207 23 192 38")
MARK_SIGNS = "M44 70h50M69 45v50M219 70h44"
MARK_CONTOUR = ("M295 73C295 41 273 15 240 15C221 15 207 23 192 38C186 43 181 47 176 52C127 96 103 128 70 128"
                "C38 128 15 101 15 70C15 39 37 15 70 15C103 15 127 48 156 75C182 99 208 128 240 128"
                "C273 128 295 105 295 73Z")
MARK_SIZE = (310, 145)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def progress(time: float, start: float, end: float) -> float:
    return clamp((time - start) / (end - start))


def smooth(value: float) -> float:
    value = clamp(value)
    return value * value * (3 - 2 * value)


def mix(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def track(keys, frame: float) -> float:
    """Monotone cubic Hermite through (frame, value) keys, flat beyond the ends.

    Same interpolation as the website's src/boot/tracks.ts, so measured speeds
    never stall at a keyframe.
    """
    if frame <= keys[0][0]:
        return keys[0][1]
    last = len(keys) - 1
    if frame >= keys[last][0]:
        return keys[last][1]

    def slope(i):
        return (keys[i + 1][1] - keys[i][1]) / (keys[i + 1][0] - keys[i][0])

    def tangent(i):
        if i == 0:
            return slope(0)
        if i == last:
            return slope(last - 1)
        a, b = slope(i - 1), slope(i)
        if a * b <= 0:
            return 0.0
        h0 = keys[i][0] - keys[i - 1][0]
        h1 = keys[i + 1][0] - keys[i][0]
        w0, w1 = 2 * h1 + h0, h1 + 2 * h0
        return (w0 + w1) / (w0 / a + w1 / b)

    i = 0
    while frame > keys[i + 1][0]:
        i += 1
    h = keys[i + 1][0] - keys[i][0]
    p = (frame - keys[i][0]) / h
    return ((2 * p ** 3 - 3 * p ** 2 + 1) * keys[i][1] + (p ** 3 - 2 * p ** 2 + p) * h * tangent(i)
            + (-2 * p ** 3 + 3 * p ** 2) * keys[i + 1][1] + (p ** 3 - p ** 2) * h * tangent(i + 1))


def path_points(data: str, steps: int = 24) -> list[list[tuple[float, float]]]:
    """Flatten the SVG path subset used by the mark (M, C, S, h, v, Z) into polylines."""
    tokens = re.findall(r"[MCShvZ]|-?\d*\.?\d+", data)
    paths, current, position, control, command = [], [], (0.0, 0.0), None, None
    index = 0

    def number():
        nonlocal index
        index += 1
        return float(tokens[index - 1])

    def cubic(start, first, second, end):
        for step in range(1, steps + 1):
            t = step / steps
            u = 1 - t
            current.append(tuple(u ** 3 * start[k] + 3 * u * u * t * first[k]
                                 + 3 * u * t * t * second[k] + t ** 3 * end[k] for k in (0, 1)))

    while index < len(tokens):
        if tokens[index] in "MCShvZ":
            command = tokens[index]
            index += 1
        if command == "M":
            if current:
                paths.append(current)
            position = (number(), number())
            current, control = [position], None
            command = "L"  # an implicit repeat would be a line; the mark has none
        elif command == "C":
            first, second, end = (number(), number()), (number(), number()), (number(), number())
            cubic(position, first, second, end)
            position, control = end, second
        elif command == "S":
            first = (2 * position[0] - control[0], 2 * position[1] - control[1]) if control else position
            second, end = (number(), number()), (number(), number())
            cubic(position, first, second, end)
            position, control = end, second
        elif command == "h":
            position = (position[0] + number(), position[1])
            current.append(position)
            control = None
        elif command == "v":
            position = (position[0], position[1] + number())
            current.append(position)
            control = None
        elif command == "Z":
            current.append(current[0])
            control = None
        else:
            raise ValueError(f"unsupported path data near {tokens[index:index + 3]}")
    if current:
        paths.append(current)
    return paths


@lru_cache(maxsize=1)
def contour_points() -> tuple[tuple[float, float], ...]:
    return tuple(path_points(MARK_CONTOUR, steps=48)[0])


@lru_cache(maxsize=256)
def font(family: str, weight: int, size: float) -> ImageFont.FreeTypeFont:
    """Montserrat and JetBrains Mono are variable fonts; Noto Sans SC is a static subset."""
    if family == "zh":
        face = ImageFont.truetype(str(FONT_DIR / FONTS["zh-700" if weight >= 600 else "zh-500"]), size)
        return face
    face = ImageFont.truetype(str(FONT_DIR / FONTS[family]), size)
    face.set_variation_by_axes([weight])
    return face


@lru_cache(maxsize=4096)
def _prefix(family: str, weight: int, size: float, text: str) -> float:
    return font(family, weight, size).getlength(text)


def is_cjk(character: str) -> bool:
    return ord(character) > 0x2E7F


@lru_cache(maxsize=8)
def _missing_glyph(weight: int) -> bytes:
    return bytes(font("zh", weight, 40).getmask("\U000F0000"))


def require_glyphs(text: str, weight: int = 500) -> None:
    """The Chinese font is a subset: fail loudly instead of drawing empty boxes."""
    missing = sorted({character for character in text if is_cjk(character)
                      and bytes(font("zh", weight, 40).getmask(character)) == _missing_glyph(weight)})
    if missing:
        raise ValueError("characters missing from the bundled Noto Sans SC subset: " + "".join(missing))


def runs(text: str):
    """Split into Latin and CJK runs so each uses its own family."""
    if not text:
        return
    start = 0
    for index in range(1, len(text) + 1):
        if index == len(text) or is_cjk(text[index]) != is_cjk(text[start]):
            yield text[start:index], is_cjk(text[start])
            start = index


class Canvas:
    """Supersampled drawing in design pixels. Every primitive is composited
    through its own alpha layer, so opacity and transparent output stay exact."""

    def __init__(self, width: int, height: int, theme: str, scale: int = 2,
                 background: str | None = "paper"):
        self.width, self.height, self.scale = width, height, scale
        self.theme = THEMES[theme]
        fill = (*self.theme[background], 255) if background else (0, 0, 0, 0)
        self.image = Image.new("RGBA", (round(width * scale), round(height * scale)), fill)
        self.opaque = background is not None
        self.clip_x = None

    def rgb(self, role) -> tuple[int, int, int]:
        return self.theme[role] if isinstance(role, str) else tuple(role)

    def _layer(self, box, draw, role, opacity):
        if opacity <= 0:
            return
        s = self.scale
        x0, y0 = max(0, math.floor(box[0] * s) - 2), max(0, math.floor(box[1] * s) - 2)
        x1 = min(self.image.width, math.ceil(box[2] * s) + 2)
        y1 = min(self.image.height, math.ceil(box[3] * s) + 2)
        if x1 <= x0 or y1 <= y0:
            return
        color = self.rgb(role)
        layer = Image.new("RGBA", (x1 - x0, y1 - y0), (*color, 0))
        draw(ImageDraw.Draw(layer), (*color, round(255 * clamp(opacity))), x0, y0)
        if self.clip_x is not None:
            # A horizontal clip-path, as the website's highlight bar and POWERED BY reveal use.
            left = max(x0, round(self.clip_x[0] * s))
            right = min(x1, round(self.clip_x[1] * s))
            if right <= left:
                return
            layer = layer.crop((left - x0, 0, right - x0, y1 - y0))
            x0 = left
        self.image.alpha_composite(layer, (x0, y0))

    def paste(self, image: Image.Image) -> None:
        """Lay a prepared full-size RGBA layer (e.g. a cached background) over the canvas."""
        self.image.alpha_composite(image)

    def rect(self, x0, y0, x1, y1, role="ink", opacity=1.0):
        s = self.scale
        left, top, right, bottom = round(x0 * s), round(y0 * s), round(x1 * s), round(y1 * s)
        if right <= left or bottom <= top:
            return
        self._layer((x0, y0, x1, y1), lambda d, c, ox, oy: d.rectangle(
            (left - ox, top - oy, right - ox - 1, bottom - oy - 1), fill=c), role, opacity)

    def frame(self, x0, y0, x1, y1, width=1.0, role="ink", opacity=1.0):
        for box in ((x0, y0, x1, y0 + width), (x0, y1 - width, x1, y1),
                    (x0, y0 + width, x0 + width, y1 - width), (x1 - width, y0 + width, x1, y1 - width)):
            self.rect(*box, role=role, opacity=opacity)

    def line(self, points, width=1.0, role="ink", opacity=1.0, caps=False):
        points = list(points)
        if len(points) < 2:
            return
        s = self.scale
        pad = width / 2 + 1
        box = (min(p[0] for p in points) - pad, min(p[1] for p in points) - pad,
               max(p[0] for p in points) + pad, max(p[1] for p in points) + pad)

        def draw(d, c, ox, oy):
            scaled = [(x * s - ox, y * s - oy) for x, y in points]
            w = max(1, round(width * s))
            if w < 4:
                d.line(scaled, fill=c, width=w)
                return
            # Pillow's curve joints spike on dense polylines: stroke each segment
            # and round every joint instead.
            r = width * s / 2
            for a, b in zip(scaled, scaled[1:]):
                d.line((a, b), fill=c, width=w)
            for x, y in scaled[1:-1] + (scaled[::len(scaled) - 1] if caps else []):
                d.ellipse((x - r, y - r, x + r, y + r), fill=c)

        self._layer(box, draw, role, opacity)

    def polygon(self, points, role="ink", opacity=1.0):
        points = list(points)
        s = self.scale
        box = (min(p[0] for p in points), min(p[1] for p in points),
               max(p[0] for p in points), max(p[1] for p in points))
        self._layer(box, lambda d, c, ox, oy: d.polygon([(x * s - ox, y * s - oy) for x, y in points], fill=c),
                    role, opacity)

    def dot(self, x, y, radius, role="ink", opacity=1.0):
        if radius <= 0:
            return
        s = self.scale
        self._layer((x - radius, y - radius, x + radius, y + radius),
                    lambda d, c, ox, oy: d.ellipse((
                        (x - radius) * s - ox, (y - radius) * s - oy,
                        (x + radius) * s - ox, (y + radius) * s - oy), fill=c), role, opacity)

    def ring(self, x, y, radius, width=1.0, role="ink", opacity=1.0):
        if radius <= 0:
            return
        s = self.scale
        self._layer((x - radius - width, y - radius - width, x + radius + width, y + radius + width),
                    lambda d, c, ox, oy: d.ellipse((
                        (x - radius) * s - ox, (y - radius) * s - oy,
                        (x + radius) * s - ox, (y + radius) * s - oy),
                        outline=c, width=max(1, round(width * s))), role, opacity)

    def arc(self, x, y, radius, start, sweep, width=1.0, role="ink", opacity=1.0, caps=False):
        """Arc from `start` degrees (clockwise on screen) through `sweep` degrees."""
        if radius <= 0 or abs(sweep) < 0.01:
            return
        steps = max(4, math.ceil(abs(sweep) * max(1, radius) / 90))
        self.line([(x + radius * math.cos(math.radians(start + sweep * i / steps)),
                    y + radius * math.sin(math.radians(start + sweep * i / steps))) for i in range(steps + 1)],
                  width, role, opacity, caps)

    # ── type ──────────────────────────────────────────────────────────────

    def measure(self, text, size, weight=500, tracking=0.0, family="sans") -> float:
        total = 0.0
        count = 0
        for run, cjk in runs(text):
            fam = "zh" if cjk else family
            total += _prefix(fam, weight, size * self.scale, run) / self.scale
            count += len(run)
        return total + tracking * max(0, count - 1)

    def text(self, value, x, y, size, weight=500, tracking=0.0, align="left", role="ink",
             opacity=1.0, family="sans", anchor="ls", stroke=0.0):
        """Draw `value` with letter-spacing. `y` is the baseline unless anchor says otherwise.

        `stroke` thickens every glyph outline (design px), e.g. for a halo drawn underneath.
        """
        if not value or opacity <= 0:
            return 0.0
        width = self.measure(value, size, weight, tracking, family)
        if align == "center":
            x -= width / 2
        elif align == "right":
            x -= width
        s = self.scale
        glyphs = []
        cursor = x
        for run, cjk in runs(value):
            fam = "zh" if cjk else family
            if cjk:
                require_glyphs(run, weight)
            face = font(fam, weight, size * s)
            for index, character in enumerate(run):
                offset = _prefix(fam, weight, size * s, run[:index]) / s + tracking * index
                glyphs.append((face, character, cursor + offset))
            cursor += _prefix(fam, weight, size * s, run) / s + tracking * len(run)
        ascent = size * 1.1
        box = (x - 2 - stroke, y - ascent - 2 - stroke, x + width + 4 + stroke, y + size * 0.45 + 2 + stroke)
        if anchor == "lt":
            box = (x - 2 - stroke, y - 2 - stroke, x + width + 4 + stroke, y + size * 1.5 + 2 + stroke)
        outline = round(stroke * s)

        def draw(d, c, ox, oy):
            for face, character, gx in glyphs:
                d.text((gx * s - ox, y * s - oy), character, font=face, fill=c, anchor=anchor,
                       stroke_width=outline, stroke_fill=c)

        self._layer(box, draw, role, opacity)
        return width

    # ── motifs ────────────────────────────────────────────────────────────

    def mark(self, x, y, width, role="ink", opacity=1.0, reveal=1.0, signs=1.0, plus=None, minus=None):
        """The ∞± mark with its top-left at (x, y), `width` design px wide.

        `reveal` draws the single contour in (the opening's stroke-in);
        `signs` scales the + and − in from the crossing.
        """
        k = width / MARK_SIZE[0]
        if reveal >= 1:
            for loop in path_points(MARK_LOOPS):
                self.line([(x + px * k, y + py * k) for px, py in loop], 26 * k, role, opacity)
        elif reveal > 0:
            points = contour_points()
            lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
            target = sum(lengths) * reveal
            visible, travelled = [points[0]], 0.0
            for point, length in zip(points[1:], lengths):
                if travelled + length >= target:
                    t = (target - travelled) / length if length else 0
                    previous = visible[-1]
                    visible.append((mix(previous[0], point[0], t), mix(previous[1], point[1], t)))
                    break
                travelled += length
                visible.append(point)
            self.line([(x + px * k, y + py * k) for px, py in visible], 26 * k, role, opacity, caps=True)
        plus = signs if plus is None else plus
        minus = signs if minus is None else minus
        if plus > 0:
            arm = 25 * plus
            cx, cy = 69, 70
            self.line([(x + (cx - arm) * k, y + cy * k), (x + (cx + arm) * k, y + cy * k)], 15 * k, role, opacity)
            self.line([(x + cx * k, y + (cy - arm) * k), (x + cx * k, y + (cy + arm) * k)], 15 * k, role, opacity)
        if minus > 0:
            arm = 22 * minus
            cx, cy = 241, 70
            self.line([(x + (cx - arm) * k, y + cy * k), (x + (cx + arm) * k, y + cy * k)], 15 * k, role, opacity)

    def tag(self, value, x, y, size=12, weight=700, tracking=0.6, pad_x=7, height=None,
            role="tag", ink="tag_ink", opacity=1.0, outline=False, family="sans", tail=0.0):
        """Black label tag: (x, y) is its top-left; `tail` is extra empty plate on the right
        (the website's SECTION 0X. tags). Returns the tag width."""
        height = height or round(size * 1.65)
        width = self.measure(value, size, weight, tracking, family) + 2 * pad_x + tail
        if outline:
            self.frame(x, y, x + width, y + height, 1.5, role, opacity)
            ink = role
        else:
            self.rect(x, y, x + width, y + height, role, opacity)
        self.text(value, x + pad_x, y + height / 2 + size * 0.36, size, weight, tracking, role=ink,
                  opacity=opacity, family=family)
        return width

    def corner(self, x, y, length=14, width=3, role="ink", opacity=1.0):
        """The callouts' ⌜ bracket."""
        self.rect(x, y, x + length, y + width, role, opacity)
        self.rect(x, y + width, x + width, y + length, role, opacity)

    def dna(self, ax, ay, bx, by, amp, period, phase, role="ghost", opacity=0.5, width=6, rung=2.0):
        """One double helix along a→b (the website's boot__dna): two strands and their rungs."""
        length = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / length, (by - ay) / length
        nx, ny = -uy, ux

        def at(t, side, k=1.0):
            o = side * amp * k * math.sin(t / period * math.pi * 2 + phase)
            return ax + ux * t + nx * o, ay + uy * t + ny * o

        for side in (1, -1):
            self.line([at(t, side) for t in range(0, int(length) + 8, 8)], width, role, opacity)
        t = period / 20
        while t < length:
            self.line([at(t, 1, 0.8), at(t, -1, 0.8)], rung, role, opacity * 0.8)
            t += period / 10

    def result(self, density: int = 1) -> Image.Image:
        """Downsample to `density` output pixels per design pixel (2 for crisp README art)."""
        size = (round(self.width * density), round(self.height * density))
        image = self.image if size == self.image.size else self.image.resize(size, Image.Resampling.LANCZOS)
        return image.convert("RGB") if self.opaque else image
