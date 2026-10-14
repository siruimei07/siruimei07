import hashlib
import json
from pathlib import Path
import re
import unittest

from PIL import ImageFont


ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "scripts" / "metrics" / "fonts"
LABELS = (ROOT / "scripts" / "metrics" / "theme.mjs", ROOT / "scripts" / "metrics" / "templates" / "traffic.ejs")


class CardFontTests(unittest.TestCase):
    """The metric cards embed font subsets; build_card_fonts.py must rerun when labels change."""

    def setUp(self):
        self.provenance = json.loads((FONTS / "provenance.json").read_text(encoding="utf-8"))

    def test_subsets_match_their_recorded_hashes(self):
        files = {path.name for path in FONTS.glob("*.woff2")}
        self.assertEqual(files, set(self.provenance["sha256"]))
        for name, digest in self.provenance["sha256"].items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256((FONTS / name).read_bytes()).hexdigest(), digest)

    def test_chinese_subset_covers_every_card_label(self):
        text = "".join(path.read_text(encoding="utf-8") for path in LABELS)
        used = "".join(sorted(set(re.findall(r"[\u3000-\u9fff\uff00-\uffef]", text))))
        self.assertEqual(used, self.provenance["chinese"], "run scripts/build_card_fonts.py")
        face = ImageFont.truetype(str(FONTS / "zh-500.woff2"), 40)
        missing = bytes(face.getmask("\U000F0000"))
        for character in used:
            with self.subTest(character=character):
                self.assertNotEqual(bytes(face.getmask(character)), missing)


if __name__ == "__main__":
    unittest.main()
