"""Cut the small WOFF2 fonts embedded in the metric cards from banners/fonts/.

The cards are SVG images, so GitHub shows them without loading any web font;
embedding Montserrat, JetBrains Mono and a few Noto Sans SC glyphs as data URIs
makes them render like the website on every viewer. Only needed when the card
labels change. Requires fontTools and brotli (not used by the daily workflow):

    python -m pip install fonttools==4.60.1 brotli==1.2.0
    python scripts/build_card_fonts.py
"""

import hashlib
import json
from pathlib import Path
import re

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "banners" / "fonts"
OUTPUT = ROOT / "scripts" / "metrics" / "fonts"
LABELS = (ROOT / "scripts" / "metrics" / "theme.mjs", ROOT / "scripts" / "metrics" / "templates" / "traffic.ejs")
# Printable ASCII plus the few symbols the cards print: · – — … ↑ ↓ ■
LATIN = [*range(0x20, 0x7F), 0xB7, 0x2013, 0x2014, 0x2026, 0x2191, 0x2193, 0x25A0]
FACES = (
    ("mont-500", "Montserrat[wght].ttf", 500),
    ("mont-600", "Montserrat[wght].ttf", 600),
    ("mont-700", "Montserrat[wght].ttf", 700),
    ("jbm-400", "JetBrainsMono[wght].ttf", 400),
    ("jbm-500", "JetBrainsMono[wght].ttf", 500),
    ("zh-500", "noto-sans-sc-500.woff2", None),
)


def card_chinese() -> str:
    """Every CJK character in the card labels, so the subset always covers them."""
    text = "".join(path.read_text(encoding="utf-8") for path in LABELS)
    return "".join(sorted(set(re.findall(r"[\u3000-\u9fff\uff00-\uffef]", text))))


def build() -> dict:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    chinese = card_chinese()
    digests = {}
    for name, source, weight in FACES:
        font = TTFont(SOURCE / source, recalcTimestamp=False)
        if weight is not None:
            font = instantiateVariableFont(font, {"wght": weight})
        options = subset.Options()
        options.flavor = "woff2"
        options.layout_features = ["kern", "tnum"]
        options.hinting = False
        options.desubroutinize = True
        options.name_IDs = ["*"]
        subsetter = subset.Subsetter(options)
        if weight is None:
            subsetter.populate(text=chinese)
        else:
            subsetter.populate(unicodes=LATIN)
        subsetter.subset(font)
        font.flavor = "woff2"
        target = OUTPUT / f"{name}.woff2"
        font.save(target)
        digests[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
        print(f"{target.name}: {target.stat().st_size:,} bytes")
    manifest = {
        "source": "banners/fonts (see banners/fonts/provenance.json)",
        "generator": "scripts/build_card_fonts.py with fontTools 4.60.1 and brotli 1.2.0",
        "chinese": chinese,
        "sha256": digests,
    }
    (OUTPUT / "provenance.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    return manifest


if __name__ == "__main__":
    build()
