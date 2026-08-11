from __future__ import annotations

import unittest

import cv2
import numpy as np

from app.imaging.detector import DetectorSettings, MotifDetector


class DetectorGroupingTests(unittest.TestCase):
    def test_center_uses_complete_visual_extent_not_ink_mass(self) -> None:
        image = np.full((260, 240, 3), 235, dtype=np.uint8)
        # A thin upper section connected to a visually dense lower body mimics
        # motifs such as a violin, ship, or sewing machine.
        cv2.rectangle(image, (116, 35), (124, 180), (25, 45, 80), -1)
        cv2.rectangle(image, (70, 145), (170, 220), (25, 45, 80), -1)

        candidates = MotifDetector().detect(
            image,
            DetectorSettings(
                minimum_area_px=100,
                morphological_cleanup=0,
                merge_distance_px_x=0,
                merge_distance_px_y=0,
            ),
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        x, y, width, height = candidate.bounding_box_px
        self.assertAlmostEqual(candidate.center_px[0], x + width / 2.0)
        self.assertAlmostEqual(candidate.center_px[1], y + height / 2.0)
        self.assertLess(candidate.center_px[1], 140.0)

    def test_nearby_fragments_are_grouped_without_merging_far_motif(self) -> None:
        image = np.full((300, 400, 3), 235, dtype=np.uint8)
        cv2.circle(image, (100, 150), 22, (40, 70, 210), -1)
        cv2.rectangle(image, (132, 145), (170, 155), (40, 70, 210), -1)
        cv2.circle(image, (310, 150), 24, (190, 80, 45), -1)

        separate = MotifDetector().detect(
            image,
            DetectorSettings(
                minimum_area_px=100,
                morphological_cleanup=0,
                merge_distance_px_x=0,
                merge_distance_px_y=0,
            ),
        )
        grouped = MotifDetector().detect(
            image,
            DetectorSettings(
                minimum_area_px=100,
                morphological_cleanup=0,
                merge_distance_px_x=20,
                merge_distance_px_y=20,
            ),
        )

        self.assertEqual(len(separate), 3)
        self.assertEqual(len(grouped), 2)


if __name__ == "__main__":
    unittest.main()
