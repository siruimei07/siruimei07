"""Render the profile's opening as theme-aware APNGs that play once.

The motion follows the opening of the owner's website (siruimei07.github.io,
src/boot/), using its measured tracks: ACCESS PERMISSION REQUIRED typed in
bursts, the ∞± mark drawn along one contour, the identity lines, the permission
rings closing in and the WELCOME TO / SIRUI MEI / PERSONAL DATABASE card. The
panel itself stays quiet: paper, two faint ∞ outlines, a small corner name and
the welcome card it settles on.

Measured tracks adapted from LBEILC/RhineLabUI (MIT) by the website; see
banners/loading/README.md. Time runs on the reference video's 25 fps frame
numbers; waiting stretches are shortened so the intro fits a README visit.
"""

import argparse
from functools import lru_cache
import json
import math
from pathlib import Path

from PIL import Image

import boot_tracks as tracks
from rhine import Canvas, clamp, contour_points, mix


ROOT = Path(__file__).resolve().parents[1]
SCALE = 2
WIDTH, HEIGHT = 1280, 320
CX, CY = WIDTH / 2, HEIGHT / 2
FONT = "barlow"

# The panel keeps its original quiet palette: light paper, and GitHub's own dark background.
THEMES = {
    "light": {"paper": (231, 230, 225), "ink": (15, 18, 17), "muted": (112, 115, 109),
              "ghost": (239, 238, 233), "pale": (255, 255, 252), "orange": (237, 130, 27)},
    "dark": {"paper": (13, 17, 23), "ink": (229, 232, 225), "muted": (133, 144, 151),
             "ghost": (24, 30, 36), "pale": (89, 103, 110), "orange": (246, 151, 53)},
}

# (first PV frame, last PV frame, speed). The website plays at 1.1×; pauses run at 4×.
SEGMENTS = (
    (166, 170, 1.0), (170, 190, 1.1), (190, 226, 4.0), (226, 229, 1.1), (229, 300, 1.1),
    (300, 321, 4.0), (321, 340, 1.1), (340, 367, 4.0), (367, 390, 1.1), (390, 423, 4.0),
    (423, 487, 1.6), (487, 569, 1.3), (569, 636, 1.2),
)
CARD_SETTLED = 635          # PERSONAL DATABASE stops flickering
BRAND_AT = 278              # the corner name starts sliding in
K_MARK = 0.58               # the opening's ∞ (296 px wide on the website's 1920 frame)
K_RING = 0.5                # permission rings
POWERED = "POWERED BY RHINE LAB"
MARK_NAME = "RHINE LAB LLC."


def read_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("loading config must be an object")
    limits = {"width": (640, 1920), "height": (160, 600),
              "fps": (10, 60), "duration_ms": (11000, 20000)}
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
    if config["duration_ms"] < math.ceil(motion_end() * 1000):
        raise ValueError(f"duration_ms must be at least {math.ceil(motion_end() * 1000)} to finish the motion")
    return config


def frame_times(duration_ms: int, fps: int) -> tuple[list[float], list[int]]:
    """Distribute rounding over the whole clip; never truncate its duration."""
    count = math.ceil(duration_ms * fps / 1000)
    boundaries = [round(index * duration_ms / count) for index in range(count + 1)]
    return ([boundary / 1000 for boundary in boundaries[:-1]],
            [right - left for left, right in zip(boundaries, boundaries[1:])])


# ── time ─────────────────────────────────────────────────────────────────

def _seconds(first: int, last: int, speed: float) -> float:
    return (last - first) / 25 / speed


def pv_frame(time: float) -> float:
    """Clip time (s) → reference frame number (25 fps), with the pauses shortened."""
    elapsed = 0.0
    for first, last, speed in SEGMENTS:
        span = _seconds(first, last, speed)
        if time < elapsed + span:
            return first + (time - elapsed) * 25 * speed
        elapsed += span
    first, last, speed = SEGMENTS[-1]
    return last + (time - elapsed) * 25 * speed


def time_of(frame: float) -> float:
    """Inverse of pv_frame within the segments."""
    elapsed = 0.0
    for first, last, speed in SEGMENTS:
        if frame <= last:
            return elapsed + (max(frame, first) - first) / 25 / speed
        elapsed += _seconds(first, last, speed)
    return elapsed


def motion_end() -> float:
    return time_of(CARD_SETTLED) + 0.25


def typed(length: int, f: int, start: float, end: float) -> int:
    if f < start:
        return 0
    return min(length, 1 + math.floor((f - start) * (length - 1) / (end - start)))


def typed_as(length: int, reference: int, f: int, start: float, end: float) -> int:
    """As typed(), stretched so our text keeps the reference's per-character speed."""
    return typed(length, f, start, start + (end - start) * max(1, length - 1) / (reference - 1))


