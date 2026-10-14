import math
import unittest

import boot_tracks
from rhine import MARK_CONTOUR, contour_points, path_points, track


class TrackInterpolationTests(unittest.TestCase):
    """Reference values computed with the website's src/boot/tracks.ts."""

    def test_ring_radius_matches_the_website(self):
        keys = boot_tracks.SCAN["radius"]
        for frame, expected in ((489.5, 1769.047), (497, 1095.0), (502.5, 761.028),
                                (520, 320.5), (545.3, 257.796), (568, 246)):
            with self.subTest(frame=frame):
                self.assertAlmostEqual(track(keys, frame), expected, places=3)

    def test_lockup_slide_matches_the_website(self):
        for local, expected in ((0.5, 225.722), (1.5, 200.083), (5.5, 85.523), (12.25, 24.724)):
            with self.subTest(local=local):
                self.assertAlmostEqual(boot_tracks.brand_track(local, 0)["x"], expected, places=3)
        # Each lockup line repeats the trajectory two frames later.
        self.assertEqual(boot_tracks.brand_track(7, 1), boot_tracks.brand_track(5, 0))

    def test_tracks_hold_flat_beyond_their_keys(self):
        keys = ((0, 1.0), (10, 3.0), (20, 2.0))
        self.assertEqual(track(keys, -5), 1.0)
        self.assertEqual(track(keys, 25), 2.0)
        self.assertEqual(track(((0, 0.0), (4, 8.0)), 1), 2.0)  # two keys: linear

    def test_logo_dash_rests_with_the_printed_gap_and_then_travels(self):
        resting = boot_tracks.logo_track(300)
        self.assertAlmostEqual(resting["start"], 0.211, places=4)
        self.assertAlmostEqual(resting["start"] + resting["length"], 1.1835, places=4)
        self.assertAlmostEqual(resting["stroke"], 26)
        self.assertAlmostEqual(boot_tracks.logo_track(486)["start"], 0.9365 + 0.0275, places=4)
        self.assertEqual(boot_tracks.logo_track(229)["signs"], 0)
        self.assertEqual(boot_tracks.logo_track(270)["plus_angle"], -90)


class MarkGeometryTests(unittest.TestCase):
    def test_contour_is_closed_and_has_the_reference_length(self):
        points = contour_points()
        self.assertEqual(points[0], points[-1])
        length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
        self.assertAlmostEqual(length, 771.28, delta=0.5)

    def test_path_parser_handles_smooth_curves_and_relative_lines(self):
        loops = path_points("M0 0C0 10 10 10 10 0S20 -10 20 0", steps=4)
        self.assertEqual(len(loops), 1)
        self.assertEqual(loops[0][-1], (20.0, 0.0))
        signs = path_points("M44 70h50M69 45v50")
        self.assertEqual(signs, [[(44.0, 70.0), (94.0, 70.0)], [(69.0, 45.0), (69.0, 95.0)]])
        with self.assertRaises(ValueError):
            path_points("M0 0L10 10")
        self.assertTrue(MARK_CONTOUR.endswith("Z"))


if __name__ == "__main__":
    unittest.main()
