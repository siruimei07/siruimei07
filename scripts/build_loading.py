"""Render a one-shot Rhine Lab inspired profile intro as theme-aware APNGs.

Only Pillow and the bundled OFL fonts are required. The animated images work
inside GitHub's sanitized README without JavaScript or external image services.
Infinity geometry and orbit motion adapted from LBEILC/RhineLabUI (MIT); see
banners/loading/README.md for the pinned reference and attribution.
"""

import argparse
from functools import lru_cache
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "banners" / "loading" / "fonts"
SCALE = 2
THEMES = {
    "light": {"background": (231, 230, 225), "ink": (15, 18, 17),
              "muted": (112, 115, 109), "ghost": (239, 238, 233),
              "white": (255, 255, 252), "accent": (237, 130, 27)},
    "dark": {"background": (13, 17, 23), "ink": (229, 232, 225),
             "muted": (133, 144, 151), "ghost": (24, 30, 36),
             "white": (89, 103, 110), "accent": (246, 151, 53)},
}
# One continuous contour, in the reference's 310 x 185 logo coordinate space.
LOGO_START = (295, 73)
LOGO_CURVES = (
    ((295, 41), (273, 15), (240, 15)),
    ((221, 15), (207, 23), (192, 38)),
    ((186, 43), (181, 47), (176, 52)),
    ((127, 96), (103, 128), (70, 128)),
    ((38, 128), (15, 101), (15, 70)),
    ((15, 39), (37, 15), (70, 15)),
    ((103, 15), (127, 48), (156, 75)),
    ((182, 99), (208, 128), (240, 128)),
    ((273, 128), (295, 105), (295, 73)),
)


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def progress(time: float, start: float, end: float) -> float:
    return clamp((time - start) / (end - start))


def smooth(value: float) -> float:
    value = clamp(value)
    return value * value * (3 - 2 * value)


def mix(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def read_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("loading config must be an object")
    limits = {"width": (640, 1920), "height": (160, 600),
              "fps": (10, 30), "duration_ms": (11000, 20000)}
    for name, (minimum, maximum) in limits.items():
        value = config.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"{name} must be an integer between {minimum} and {maximum}")
    if config["width"] != config["height"] * 4:
        raise ValueError("loading canvas aspect ratio must be 4:1")
    for name in ("profile_name", "subtitle"):
        value = config.get(name)
        if (not isinstance(value, str) or not value.strip() or len(value) > 24
                or not all(32 <= ord(character) <= 126 for character in value)):
            raise ValueError(f"{name} must contain 1 to 24 printable ASCII characters")
    return config


def frame_times(duration_ms: int, fps: int) -> tuple[list[float], list[int]]:
    """Distribute rounding over the whole clip; never truncate its duration."""
    count = math.ceil(duration_ms * fps / 1000)
    boundaries = [round(index * duration_ms / count) for index in range(count + 1)]
    return ([boundary / 1000 for boundary in boundaries[:-1]],
            [right - left for left, right in zip(boundaries, boundaries[1:])])


@lru_cache(maxsize=32)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Barlow-SemiBold.ttf" if bold else "Barlow-Regular.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), size * SCALE)


@lru_cache(maxsize=1)
def logo_points() -> tuple[tuple[float, float], ...]:
    points = [LOGO_START]
    start = LOGO_START
    for first, second, end in LOGO_CURVES:
        for step in range(1, 33):
            t = step / 32
            u = 1 - t
            points.append(tuple(u ** 3 * start[axis] + 3 * u * u * t * first[axis]
                                + 3 * u * t * t * second[axis] + t ** 3 * end[axis]
                                for axis in (0, 1)))
        start = end
    return tuple(points)