def auth_line(f: int):
    """Which identity line shows, and which of its characters (the website's authLine)."""
    head, name = "ID CONFIRMED", "VISITOR"
    lines = (f"{head} : {name}", "REQUEST RECEIVED", "START PROCESSING...")
    if f < 363:
        to = typed_as(len(head), 12, f, 282, 295)
        if f >= 299:
            to = len(head) + 3
        if f >= 320:
            to += typed_as(len(name), 11, f, 321, 339)
        return lines[0], 0, to
    if f < 421:
        return lines[1], 0, typed_as(len(lines[1]), 16, f, 367, 389)
    processing, dots = "START PROCESSING", 3
    if f in (479, 485, 486):
        return lines[2], len(lines[2]) - 7, len(lines[2])
    to = typed_as(len(processing), 16, f, 423, 440)
    if f >= 449:
        to = len(processing) + min(dots, 1 + (f - 449) // 4)
    return lines[2], 0, to


# ── drawing helpers ──────────────────────────────────────────────────────

def text_in_place(c: Canvas, full: str, start: int, end: int, x: float, y: float, size: float,
                  weight: int, tracking: float, align="left", **style) -> float:
    """Typed text: characters [start, end) show; the rest keep their room so nothing shifts."""
    width = c.measure(full, size, weight, tracking, FONT)
    left = x - width / 2 if align == "center" else x - width if align == "right" else x
    if end > start:
        offset = c.measure(full[:start], size, weight, tracking, FONT) + (tracking if start else 0)
        c.text(full[start:end], left + offset, y, size, weight, tracking, family=FONT, **style)
    return width


@lru_cache(maxsize=1)
def contour_lengths() -> tuple[tuple[float, ...], float]:
    points = contour_points()
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + math.dist(a, b))
    return tuple(lengths), lengths[-1]


def contour_slice(start: float, end: float) -> list[tuple[float, float]]:
    """Points along the closed contour between normalised positions start < end (no wrap)."""
    points = contour_points()
    lengths, total = contour_lengths()

    def at(position):
        target = clamp(position) * total
        for index in range(1, len(lengths)):
            if lengths[index] >= target:
                span = lengths[index] - lengths[index - 1]
                t = (target - lengths[index - 1]) / span if span else 0
                a, b = points[index - 1], points[index]
                return index, (mix(a[0], b[0], t), mix(a[1], b[1], t))
        return len(points) - 1, points[-1]

    first_index, first = at(start)
    last_index, last = at(end)
    return [first, *points[first_index:last_index], last]


def draw_boot_mark(c: Canvas, left: float, top: float, width: float, state: dict, role="ink"):
    """The ∞ as one dash travelling along the contour, with the + and − popping in."""
    k = width / 310
    start, length = state["start"], state["length"]
    if length > 0.0005:
        a, b = start % 1.0, start % 1.0 + length
        pieces = [(a, min(b, 1.0))] + ([(0.0, b - 1.0)] if b > 1.0 else [])
        for p, q in pieces:
            if q - p > 0.0002:
                c.line([(left + x * k, top + y * k) for x, y in contour_slice(p, q)],
                       state["stroke"] * k, role)
    scale = state["signs"]
    if scale > 0:
        stroke = 15 * scale * k
        arm = 25 * scale
        angle = math.radians(state["plus_angle"])
        px, py = left + state["plus_x"] * k, top + 70 * k
        for dx, dy in ((1, 0), (0, 1)):
            ex = (dx * math.cos(angle) - dy * math.sin(angle)) * arm * k
            ey = (dx * math.sin(angle) + dy * math.cos(angle)) * arm * k
            c.line([(px - ex, py - ey), (px + ex, py + ey)], stroke, role)
        half = state["minus_width"] / 2 * scale
        mx = left + state["minus_x"] * k
        c.line([(mx - half * k, py), (mx + half * k, py)], stroke, role)


@lru_cache(maxsize=4)
def background(theme: str) -> Image.Image:
    """Flat paper with two faint ∞ outlines running off the edges."""
    c = Canvas(WIDTH, HEIGHT, "light", scale=SCALE, background=None)
    c.theme = THEMES[theme]
    c.rect(0, 0, WIDTH, HEIGHT, "paper")
    for x, y, width in ((-110, 27, 385), (1110, 145, 275)):
        k = width / 310
        c.line([(x + px * k, y + py * k) for px, py in contour_points()], 2, "ghost")
    return c.image


# ── stages ───────────────────────────────────────────────────────────────

