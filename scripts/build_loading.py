"""Render the profile's opening as theme-aware APNGs that play once.

The sequence is the opening of the owner's website (siruimei07.github.io,
src/boot/): ACCESS PERMISSION REQUIRED typed in bursts, the ∞± mark drawn along
one contour, the corner lockup sliding in, the identity lines, the permission
rings closing in, a flash cut and the WELCOME TO / SIRUI MEI / PERSONAL DATABASE
card. The README cannot run code, so the panel then settles on a still that also
names who this is: the website's identity block on the left, the card in the
middle and the personnel file on the right.

Motion uses the website's measured tracks (adapted from LBEILC/RhineLabUI, MIT;
see banners/loading/README.md). Time runs on the reference video's 25 fps frame
numbers; waiting stretches are shortened so the whole intro fits a README visit.
"""

import argparse
from functools import lru_cache
import json
import math
from pathlib import Path

from PIL import Image, ImageFilter

import boot_tracks as tracks
from rhine import THEMES, Canvas, clamp, contour_points, mix, progress, require_glyphs, smooth


ROOT = Path(__file__).resolve().parents[1]
SCALE = 2
WIDTH, HEIGHT = 1280, 320
CX, CY = WIDTH / 2, HEIGHT / 2

# (first PV frame, last PV frame, speed). The reference plays at 1.1×; pauses run at 4×.
SEGMENTS = (
    (166, 170, 1.0), (170, 190, 1.1), (190, 226, 4.0), (226, 229, 1.1), (229, 300, 1.1),
    (300, 321, 4.0), (321, 340, 1.1), (340, 367, 4.0), (367, 390, 1.1), (390, 423, 4.0),
    (423, 487, 1.6), (487, 569, 1.3), (569, 640, 1.2),
)
CARD_SETTLED = 612          # the name bar has finished its sweep
IDENTITY_SECONDS = 1.0      # the profile-only identity block and file column

# Scales from the reference's 1920 × 1080 frame to this 1280 × 320 canvas, per stage.
K_BOOT = 0.8                # access line, ∞ mark and identity lines
K_TEXT = 0.92               # their type, a little larger so it survives the README's downscale
K_LOGO_SHIFT = 0.85         # how far the mark slides left (the website's --logo-k)
K_RING = 0.5                # permission rings
K_CARD = 0.66               # welcome card
K_CHROME = 0.75             # corner lockup, orange dots, POWERED BY, section line, caption
K_ID = 0.95                 # identity block

BRAND_AT = 278
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
    for name, limit in (("profile_name", 24), ("subtitle", 24), ("tagline", 28), ("rank", 24),
                        ("affiliation", 28), ("code", 12)):
        value = config.get(name)
        if (not isinstance(value, str) or not value.strip() or len(value) > limit
                or not all(32 <= ord(character) <= 126 for character in value)):
            raise ValueError(f"{name} must contain 1 to {limit} printable ASCII characters")
    focus = config.get("focus")
    if (not isinstance(focus, list) or not 1 <= len(focus) <= 4
            or not all(isinstance(item, str) and item.strip() and len(item) <= 14
                       and all(32 <= ord(character) <= 126 for character in item) for item in focus)):
        raise ValueError("focus must list 1 to 4 ASCII fields of at most 14 characters")
    captions = config.get("captions")
    if (not isinstance(captions, list) or len(captions) != 4
            or not all(isinstance(item, str) and item.strip() and len(item) <= 30 for item in captions)):
        raise ValueError("captions must be four lines of at most 30 characters")
    for caption in captions:
        require_glyphs(caption)
    if config["duration_ms"] < round(motion_end() * 1000):
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
    return time_of(CARD_SETTLED) + IDENTITY_SECONDS + 0.4


def typed(length: int, f: int, start: float, end: float) -> int:
    if f < start:
        return 0
    return min(length, 1 + math.floor((f - start) * (length - 1) / (end - start)))


