import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from build_loading import build, frame_times, read_config


SMALL_CONFIG = {
    "width": 640,
    "height": 160,
    "fps": 10,
    "duration_ms": 11000,
    "profile_name": "SIRUIMEI07",
    "subtitle": "PUBLIC ARCHIVE",
}


class LoadingTimingTests(unittest.TestCase):
    def test_rounding_keeps_exact_duration_and_positive_frame_holds(self):
        for duration_ms, fps in ((11000, 10), (11003, 24), (12000, 20)):
            with self.subTest(duration_ms=duration_ms, fps=fps):
                times, durations = frame_times(duration_ms, fps)
                self.assertEqual(len(times), len(durations))
                self.assertEqual(times[0], 0)
                self.assertEqual(sum(durations), duration_ms)
                self.assertTrue(all(duration > 0 for duration in durations))
                self.assertLessEqual(max(durations) - min(durations), 1)
                elapsed = 0
                for time, duration in zip(times, durations):
                    self.assertAlmostEqual(time * 1000, elapsed)
                    elapsed += duration
                self.assertLess(times[-1] * 1000, duration_ms)


class LoadingConfigTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="profile-loading-config-")
        self.addCleanup(temporary.cleanup)
        self.config_path = Path(temporary.name) / "config.json"

    def load(self, value):
        self.config_path.write_text(json.dumps(value), encoding="utf-8")
        return read_config(self.config_path)

    def test_accepts_small_canvas_and_ascii_names_with_spaces(self):
        config = {**SMALL_CONFIG, "profile_name": "NAME SPACE", "subtitle": "PUBLIC RECORDS"}
        self.assertEqual(self.load(config), config)

    def test_rejects_non_object_configuration(self):
        for value in (None, [], True, "config"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "object"):
                self.load(value)

    def test_rejects_invalid_numbers_and_booleans(self):
        limits = {
            "width": (640, 1920),
            "height": (160, 600),
            "fps": (10, 30),
            "duration_ms": (11000, 20000),
        }
        for name, (minimum, maximum) in limits.items():
            for value in (None, True, False, minimum - 1, maximum + 1, float(minimum), str(minimum)):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, name):
                        self.load({**SMALL_CONFIG, name: value})
            missing = dict(SMALL_CONFIG)
            del missing[name]
            with self.subTest(name=name, missing=True), self.assertRaisesRegex(ValueError, name):
                self.load(missing)

    def test_rejects_unsupported_canvas_aspect_ratios(self):
        for width, height in ((640, 600), (1920, 160)):
            with self.subTest(width=width, height=height):
                with self.assertRaisesRegex(ValueError, "aspect ratio"):
                    self.load({**SMALL_CONFIG, "width": width, "height": height})

    def test_rejects_missing_empty_non_ascii_and_overlong_text(self):
        for name in ("profile_name", "subtitle"):
            for value in (None, True, 123, "", "   ", "A" * 25, "档案"):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, name):
                        self.load({**SMALL_CONFIG, name: value})
            missing = dict(SMALL_CONFIG)
            del missing[name]
            with self.subTest(name=name, missing=True), self.assertRaisesRegex(ValueError, name):
                self.load(missing)


class LoadingOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="profile-loading-output-")
        cls.addClassCleanup(temporary.cleanup)
        cls.first_dir = Path(temporary.name) / "first"
        cls.second_dir = Path(temporary.name) / "second"
        cls.first_outputs = build(dict(SMALL_CONFIG), cls.first_dir)
        cls.second_outputs = build(dict(SMALL_CONFIG), cls.second_dir)

    def test_both_themes_play_once_and_stop_on_the_static_welcome(self):
        static_pixels = {}
        for theme in ("light", "dark"):
            with self.subTest(theme=theme):
                with Image.open(self.first_dir / f"loading-{theme}.png") as animation:
                    self.assertTrue(animation.is_animated)
                    self.assertGreater(animation.n_frames, 1)
                    self.assertEqual(animation.size, (640, 160))
                    self.assertEqual(animation.info["loop"], 1)
                    self.assertFalse(animation.info.get("default_image", False))
                    first_pixels = animation.convert("RGB").tobytes()
                    durations = []
                    for index in range(animation.n_frames):
                        animation.seek(index)
                        durations.append(animation.info["duration"])
                    self.assertTrue(all(duration > 0 for duration in durations))
                    self.assertAlmostEqual(sum(durations), SMALL_CONFIG["duration_ms"], places=3)
                    final_pixels = animation.convert("RGB").tobytes()
                    self.assertNotEqual(first_pixels, final_pixels)

                with Image.open(self.first_dir / f"loading-static-{theme}.png") as static:
                    self.assertFalse(getattr(static, "is_animated", False))
                    self.assertEqual(static.size, (640, 160))
                    static_pixels[theme] = static.convert("RGB").tobytes()
                    self.assertEqual(final_pixels, static_pixels[theme])
        self.assertNotEqual(static_pixels["light"], static_pixels["dark"])

    def test_two_builds_produce_identical_files(self):
        expected = {
            "loading-light.png", "loading-dark.png",
            "loading-static-light.png", "loading-static-dark.png",
        }
        self.assertEqual({path.name for path in self.first_outputs}, expected)
        self.assertEqual({path.name for path in self.second_outputs}, expected)
        for name in sorted(expected):
            with self.subTest(name=name):
                first = hashlib.sha256((self.first_dir / name).read_bytes()).hexdigest()
                second = hashlib.sha256((self.second_dir / name).read_bytes()).hexdigest()
                self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