def draw_chrome(c: Canvas, config: dict, frame: float, f: int):
    """The corner name slides in like the website's lockup; POWERED BY RHINE LAB uncovers."""
    rows = ((config["profile_name"], 27, 20, 600, 1.1, "ink"), ("ANALYSIS OS", 51, 11, 400, 1.7, "muted"))
    for line, (text, top, size, weight, tracking, role) in enumerate(rows):
        state = tracks.brand_track(frame - BRAND_AT, line)
        if state["o"] > 0:
            c.text(text, 42 + state["x"] * 0.35, top, size, weight, tracking, role=role,
                   opacity=state["o"], family=FONT, anchor="lt")
    shown = typed(len(POWERED), f, BRAND_AT + 1, BRAND_AT + 17)
    if shown:
        width = c.measure(POWERED, 10, 400, 1.4, FONT)
        c.clip_x = (WIDTH - 42 - width - 2, WIDTH - 42 - width + width * shown / len(POWERED) + 1)
        c.text(POWERED, WIDTH - 42, 295, 10, 400, 1.4, align="right", role="muted", family=FONT, anchor="lt")
        c.clip_x = None


def draw_access(c: Canvas, f: int):
    if not 170 <= f < 227:
        return
    count = tracks.ACCESS_COUNTS[min(len(tracks.ACCESS_COUNTS) - 1, f - 170)]
    full = "ACCESS PERMISSION REQUIRED"
    text_in_place(c, full, 0, round(count * len(full) / 26), CX, CY + 7, 22, 400, 1.6, align="center",
                  opacity=0.25 if f == 226 else 1.0)


def draw_identity(c: Canvas, frame: float, f: int):
    if not 229 <= f < 487:
        return
    state = tracks.logo_track(frame)
    width = 296 * K_MARK
    center = CX + (state["left"] - 814) * K_MARK
    top = CY - 77 * K_MARK
    draw_boot_mark(c, center - width / 2, top, width, state)
    shown = typed_as(len(MARK_NAME), 9, f, 232, 255)
    text_in_place(c, MARK_NAME, 0, shown, center + 1.2, top + width * 145 / 310 + 24, 10, 600, 2.4,
                  align="center")
    if 281 <= f < 487:
        full, start, end = auth_line(f)
        x = CX - 27 * K_MARK
        c.rect(x, CY - 1, x + 7, CY + 1, "ink")
        text_in_place(c, full, start, end, x + 16, CY + 7, 20, 400, 1.0)


def draw_scan(c: Canvas, frame: float, f: int, theme: str):
    if not 487 <= f < 569:
        return
    s = tracks.scan_track(frame)
    o = tracks.orbit_track(frame)
    glitch = f in (525, 526, 528, 529)
    k = K_RING * (1.94 if glitch else 1.0)
    alpha = 0.32 if glitch else tracks.ring_fade(frame)
    boost = 1.5  # the website's 2 px hairlines would vanish at the README's scale

    def stroke(rest, at, radius):
        return rest * max(0.2, radius / at) ** 0.85 * K_RING * boost

    def arc(radius, start, sweep, width, role="ink", x=960.0, y=540.0):
        c.arc(CX + (x - 960) * k, CY + (y - 540) * k, radius * k, math.degrees(start), math.degrees(sweep),
              width, role, alpha, caps=True)

    def point(angle, radius):
        return CX + math.cos(angle) * radius * k, CY + math.sin(angle) * radius * k

    arc(s["radius"], s["outer_start"], s["outer_sweep"], stroke(2.75, 248, s["radius"]))
    arc(s["white_radius"], s["white_start"], s["white_sweep"], stroke(5, 224, s["white_radius"]), "pale")
    for i in range(2):
        arc(s["inner_radius"], s["inner_start"] + i * math.pi, s["inner_sweep"], 2 * K_RING * boost)
    if o["side_visible"]:
        for side in o["sides"]:
            arc(side["radius"], side["start"], side["sweep"], 2 * K_RING * boost, x=side["x"], y=side["y"])
    for i in range(2):
        c.dot(*point(s["orbit"] + i * math.pi, s["orbit_radius"]), s["dot_radius"] * k * 1.2, "orange", alpha)
    for sat in o["satellites"]:
        c.dot(CX + (sat["x"] - 960) * k, CY + (sat["y"] - 540) * k, sat["radius"] * k * 1.2, "ink", alpha)
    if frame / 25 >= 21.84:
        c.dot(CX - 0.5 * k, CY - 0.5 * k, o["core_radius"] * k, "ink", alpha)
    c.dot(*point(s["outer_start"] + s["outer_sweep"], s["radius"]), s["black_cap"] * k, "ink", alpha)
    c.dot(*point(s["white_start"], s["white_radius"]), s["white_cap"] * k, "pale", alpha)

    t = frame / 25
    label = clamp((t - 19.48) / 0.4) if t < 21.8 else tracks.permission_fade(frame)
    if label > 0:
        spacing = tracks.permission_tracking(frame) * K_RING
        c.text("PERMISSION AUTHORIZED", CX + spacing / 2, CY + 6, 16, 400, spacing + 1.0, align="center",
               opacity=label, family=FONT)