def typed_as(length: int, reference: int, f: int, start: float, end: float) -> int:
    """As typed(), stretched so our text keeps the reference's per-character speed."""
    return typed(length, f, start, start + (end - start) * max(1, length - 1) / (reference - 1))


def auth_line(f: int):
    """Which identity line shows, and which of its characters (motion.ts authLine)."""
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
    width = c.measure(full, size, weight, tracking)
    left = x - width / 2 if align == "center" else x - width if align == "right" else x
    if end > start:
        offset = c.measure(full[:start], size, weight, tracking) + (tracking if start else 0)
        c.text(full[start:end], left + offset, y, size, weight, tracking, **style)
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


def lockup_lines(c: Canvas, config: dict, x: float, top: float, k: float, offsets, opacity):
    """SIRUI MEI / SYNTHESIZE INFORMATION / ANALYSIS · OS (app.css .brand)."""
    width = 268 * k
    rows = (
        lambda dx, o: c.text(config["profile_name"], x + dx, top + 38.7 * k, 44 * k, 700, 0.035 * 44 * k,
                             opacity=o),
        lambda dx, o: c.text(config["tagline"], x + dx, top + 64.2 * k, 18.6 * k, 500, 0.012 * 18.6 * k,
                             opacity=o),
        lambda dx, o: (c.text("ANALYSIS", x + dx, top + 101.4 * k, 35 * k, 400, 0.05 * 35 * k, opacity=o),
                       c.text("OS", x + dx + width - 2 * k, top + 101.4 * k, 35 * k, 700, 0.06 * 35 * k,
                              align="right", opacity=o)),
    )
    for draw, dx, o in zip(rows, offsets, opacity):
        if o > 0:
            draw(dx, o)