class Canvas:
    """Draw in a fixed 1280 x 320 design space with supersampled edges."""

    def __init__(self, theme: str):
        self.colors = THEMES[theme]
        self.image = Image.new("RGB", (1280 * SCALE, 320 * SCALE), self.colors["background"])
        self.draw = ImageDraw.Draw(self.image)

    def color(self, role: str, opacity: float = 1) -> tuple[int, int, int]:
        return tuple(round(mix(bg, fg, clamp(opacity)))
                     for bg, fg in zip(self.colors["background"], self.colors[role]))

    def line(self, points, role="ink", width=1, opacity=1):
        if len(points) < 2 or opacity <= 0:
            return
        scaled = [(round(x * SCALE), round(y * SCALE)) for x, y in points]
        self.draw.line(scaled, fill=self.color(role, opacity),
                       width=max(1, round(width * SCALE)), joint="curve")
        # Rounded end caps are visible while the infinity contour is drawn.
        if width >= 3:
            for x, y in (points[0], points[-1]):
                self.dot(x, y, width / 2, role, opacity)

    def dot(self, x, y, radius, role="ink", opacity=1):
        if radius > 0 and opacity > 0:
            self.draw.ellipse(tuple(round(v * SCALE) for v in
                                    (x - radius, y - radius, x + radius, y + radius)),
                              fill=self.color(role, opacity))

    def arc(self, x, y, radius, heading, sweep, role="ink", width=1, opacity=1):
        steps = max(2, math.ceil(abs(sweep) * max(1, radius) / 160))
        points = []
        for step in range(steps + 1):
            angle = math.radians(heading + sweep * step / steps)
            points.append((x + radius * math.cos(angle), y + radius * math.sin(angle)))
        self.line(points, role, width, opacity)

    def text(self, value, x, y, size=18, bold=False, tracking=0,
             align="left", role="ink", opacity=1):
        face = font(size, bold)
        widths = [self.draw.textlength(character, font=face) / SCALE for character in value]
        total = sum(widths) + tracking * max(0, len(value) - 1)
        if align == "center":
            x -= total / 2
        elif align == "right":
            x -= total
        for character, width in zip(value, widths):
            self.draw.text((round(x * SCALE), round(y * SCALE)), character,
                           font=face, fill=self.color(role, opacity), anchor="lt")
            x += width + tracking

    def logo(self, x, y, width=146, reveal=1, opacity=1, symbols=1,
             role="ink", stroke=26):
        factor = width / 310
        points = logo_points()
        # Length-weighted sampling keeps drawing speed continuous across curves.
        distances = [math.dist(left, right) for left, right in zip(points, points[1:])]
        target = sum(distances) * clamp(reveal)
        visible = [points[0]]
        travelled = 0
        for point, distance in zip(points[1:], distances):
            travelled += distance
            if travelled > target:
                break
            visible.append(point)
        self.line([(x + px * factor, y + py * factor) for px, py in visible],
                  role=role, width=stroke * factor, opacity=opacity)
        if symbols > 0:
            left = x + mix(155, 69, symbols) * factor
            right = x + mix(155, 241, symbols) * factor
            cy = y + 70 * factor
            arm = 23 * factor * symbols
            stroke = 14 * factor
            self.line([(left - arm, cy), (left + arm, cy)], width=stroke, opacity=opacity)
            self.line([(left, cy - arm), (left, cy + arm)], width=stroke, opacity=opacity)
            self.line([(right - arm, cy), (right + arm, cy)], width=stroke, opacity=opacity)


def background(canvas: Canvas, config: dict, time: float):
    # Faint off-canvas infinity contours echo the opening's etched background.
    canvas.logo(-110, 27, width=385, role="ghost", stroke=2, symbols=0)
    canvas.logo(1110, 145, width=275, role="ghost", stroke=2, symbols=0)
    opacity = smooth(progress(time, 2.65, 3.25))
    canvas.text(config["profile_name"], 42, 27, size=20, bold=True, tracking=1.1, opacity=opacity)
    canvas.text("PROFILE SYSTEM", 42, 51, size=11, tracking=1.7, role="muted", opacity=opacity)
    canvas.line([(42, 283), (1238, 283)], role="muted", opacity=0.16)
    canvas.text("PUBLIC ACCESS  /  01", 42, 295, size=10, tracking=1.5, role="muted")
    canvas.text("RHINE LAB  /  INTERFACE STUDY", 1238, 295, size=10,
                tracking=1.2, align="right", role="muted")
    # Quiet phase markers remain useful as a frame for the final welcome state.
    phase = 0 if time < 1.5 else 1 if time < 5.8 else 2 if time < 9.4 else 3
    for index in range(4):
        x = 610 + index * 20
        canvas.line([(x, 267), (x + 11, 267)], role="accent" if index == phase else "muted",
                    width=2, opacity=0.8 if index == phase else 0.24)


def draw_access(canvas: Canvas, time: float):
    text = "ACCESS PERMISSION REQUIRED"
    count = round(len(text) * progress(time, 0.16, 1.03))
    canvas.text(text[:count], 640, 148, size=24, tracking=1.6, align="center")


def draw_identity(canvas: Canvas, time: float, config: dict):
    shift = smooth(progress(time, 2.65, 3.25))
    reveal = smooth(progress(time, 1.42, 2.30))
    x = mix(567, 350, shift)
    canvas.logo(x, 108, reveal=reveal, symbols=smooth(progress(time, 2.0, 2.55)))
    canvas.text("R H I N E  L A B", x + 73, 183, size=10, tracking=2.2,
                align="center", opacity=smooth(progress(time, 2.05, 2.6)))
    if time >= 3.05:
        messages = ((3.05, "ID: " + config["profile_name"]), (3.55, "CONNECTING ..."),
                    (4.10, "CONNECTION ESTABLISHED"), (4.75, "IDENTITY VERIFIED"),
                    (5.30, "ACCESS GRANTED"))
        start, message = next((start, message) for start, message in reversed(messages) if time >= start)
        count = round(len(message) * progress(time, start, start + 0.28))
        canvas.text("+ " + message[:count], 573, 144, size=22, tracking=1.2)
        canvas.text("ESTABLISHING SECURE CONNECTION", 575, 179, size=10,
                    tracking=1.6, role="muted", opacity=0.7)
        canvas.text("CONNECTED TO PUBLIC ARCHIVE  >", 1238, 249, size=10,
                    tracking=1.2, align="right", role="muted", opacity=shift)


