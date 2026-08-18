from __future__ import annotations

import unittest

import cv2
import numpy as np

from app.demo.demo_image import create_demo_image
from app.imaging.detector import (
    DetectorSettings,
    MotifCandidate,
    MotifDetector,
    _RawComponent,
    _attach_orphan_groups,
    _group_nearby_components,
    _infer_regular_tile_grid,
)


class DetectorGroupingTests(unittest.TestCase):
    def test_camera_frame_and_uneven_lighting_preserve_motif_centers(self) -> None:
        base = create_demo_image(900, 600)
        settings = DetectorSettings(
            minimum_area_px=220,
            morphological_cleanup=0.25,
            merge_distance_px_x=10,
            merge_distance_px_y=10,
        )
        expected = MotifDetector().detect(base, settings)

        # Give the motifs some fabric margin, then reproduce two normal camera
        # conditions: an uneven light/shadow field and a dark laser-bed surround.
        fabric = cv2.copyMakeBorder(
            base,
            100,
            100,
            100,
            100,
            cv2.BORDER_CONSTANT,
            value=(218, 226, 232),
        )
        height, width = fabric.shape[:2]
        y_grid, x_grid = np.mgrid[0:height, 0:width]
        illumination = (
            0.98
            + 0.00008 * x_grid
            - 0.00012 * y_grid
            - 0.18
            * np.exp(
                -(
                    np.square(x_grid - 760) / (2 * 220**2)
                    + np.square(y_grid - 250) / (2 * 170**2)
                )
            )
        )
        uneven = np.clip(
            fabric.astype(np.float32) * illumination[:, :, None], 0, 255
        ).astype(np.uint8)
        camera_image = cv2.copyMakeBorder(
            uneven,
            40,
            40,
            40,
            40,
            cv2.BORDER_CONSTANT,
            value=(42, 38, 35),
        )

        actual = MotifDetector().detect(camera_image, settings)

        self.assertEqual(len(expected), 12)
        self.assertEqual(len(actual), len(expected))
        expected_shifted = [
            (candidate.center_px[0] + 140, candidate.center_px[1] + 140)
            for candidate in expected
        ]
        for candidate, expected_center in zip(actual, expected_shifted):
            self.assertAlmostEqual(
                candidate.center_px[0], expected_center[0], delta=4
            )
            self.assertAlmostEqual(
                candidate.center_px[1], expected_center[1], delta=4
            )

    def test_center_uses_robust_extent_instead_of_ink_mass(self) -> None:
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
        foreground_rows = np.nonzero(np.any(image < 200, axis=2))[0]
        ink_mass_y = float(foreground_rows.mean())
        box_center_y = y + height / 2.0
        self.assertAlmostEqual(candidate.center_px[0], x + width / 2.0, delta=1)
        self.assertGreater(candidate.center_px[1], box_center_y + 10)
        self.assertLess(candidate.center_px[1], ink_mass_y - 10)

    def test_small_merged_fragment_does_not_pull_center_from_visual_core(self) -> None:
        image = np.full((260, 300, 3), 235, dtype=np.uint8)
        cv2.rectangle(image, (100, 110), (200, 170), (35, 65, 200), -1)
        # This strong fragment is close enough to be grouped, but is too small
        # to define the center of the motif.
        cv2.rectangle(image, (94, 86), (106, 98), (35, 65, 200), -1)

        candidates = MotifDetector().detect(
            image,
            DetectorSettings(
                minimum_area_px=100,
                morphological_cleanup=0,
                merge_distance_px_x=20,
                merge_distance_px_y=20,
            ),
        )

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        x, y, width, height = candidate.bounding_box_px
        box_center = (x + width / 2.0, y + height / 2.0)
        expected_visual_center = (150.0, 140.0)
        self.assertGreater(
            np.hypot(
                box_center[0] - expected_visual_center[0],
                box_center[1] - expected_visual_center[1],
            ),
            10,
        )
        self.assertLess(
            np.hypot(
                candidate.center_px[0] - expected_visual_center[0],
                candidate.center_px[1] - expected_visual_center[1],
            ),
            2,
        )

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

    def test_texture_specks_cannot_bridge_neighboring_motifs(self) -> None:
        components = [
            _RawComponent((0, 0, 40, 40), 1000, 60.0, 1),
            _RawComponent((45, 10, 5, 5), 30, 40.0, 2),
            _RawComponent((54, 10, 5, 5), 30, 40.0, 3),
            _RawComponent((63, 10, 5, 5), 30, 40.0, 4),
            _RawComponent((72, 10, 5, 5), 30, 40.0, 5),
            _RawComponent((81, 10, 5, 5), 30, 40.0, 6),
            _RawComponent((90, 0, 40, 40), 1000, 60.0, 7),
        ]

        groups = _group_nearby_components(
            components, 10.0, 10.0, core_area_px=250
        )

        label_groups = [
            {component.label_id for component in group} for group in groups
        ]
        self.assertFalse(
            any({1, 7}.issubset(labels) for labels in label_groups)
        )

    def test_single_detached_detail_can_rejoin_its_clear_parent(self) -> None:
        parent = [_RawComponent((0, 20, 50, 50), 1200, 60.0, 1)]
        detail = [_RawComponent((15, 0, 12, 10), 120, 60.0, 2)]

        groups = _attach_orphan_groups(
            [parent, detail],
            minimum_area_px=100,
            merge_distance_px_x=8.0,
            merge_distance_px_y=8.0,
        )

        self.assertEqual(len(groups), 1)
        self.assertEqual({item.label_id for item in groups[0]}, {1, 2})

    def test_irregular_free_layout_does_not_enable_tile_consolidation(self) -> None:
        centers = [
            (25.0, 25.0),
            (62.0, 88.0),
            (145.0, 52.0),
            (272.0, 116.0),
            (338.0, 188.0),
            (300.0, 267.0),
            (83.0, 311.0),
            (214.0, 348.0),
            (376.0, 379.0),
        ]
        candidates = [
            MotifCandidate(center, (int(center[0]), int(center[1]), 8, 8), 0.8, 64)
            for center in centers
        ]

        self.assertIsNone(_infer_regular_tile_grid(candidates, 400, 400))


if __name__ == "__main__":
    unittest.main()