# ── background ───────────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def background(theme: str) -> Image.Image:
    """Paper with the opening's soft radial light and two blurred double helices."""
    colors = THEMES[theme]
    w, h = WIDTH * SCALE, HEIGHT * SCALE
    small = Image.new("RGB", (WIDTH // 8, HEIGHT // 8))
    stops = ((0.0, colors["paper_hi"]), (0.55, colors["paper"]), (1.2, colors["paper_lo"]))
    for y in range(small.height):
        for x in range(small.width):
            # radial-gradient(120% 90% at 50% 40%, bg-hi 0%, bg 55%, bg-lo 120%)
            d = math.hypot(((x + 0.5) / small.width - 0.5) / 1.2, ((y + 0.5) / small.height - 0.4) / 0.9)
            (p0, c0), (p1, c1) = stops[:2] if d <= stops[1][0] else stops[1:]
            t = clamp((d - p0) / (p1 - p0))
            small.putpixel((x, y), tuple(round(mix(a, b, t)) for a, b in zip(c0, c1)))
    paper = small.resize((w, h), Image.Resampling.BICUBIC).convert("RGBA")

    helix = Canvas(WIDTH, HEIGHT, theme, scale=SCALE, background=None)
    strand = (255, 255, 255) if theme == "light" else colors["ink"]
    alpha = 0.5 if theme == "light" else 0.1
    k = 0.6
    for (ax, ay), (bx, by), amp, period, phase in (((800, -160), (-160, 1260), 170, 620, 0.6),
                                                     ((1522, -120), (1522, 1200), 96, 540, 2.2)):
        helix.dna(CX + (ax - 960) * k, CY + (ay - 540) * k, CX + (bx - 960) * k, CY + (by - 540) * k,
                  amp * k, period * k, phase, role=strand, opacity=alpha, width=20 * k, rung=7 * k)
    # The reference blurs its helices by 5 px at 1920 wide; a little more here keeps
    # them atmospheric once the README scales the panel down.
    # Blur premultiplied, or the transparent black around the strands greys them.
    soft = helix.image.convert("RGBa").filter(ImageFilter.GaussianBlur(10 * k * SCALE)).convert("RGBA")
    paper.alpha_composite(soft)
    return paper


# ── stages ───────────────────────────────────────────────────────────────

def draw_chrome(c: Canvas, config: dict, frame: float, f: int):
    k = K_CHROME
    lockup = frame - BRAND_AT
    offsets, opacity = [], []
    for line in range(3):
        state = tracks.brand_track(lockup, line)
        offsets.append(state["x"] * k)
        opacity.append(state["o"])
    lockup_lines(c, config, 44, 34, k, offsets, opacity)

    shown = typed(len(POWERED), f, BRAND_AT + 1, BRAND_AT + 17)
    if shown:
        size = 19 * k
        right = WIDTH - 44
        dash = 24 * k
        bold = c.measure("RHINE LAB", size, 700, 0.04 * size)
        regular = c.measure("POWERED BY", size, 500, 0.01 * size)
        gap = 0.32 * size
        x0 = right - dash - 18 * k - bold - gap - regular
        baseline = 289
        reveal = x0 + (right - x0) * shown / len(POWERED)
        c.clip_x = (x0 - 2, reveal + 1)
        c.text("POWERED BY", x0, baseline, size, 500, 0.01 * size)
        c.text("RHINE LAB", x0 + regular + gap, baseline, size, 700, 0.04 * size)
        c.rect(right - dash, baseline - 6.6 - 3 * k, right, baseline - 6.6 + 3 * k, "ink")
        c.clip_x = None


def draw_access(c: Canvas, f: int):
    if not 170 <= f < 227:
        return
    count = tracks.ACCESS_COUNTS[min(len(tracks.ACCESS_COUNTS) - 1, f - 170)]
    full = "ACCESS PERMISSION REQUIRED"
    n = round(count * len(full) / 26)
    size = 18 * K_TEXT
    text_in_place(c, full, 0, n, CX, CY + 0.35 * size, size, 500, 0.045 * size, align="center",
                  opacity=0.25 if f == 226 else 1.0)


def draw_identity(c: Canvas, frame: float, f: int):
    if not 229 <= f < 487:
        return
    state = tracks.logo_track(frame)
    width = 296 * K_BOOT
    center = CX + (state["left"] - 814) * K_BOOT * K_LOGO_SHIFT
    top = CY - 77 * K_BOOT
    draw_boot_mark(c, center - width / 2, top, width, state)
    name_size = 15.5 * K_TEXT
    shown = typed_as(len(MARK_NAME), 9, f, 232, 255)
    mark_bottom = top + width * 145 / 310
    text_in_place(c, MARK_NAME, 0, shown, center + 0.34 * name_size, mark_bottom + 16 * K_BOOT + name_size * 0.72,
                  name_size, 700, 0.68 * name_size, align="center")

    if 281 <= f < 487:
        full, start, end = auth_line(f)
        size = 19.5 * K_TEXT
        x = CX - 27 * K_BOOT
        c.rect(x, CY - 0.065 * size, x + 0.36 * size, CY + 0.065 * size, "ink")
        text_in_place(c, full, start, end, x + 0.78 * size, CY + 0.35 * size, size, 500, 0.012 * size)


def ring_point(angle: float, radius: float, scale: float = 1.0):
    return (CX + math.cos(angle) * radius * K_RING * scale, CY + math.sin(angle) * radius * K_RING * scale)


def draw_scan(c: Canvas, frame: float, f: int, theme: str):
    if not 487 <= f < 569:
        return
    s = tracks.scan_track(frame)
    o = tracks.orbit_track(frame)
    glitch = f in (525, 526, 528, 529)
    scale = 1.94 if glitch else 1.0
    alpha = 0.32 if glitch else tracks.ring_fade(frame)
    k = K_RING * scale
    pale = ((255, 255, 255), 1.0) if theme == "light" else ("ink", 0.42)
    boost = 1.5  # the reference's 2 px hairlines would vanish at the README's scale

    def stroke(rest, at, radius):
        return rest * max(0.2, radius / at) ** 0.85 * K_RING * boost

    def arc(radius, start, sweep, width, role="ink", opacity=1.0, x=960.0, y=540.0):
        c.arc(CX + (x - 960) * k, CY + (y - 540) * k, radius * k, math.degrees(start), math.degrees(sweep),
              width, role, opacity * alpha, caps=True)

    arc(s["radius"], s["outer_start"], s["outer_sweep"], stroke(2.75, 248, s["radius"]))
    arc(s["white_radius"], s["white_start"], s["white_sweep"], stroke(5, 224, s["white_radius"]),
        pale[0], pale[1])
    for i in range(2):
        arc(s["inner_radius"], s["inner_start"] + i * math.pi, s["inner_sweep"], 2 * K_RING * boost)
    if o["side_visible"]:
        for side in o["sides"]:
            arc(side["radius"], side["start"], side["sweep"], 2 * K_RING * boost, x=side["x"], y=side["y"])
    for i in range(2):
        angle = s["orbit"] + i * math.pi
        c.dot(CX + math.cos(angle) * s["orbit_radius"] * k, CY + math.sin(angle) * s["orbit_radius"] * k,
              s["dot_radius"] * k * 1.2, "orange", alpha)
    for sat in o["satellites"]:
        c.dot(CX + (sat["x"] - 960) * k, CY + (sat["y"] - 540) * k, sat["radius"] * k * 1.2, "ink", alpha)
    if frame / 25 >= 21.84:
        c.dot(CX + (959.5 - 960) * k, CY + (539.5 - 540) * k, o["core_radius"] * k, "ink", alpha)
    for angle, radius, size, role, opacity in (
            (s["outer_start"] + s["outer_sweep"], s["radius"], s["black_cap"], "ink", 1.0),
            (s["white_start"], s["white_radius"], s["white_cap"], pale[0], pale[1])):
        c.dot(CX + math.cos(angle) * radius * k, CY + math.sin(angle) * radius * k, size * k, role,
              opacity * alpha)

    t = frame / 25
    label = progress(t, 19.48, 19.88) if t < 21.8 else tracks.permission_fade(frame)
    if label > 0:
        size = 27.5 * K_RING * 1.3
        spacing = tracks.permission_tracking(frame) * K_RING
        c.text("PERMISSION AUTHORIZED", CX + spacing / 2, CY + 0.35 * size, size, 400, spacing,
               align="center", opacity=label)


def card_state(f: int, frame: float) -> dict:
    flash = f - 569
    return {
        "panel": (1, 0, 0.28, 0, 1, 0, 0)[flash] if 0 <= flash < 7 else 0,
        "ink": (0, 0, 0.2, 1, 0, 0, 0.25)[flash] if 0 <= flash < 7 else 1,
        "company": f >= 588 and f not in (590, 591),
        "mask": f in (594, 595),
        "bar": tracks.company_track(frame),
        "db": 0 if f < 626 or f in (628, 629, 631, 634) else 1,
        "logo": f >= 588,
    }


def draw_card(c: Canvas, config: dict, frame: float, f: int, theme: str):
    if f < 569:
        return
    k = K_CARD
    state = card_state(f, frame)
    y = lambda value: CY + (value - 540) * k  # noqa: E731 - frame y → canvas y
    if state["panel"] > 0:
        c.rect(CX - 235 * k, y(344), CX + 235 * k, y(736), "tag", state["panel"])
    knock = THEMES[theme]["tag_ink"]
    ink = THEMES[theme]["ink"]
    welcome_ink = tuple(round(mix(a, b, state["ink"])) for a, b in zip(knock, ink))

    def line(text, top, line_height, size, tracking, role, opacity=1.0):
        # Montserrat ascent .968 / descent .251: centre the content box in the line box.
        baseline = top + (line_height - 1.219 * size) / 2 + 0.968 * size
        c.text(text, CX + tracking / 2, baseline, size, 700, tracking, align="center", role=role, opacity=opacity)

    line("WELCOME TO", y(403), 65 * k, 52.5 * k, 0.035 * 52.5 * k, welcome_ink)
    if state["company"]:
        size = 48 * k
        top, height, width = y(470), 58 * k, 407 * k
        opacity = 0.65 if state["mask"] else 1.0
        line(config["profile_name"], top, height, size, 0.03 * size, "ink", opacity)
        if state["bar"] > 0:
            c.clip_x = (CX - width / 2, CX - width / 2 + width * state["bar"])
            c.rect(CX - width / 2, top, CX + width / 2, top + height, "tag", opacity)
            line(config["profile_name"], top, height, size, 0.03 * size, "tag_ink",
                 opacity * (0.06 if state["mask"] else 1.0))
            c.clip_x = None
    if state["db"]:
        line(config["subtitle"], y(534), 43 * k, 33.5 * k, 0.012 * 33.5 * k, "ink")
    if state["logo"]:
        mark_width = 203 * k
        c.mark(CX - mark_width / 2, y(589), mark_width)
        size = 11 * k * 1.25
        c.text(MARK_NAME, CX + 0.3 * size, y(694) + size * 0.72, size, 700, 0.6 * size, align="center")


def reveal(time: float, start: float, length: float = 0.3) -> float:
    return smooth(progress(time, start, start + length))


def draw_profile(c: Canvas, config: dict, time: float):
    """The README-only still: identity block, personnel file column and section line."""
    t0 = time_of(CARD_SETTLED)
    if time < t0:
        return
    k = K_ID
    x, top = 44, 34 + 136 * K_CHROME

    # ∞ badge: the tile wipes in from the left, then the mark appears
    badge = reveal(time, t0, 0.22)
    if badge > 0:
        bw, bh = 96 * k, 66 * k
        c.clip_x = (x, x + bw * badge)
        c.rect(x, top, x + bw, top + bh, "tag")
        c.clip_x = None
        mark = reveal(time, t0 + 0.16, 0.2)
        if mark > 0:
            mw = 61.4 * k
            c.mark(x + bw / 2 - mw / 2, top + 11.7 * k, mw, role="tag_ink", opacity=mark)
            size = 5.5 * k
            c.text(MARK_NAME, x + bw / 2 + 0.2 * size, top + 51.9 * k, size, 700, 0.4 * size,
                   align="center", role="tag_ink", opacity=mark)

    # role lines slide in like the corner lockup, two frames apart
    tx = x + 112 * k
    for index, (text, weight, baseline) in enumerate(((config["rank"], 800, 23.9), (config["affiliation"], 600, 45.5))):
        state = tracks.brand_track((time - t0 - 0.12) * 25 * 1.1, index)
        if state["o"] > 0:
            c.text(text, tx + state["x"] * 0.25, top + baseline * k, 16 * k, weight, 0.05 * 16 * k,
                   opacity=state["o"])
    rule = reveal(time, t0 + 0.3, 0.35)
    if rule > 0:
        end = tx + c.measure(config["affiliation"], 16 * k, 600, 0.05 * 16 * k) + 40 * k
        c.rect(tx, top + 54.1 * k, mix(tx, end, rule), top + 56.6 * k, "ink")
    focus = " · ".join(config["focus"])
    state = tracks.brand_track((time - t0 - 0.4) * 25 * 1.1, 0)
    if state["o"] > 0:
        size = 14 * k
        c.text(focus, x + state["x"] * 0.25, top + (327 - 250 + 17) * k, size, 700, 0.08 * size,
               opacity=state["o"])

    # right column: orange pager dots, then the personnel file number
    kc = K_CHROME
    for index in range(6):
        on = reveal(time, t0 + 0.05 + index * 0.06, 0.08)
        if on > 0:
            c.dot(WIDTH - 44 - 4.5 * kc - (5 - index) * 34 * kc, 34 + 11 * kc, 4.5 * kc * on, "orange")
    right = WIDTH - 44
    code = config["code"]
    size = 16
    shown = typed(len(code), math.floor((time - t0 - 0.25) * 25 * 1.1), 0, 9)
    width = text_in_place(c, code, 0, shown, right, 150, size, 500, 0.08 * size, align="right", family="mono")
    if shown:
        c.rect(right - width - 18, 150 - 10.5, right - width - 10, 150 - 2.5, "ink")
    loaded = reveal(time, t0 + 0.55, 0.3)
    if loaded > 0:
        size = 13
        c.text("PERSONAL INFORMATION", right, 182, size, 500, 0.08 * size, align="right", opacity=loaded)
        c.text("LOADED", right - 15, 200, size, 500, 0.08 * size, align="right", opacity=loaded)
        c.rect(right - 8, 191.5, right, 199.5, "ink", loaded)

    # bottom-left section line: the bar runs out, then the name types
    bar = reveal(time, t0 + 0.2, 0.25)
    if bar > 0:
        kc = K_CHROME
        c.rect(0, 289 - 6.6 - 6.5 * kc, 46 * kc * bar, 289 - 6.6 + 6.5 * kc, "ink")
        label = "PERSONNEL SECTION"
        shown = typed(len(label), math.floor((time - t0 - 0.35) * 25 * 1.1), 0, 10)
        size = 19 * kc
        text_in_place(c, label, 0, shown, 73 * kc, 289, size, 700, 0.01 * size)


def draw_caption(c: Canvas, config: dict, frame: float):
    t = frame / 25
    for index, (start, end) in enumerate(((6.8, 9.04), (11.28, 14.4), (19.48, 22.0), (22.84, math.inf))):
        if start <= t < end:
            opacity = progress(t, start, start + 0.08)
            if end < math.inf:
                opacity = min(opacity, 1 - progress(t, end - 0.08, end))
            size = 23 * K_CHROME
            # The website's paper halo keeps the caption clear of the rings it crosses.
            c.text(config["captions"][index], CX, 309, size, 500, 0.04 * size, align="center",
                   role="paper", opacity=0.85 * opacity, stroke=2.5)
            c.text(config["captions"][index], CX, 309, size, 500, 0.04 * size, align="center",
                   opacity=opacity)


def render_frame(time: float, config: dict, theme: str) -> Image.Image:
    c = Canvas(WIDTH, HEIGHT, theme, scale=SCALE, background=None)
    c.image = background(theme).copy()
    c.opaque = True
    frame = pv_frame(time)
    f = math.floor(frame + 0.00001)
    draw_chrome(c, config, frame, f)
    draw_access(c, f)
    draw_identity(c, frame, f)
    draw_scan(c, frame, f, theme)
    draw_card(c, config, frame, f, theme)
    draw_profile(c, config, time)
    draw_caption(c, config, frame)
    image = c.result()
    if image.size != (config["width"], config["height"]):
        image = image.resize((config["width"], config["height"]), Image.Resampling.LANCZOS)
    return image


def palette(config: dict, theme: str, times: list[float]) -> Image.Image:
    """One 256-colour palette for the whole clip (an APNG shares a single PLTE).

    Indexed frames are about a third of the RGB size. The theme's own colours
    and their anti-aliasing ramps are reserved first, so small accents such as
    the orange dots survive; the paper and helices take most of the rest.
    """
    colors = THEMES[theme]
    pale = (255, 255, 255) if theme == "light" else tuple(round(mix(p, i, 0.42))
                                                        for p, i in zip(colors["paper"], colors["ink"]))
    ramps = ((colors["ink"], colors["paper"], 28), (colors["ink"], colors["paper_hi"], 12),
             (colors["tag_ink"], colors["tag"], 20), (colors["orange"], colors["paper"], 12),
             (colors["orange"], colors["paper_hi"], 6), (pale, colors["paper"], 8))
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
        # APNG num_plays=1 stops on the final still. SOURCE patches avoid
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