def draw_scan(canvas: Canvas, time: float):
    p = smooth(progress(time, 5.8, 9.28))
    arrival = smooth(progress(time, 5.8, 6.55))
    outer = mix(355, 117, arrival)
    heading = mix(125, -90, p)
    sweep = mix(55, 360, progress(time, 5.8, 8.55))
    canvas.arc(640, 151, outer, heading, sweep, width=1.35)
    edge = math.radians(heading + sweep)
    canvas.dot(640 + outer * math.cos(edge), 151 + outer * math.sin(edge), mix(4, 2, p))
    canvas.arc(640, 151, mix(302, 108, arrival), heading + 165, sweep,
               role="white", width=2.3)
    inner = mix(59, 42, p)
    for offset in (0, 180):
        canvas.arc(640, 151, inner, mix(-20, 201.5, p) + offset,
                   136 * progress(time, 6.0, 7.15), width=0.8)
        angle = math.radians(mix(70, -270, p) + offset)
        orbit = mix(127, 80, p)
        canvas.dot(640 + orbit * math.cos(angle), 151 + orbit * math.sin(angle),
                   2.3 * progress(time, 5.8, 6.25), role="accent")
    label_opacity = 1 - smooth(progress(time, 8.05, 8.52))
    canvas.text("PERMISSION AUTHORIZED", 640, 147, size=14,
                tracking=mix(10, 1.2, smooth(progress(time, 5.8, 7.25))),
                align="center", opacity=label_opacity)
    if time > 8.38:
        opacity = smooth(progress(time, 8.38, 8.9))
        for x in (606, 674):
            canvas.arc(x, 151, 17, 0, 360, width=0.75, opacity=opacity)
        canvas.dot(640, 151, 2.5, opacity=opacity)
        for index in range(6):
            angle = math.radians(index * 60 + time * 80)
            canvas.dot(640 + 13 * math.cos(angle), 151 + 13 * math.sin(angle),
                       1.3, opacity=opacity)
    canvas.text("PERMISSION  /  AUTHORIZED", 640, 249, size=10, tracking=2.4,
                align="center", role="muted")


def draw_welcome(canvas: Canvas, time: float, config: dict):
    opacity = smooth(progress(time, 9.4, 9.88))
    canvas.text("WELCOME TO", 640, 96, size=23, bold=True, tracking=2.4,
                align="center", opacity=opacity)
    name = config["profile_name"]
    # Keep a longer customized name inside the same compact composition.
    size = min(42, round(470 / max(1, len(name)) * 1.6))
    canvas.text(name, 640, 126, size=size, bold=True, tracking=2.8,
                align="center", opacity=smooth(progress(time, 9.68, 10.10)))
    canvas.text(config["subtitle"], 640, 177, size=12, tracking=3.2,
                align="center", role="muted", opacity=smooth(progress(time, 9.90, 10.28)))
    canvas.logo(604, 207, width=72, opacity=smooth(progress(time, 10.02, 10.4)))


def render_frame(time: float, config: dict, theme: str) -> Image.Image:
    canvas = Canvas(theme)
    background(canvas, config, time)
    if time < 1.4:
        draw_access(canvas, time)
    elif time < 5.8:
        draw_identity(canvas, time, config)
    elif time < 9.4:
        draw_scan(canvas, time)
    else:
        draw_welcome(canvas, time, config)
    return canvas.image.resize((config["width"], config["height"]), Image.Resampling.LANCZOS)


def build(config: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    times, durations = frame_times(config["duration_ms"], config["fps"])
    outputs = []
    for theme in THEMES:
        frames = [render_frame(time, config, theme) for time in times]
        animation = output_dir / f"loading-{theme}.png"
        # APNG num_plays=1 stops at the welcome screen. SOURCE patches avoid
        # ghosting; Pillow combines identical holds without changing timing.
        frames[0].save(animation, format="PNG", save_all=True, append_images=frames[1:],
                       duration=durations, loop=1, disposal=0, blend=0, optimize=True)
        static = output_dir / f"loading-static-{theme}.png"
        frames[-1].save(static, optimize=True)
        outputs.extend((animation, static))
        print(f"Built {animation.name}: {config['width']} x {config['height']}, "
              f"{config['duration_ms']} ms, plays once, {animation.stat().st_size:,} bytes")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "banners" / "loading" / "config.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets")
    args = parser.parse_args()
    try:
        build(read_config(args.config), args.output_dir)
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
