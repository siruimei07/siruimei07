"""Crop local artwork into profile banners without repainting or resampling it.

Each output retains the cropped source RGB pixels. Only its alpha channel is
changed, fading the lower half into either GitHub background theme.
"""

import argparse
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
import shutil

from PIL import Image, ImageChops, ImageOps


ROOT = Path(__file__).resolve().parents[1]
FORMATS = {".png", ".jpg", ".jpeg", ".webp"}


def read_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def crop_offset(value, available: int, name: str) -> int:
    """Integers are source pixels; floats from 0.0 to 1.0 are relative positions."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be an integer pixel offset or a decimal between 0.0 and 1.0")
    if isinstance(value, float):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name}: a decimal crop position must be between 0.0 and 1.0")
        return round(available * value)
    if not 0 <= value <= available:
        raise ValueError(f"{name}: pixel offset {value} is outside 0..{available}")
    return value


def make_banner(source: Path, settings: dict) -> Image.Image:
    with Image.open(source) as original:
        # EXIF orientation is a lossless pixel rearrangement, not a resize.
        canvas = ImageOps.exif_transpose(original).convert("RGBA")
    width, height = canvas.size
    if width / height < 3:
        crop_width, crop_height = width, math.ceil(width / 3)
    else:
        crop_width, crop_height = min(width, height * 3), height
    left = crop_offset(settings.get("crop_x", 0.5), width - crop_width, f"{source.name}: crop_x")
    top = crop_offset(settings.get("crop_y", 0.5), height - crop_height, f"{source.name}: crop_y")
    banner = canvas.crop((left, top, left + crop_width, top + crop_height))

    # Smoothstep has zero slope at both ends of the transition.
    opacity = []
    for y in range(crop_height):
        progress = max(0.0, min(1.0, (y / max(1, crop_height - 1) - 0.5) * 2))
        opacity.append(round(255 * (1 - progress * progress * (3 - 2 * progress))))
    mask = Image.new("L", (1, crop_height))
    mask.putdata(opacity)
    mask = mask.resize((crop_width, crop_height), resample=Image.Resampling.NEAREST)
    # Multiplication also preserves any transparency already in a source image.
    banner.putalpha(ImageChops.multiply(banner.getchannel("A"), mask))
    return banner


def select_source(sources: list[Path], selection: str, config: dict, day: date) -> Path:
    if selection == "slideshow":
        selection = "default"
    if selection == "auto":
        # Filesystem ordering and machine locale never affect the rotation.
        return sources[day.toordinal() % len(sources)]
    if selection == "default":
        selection = config.get("default", sources[0].name)
    matches = [source for source in sources if source.name == selection]
    if not matches:
        raise ValueError(f"Unknown banner {selection!r}; choose slideshow, auto, default, or one of: "
                         + ", ".join(source.name for source in sources))
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--select", help="slideshow, auto, default, or an exact source filename; defaults to config.json selection")
    parser.add_argument("--save-selection", action="store_true",
                        help="persist an explicit --select choice in config.json")
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(timezone.utc).date(),
                        help="UTC date for deterministic daily rotation (YYYY-MM-DD)")
    parser.add_argument("--source-dir", type=Path, default=ROOT / "banners" / "originals")
    parser.add_argument("--config", type=Path, default=ROOT / "banners" / "config.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "assets" / "banners")
    parser.add_argument("--output", type=Path, default=ROOT / "assets" / "banner.png")
    parser.add_argument("--static-output", type=Path, default=ROOT / "assets" / "banner-static.png")
    args = parser.parse_args()
    if args.save_selection and not args.select:
        parser.error("--save-selection requires an explicit --select value")

    config = read_config(args.config)
    if not args.source_dir.is_dir():
        parser.error(f"Banner source folder does not exist: {args.source_dir}")
    sources = sorted((p for p in args.source_dir.iterdir() if p.is_file() and p.suffix.lower() in FORMATS),
                     key=lambda p: (p.name.casefold(), p.name))
    if not sources:
        parser.error(f"No PNG, JPG, JPEG, or WebP images in {args.source_dir}")
    # Avoid one source silently overwriting another with the same stem.
    stems = [p.stem.casefold() for p in sources]
    if len(set(stems)) != len(stems):
        parser.error("Source filenames must have unique stems, even with different extensions")

    try:
        selection = args.select or config.get("selection", "slideshow")
        selected = select_source(sources, selection, config, args.date)
        interval = config.get("interval_ms", 12000)
        if isinstance(interval, bool) or not isinstance(interval, int) or interval < 1000:
            raise ValueError("interval_ms must be an integer of at least 1000 milliseconds")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        banners = {}
        for source in sources:
            banner = make_banner(source, config.get("images", {}).get(source.name, {}))
            banners[source.name] = banner
            destination = args.output_dir / f"{source.stem}.png"
            banner.save(destination, optimize=True)
            print(f"Built {destination.name}: {banner.width} x {banner.height}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.static_output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.output_dir / f"{selected.stem}.png", args.static_output)
        if selection == "slideshow":
            # The poster/default artwork leads, followed by filename order.
            ordered = [selected] + [source for source in sources if source != selected]
            frame_width = min(1600, max(banner.width for banner in banners.values()))
            frame_size = (frame_width, math.ceil(frame_width / 3))
            frames = []
            for source in ordered:
                banner = banners[source.name]
                if banner.size == frame_size:
                    frame = banner.copy()
                else:
                    # Only mixed-size additions need resampling to an APNG canvas.
                    fitted = ImageOps.contain(banner, frame_size, Image.Resampling.LANCZOS)
                    frame = Image.new("RGBA", frame_size, (0, 0, 0, 0))
                    frame.paste(fitted, ((frame.width - fitted.width) // 2,
                                        (frame.height - fitted.height) // 2))
                frames.append(frame)
            # SOURCE blending replaces every pixel, including full transparency.
            frames[0].save(args.output, format="PNG", save_all=True,
                           append_images=frames[1:], duration=interval,
                           loop=0, disposal=0, blend=0, optimize=True)
            print(f"Slideshow: {len(frames)} frames, {interval} ms each, infinite loop")
        else:
            shutil.copyfile(args.output_dir / f"{selected.stem}.png", args.output)
        if args.save_selection:
            config["selection"] = args.select
            args.config.parent.mkdir(parents=True, exist_ok=True)
            args.config.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Active banner: {selected.name} ({args.date.isoformat()} UTC) -> {args.output}")
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