def draw_card(c: Canvas, config: dict, f: int, theme: str):
    """WELCOME TO / name / subtitle with the mark, cut in on the website's frames, no name bar."""
    if f < 569:
        return
    flash = f - 569
    # The cut in: the words blink through the paper colour before they settle in ink.
    ink = (0, 0, 0.2, 1, 0, 0, 0.25)[flash] if 0 <= flash < 7 else 1
    if ink > 0:
        c.text("WELCOME TO", CX + 1.2, 96, 23, 600, 2.4, align="center", opacity=ink, family=FONT, anchor="lt")
    if f >= 588 and f not in (590, 591):
        name = config["profile_name"]
        size = min(42, round(470 / max(1, len(name)) * 1.6))
        c.text(name, CX + 1.4, 126, size, 600, 2.8, align="center", opacity=0.65 if f in (594, 595) else 1,
               family=FONT, anchor="lt")
        c.mark(CX - 36, 207, 72)
    if f >= 626 and f not in (628, 629, 631, 634):
        c.text(config["subtitle"], CX + 1.6, 177, 12, 400, 3.2, align="center", role="muted",
               family=FONT, anchor="lt")


def render_frame(time: float, config: dict, theme: str) -> Image.Image:
    c = Canvas(WIDTH, HEIGHT, "light", scale=SCALE, background=None)
    c.theme = THEMES[theme]
    c.image = background(theme).copy()
    c.opaque = True
    frame = pv_frame(time)
    f = math.floor(frame + 0.00001)
    draw_chrome(c, config, frame, f)
    draw_access(c, f)
    draw_identity(c, frame, f)
    draw_scan(c, frame, f, theme)
    draw_card(c, config, f, theme)
    image = c.result()
    if image.size != (config["width"], config["height"]):
        image = image.resize((config["width"], config["height"]), Image.Resampling.LANCZOS)
    return image


def palette(config: dict, theme: str, times: list[float]) -> Image.Image:
    """One 256-colour palette for the whole clip (an APNG shares a single PLTE).

    Indexed frames are about a third of the RGB size. The panel's own colours and
    their anti-aliasing ramps are reserved first, so the orange orbit dots
    survive; sampled frames fill the rest.
    """
    colors = THEMES[theme]
    ramps = ((colors["ink"], colors["paper"], 32), (colors["muted"], colors["paper"], 16),
             (colors["orange"], colors["paper"], 12), (colors["pale"], colors["paper"], 8),
             (colors["ghost"], colors["paper"], 4))
    reserved = []
    for fg, bg, steps in ramps:
        for step in range(steps + 1):
            color = tuple(round(mix(b, f, step / steps)) for f, b in zip(fg, bg))
            if color not in reserved:
                reserved.append(color)
    samples = [render_frame(time, config, theme) for time in times[:: max(1, len(times) // 24)] + [times[-1]]]
    strip = Image.new("RGB", (WIDTH, HEIGHT * len(samples)))
    for index, sample in enumerate(samples):
        strip.paste(sample.resize((WIDTH, HEIGHT)), (0, index * HEIGHT))
    rest = strip.quantize(256 - len(reserved), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    found = rest.getpalette()[: 3 * (256 - len(reserved))]
    entries = reserved + [tuple(found[i:i + 3]) for i in range(0, len(found), 3)]
    entries += [entries[-1]] * (256 - len(entries))
    image = Image.new("P", (1, 1))
    image.putpalette([value for color in entries[:256] for value in color])
    return image


def build(config: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    times, durations = frame_times(config["duration_ms"], config["fps"])
    outputs = []
    for theme in THEMES:
        indexed = palette(config, theme, times)
        frames = [render_frame(time, config, theme).quantize(palette=indexed, dither=Image.Dither.NONE)
                  for time in times]
        animation = output_dir / f"loading-{theme}.png"
        # APNG num_plays=1 stops on the welcome card. SOURCE patches avoid
        # ghosting; Pillow combines identical holds without changing timing.
        frames[0].save(animation, format="PNG", save_all=True, append_images=frames[1:],
                       duration=durations, loop=1, disposal=0, blend=0, optimize=True)
        static = output_dir / f"loading-static-{theme}.png"
        frames[-1].save(static, optimize=True)
        outputs.extend((animation, static))
        print(f"Built {animation.name}: {config['width']} x {config['height']}, "
              f"{config['duration_ms']} ms, plays once, {animation.stat().st_size:,} bytes")
        # Release this theme before allocating the next full sequence.
        del frames
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
