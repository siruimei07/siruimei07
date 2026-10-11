import unittest

from PIL import Image

from build_banner import build_animation, read_transition


class BannerTransitionTests(unittest.TestCase):
    def setUp(self):
        self.red = Image.new("RGBA", (3, 2), (255, 0, 0, 255))
        self.blue = Image.new("RGBA", (3, 2), (0, 0, 255, 255))

    def test_transition_defaults_and_custom_settings(self):
        self.assertEqual(read_transition({}, 5000), (0, 0))
        self.assertEqual(read_transition({"effect": "none"}, 5000), (0, 0))
        self.assertEqual(read_transition({"effect": "crossfade"}, 5000), (500, 4))
        self.assertEqual(
            read_transition({"effect": "crossfade", "duration_ms": 503, "frames": 3}, 5000),
            (503, 3),
        )

    def test_invalid_transition_settings(self):
        invalid = [None, [], "crossfade", True, {"effect": "slide"}]
        invalid.extend(
            {"effect": "crossfade", "duration_ms": value}
            for value in (None, True, 0, -1, 5000, 5001, 0.5, "500")
        )
        invalid.extend(
            {"effect": "crossfade", "frames": value}
            for value in (None, True, 0, -1, 61, 1.5, "4")
        )
        invalid.append({"effect": "crossfade", "duration_ms": 3, "frames": 4})
        for settings in invalid:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                read_transition(settings, 5000)

    def test_rounding_preserves_each_five_second_period(self):
        sources = [self.red, self.blue]
        originals = [frame.tobytes() for frame in sources]
        animation, durations = build_animation(sources, 5000, 503, 4)
        self.assertEqual(len(animation), 10)
        self.assertEqual(durations, [4497, 125, 126, 126, 126] * 2)
        self.assertEqual(sum(durations), 10000)
        for index, original in enumerate(originals):
            self.assertEqual(animation[index * 5].tobytes(), original)
            self.assertEqual(sources[index].tobytes(), original)

    def test_last_image_crossfades_back_to_first(self):
        animation, _ = build_animation([self.red, self.blue], 5000, 500, 3)
        self.assertEqual(len(animation), 8)
        first_mix = animation[1].getpixel((0, 0))
        final_mix = animation[-1].getpixel((0, 0))
        self.assertGreater(first_mix[0], first_mix[2])
        self.assertGreater(final_mix[0], 190)
        self.assertLess(final_mix[2], 65)
        self.assertEqual(final_mix[3], 255)

    def test_transparent_pixels_do_not_add_color_halos(self):
        transparent_blue = Image.new("RGBA", (3, 2), (0, 0, 255, 0))
        animation, _ = build_animation([self.red, transparent_blue], 5000, 500, 1)
        for index in (1, 3):
            pixel = animation[index].getpixel((0, 0))
            self.assertEqual(pixel[:3], (255, 0, 0))
            self.assertIn(pixel[3], (127, 128))

    def test_disabled_transition_and_single_image_keep_original_frames(self):
        for sources, duration, steps in (
            ([self.red, self.blue], 0, 0),
            ([self.red], 500, 4),
        ):
            with self.subTest(source_count=len(sources), duration=duration):
                animation, durations = build_animation(sources, 5000, duration, steps)
                self.assertEqual(durations, [5000] * len(sources))
                self.assertEqual(len(animation), len(sources))
                self.assertEqual(
                    [frame.tobytes() for frame in animation],
                    [frame.tobytes() for frame in sources],
                )


if __name__ == "__main__":
    unittest.main()
