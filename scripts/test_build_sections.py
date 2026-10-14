import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from PIL import Image

from build_sections import BUTTON_HEIGHT, DENSITY, HEADER_SIZE, build, button_width, read_config
from rhine import FONT_DIR, ROOT, require_glyphs


CONFIG_PATH = ROOT / "banners" / "sections" / "config.json"


class FontProvenanceTests(unittest.TestCase):
    def test_bundled_fonts_match_their_pinned_sources(self):
        provenance = json.loads((FONT_DIR / "provenance.json").read_text(encoding="utf-8"))
        listed = set()
        for source in provenance.values():
            for name, entry in source["files"].items():
                listed.add(name)
                with self.subTest(name=name):
                    digest = hashlib.sha256((FONT_DIR / name).read_bytes()).hexdigest()
                    self.assertEqual(digest, entry["sha256"])
        bundled = {path.name for path in FONT_DIR.iterdir()} - {"provenance.json", "README.md"}
        self.assertEqual(bundled, listed)

    def test_missing_chinese_glyphs_are_reported(self):
        require_glyphs("作品与公开仓库")
        with self.assertRaisesRegex(ValueError, "鑫"):
            require_glyphs("作品鑫")


class SectionConfigTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="profile-sections-config-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "config.json"
        self.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def load(self, value):
        self.path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return read_config(self.path)

    def test_repository_config_is_valid(self):
        self.assertEqual(self.load(self.config), self.config)

    def test_rejects_bad_ids_duplicates_and_styles(self):
        cases = []
        bad_id = json.loads(json.dumps(self.config))
        bad_id["headers"][0]["id"] = "../escape"
        cases.append((bad_id, "id"))
        duplicate = json.loads(json.dumps(self.config))
        duplicate["buttons"].append(dict(duplicate["buttons"][0]))
        cases.append((duplicate, "duplicate"))
        style = json.loads(json.dumps(self.config))
        style["buttons"][0]["style"] = "ghost"
        cases.append((style, "style"))
        number = json.loads(json.dumps(self.config))
        number["headers"][0]["number"] = "1"
        cases.append((number, "number"))
        for value, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.load(value)

    def test_rejects_non_ascii_labels_and_unknown_chinese_glyphs(self):
        label = json.loads(json.dumps(self.config))
        label["headers"][0]["title"] = "档案"
        with self.assertRaisesRegex(ValueError, "title"):
            self.load(label)
        glyph = json.loads(json.dumps(self.config))
        glyph["headers"][0]["zh"] = "鑫"
        with self.assertRaisesRegex(ValueError, "missing"):
            self.load(glyph)
        for value in (None, [], "headers"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.load(value)


class ReadmeReferenceTests(unittest.TestCase):
    def test_readme_shows_every_section_image_at_its_design_size(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        config = read_config(CONFIG_PATH)
        for item in config["buttons"]:
            with self.subTest(button=item["id"]):
                match = re.search(rf'button-{item["id"]}-light\.png" width="(\d+)"', readme)
                self.assertIsNotNone(match)
                self.assertEqual(int(match.group(1)), button_width(item))
        for name in [f"header-{item['id']}" for item in config["headers"]]:
            for theme in ("light", "dark"):
                with self.subTest(image=name, theme=theme):
                    self.assertEqual(readme.count(f"./assets/sections/{name}-{theme}.png"), 1)


class SectionOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="profile-sections-output-")
        cls.addClassCleanup(temporary.cleanup)
        config = read_config(CONFIG_PATH)
        cls.filled = {f"button-{item['id']}" for item in config["buttons"] if item["style"] == "filled"}
        cls.first = build(config, Path(temporary.name) / "first")
        cls.second = build(config, Path(temporary.name) / "second")

    def test_every_image_has_both_themes_at_double_density(self):
        config = read_config(CONFIG_PATH)
        sizes = {"header": HEADER_SIZE}
        sizes.update({f"button-{item['id']}": (button_width(item), BUTTON_HEIGHT) for item in config["buttons"]})
        names = {path.name for path in self.first}
        for path in self.first:
            with self.subTest(name=path.name):
                other = "dark" if path.stem.endswith("light") else "light"
                self.assertIn(path.name.replace(path.stem.rsplit("-", 1)[1], other), names)
                with Image.open(path) as image:
                    self.assertEqual(image.mode, "RGBA")
                    kind = path.stem.rsplit("-", 1)[0]
                    width, height = sizes.get(kind) or sizes[kind.split("-", 1)[0]]
                    self.assertEqual(image.size, (width * DENSITY, height * DENSITY))
                    # Only the filled button is opaque; the rest blends into either GitHub theme.
                    lowest = image.getchannel("A").getextrema()[0]
                    self.assertEqual(lowest, 255 if path.stem.rsplit("-", 1)[0] in self.filled else 0)

    def test_builds_are_byte_identical(self):
        for first, second in zip(self.first, self.second):
            with self.subTest(name=first.name):
                self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
