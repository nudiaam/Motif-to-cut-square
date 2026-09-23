"""General failure mechanisms, independent of a collection's motif classes."""
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.imaging.camera_panel import _measured_lines
from app.imaging.detector import (
    DetectionResult, DetectorSettings, MotifCandidate, MotifDetector,
    _consolidate_grid_candidates,
)
from app.imaging.extent_review import review_extents
from app.imaging.panel_grid import PanelGrid


class GlobalDetectionContractTests(unittest.TestCase):
    def test_disconnected_accessory_has_same_owner_for_every_grid_source(self):
        main = MotifCandidate((50, 50), (30, 25, 40, 50), .8, 1600)
        accessory = MotifCandidate((80, 32), (75, 27, 10, 10), .7, 80)
        expected = None
        for source in ('visual', 'camera', 'pattern', 'fabric', 'reference', 'automatic', 'manual'):
            grid = PanelGrid.regular(600, 400, 6, 4, confidence=.95, source=source)
            result = _consolidate_grid_candidates((main, accessory), grid)
            self.assertEqual(len(result), 1, source)
            self.assertEqual(result[0].bounding_box_px, (30, 25, 55, 50))
            if expected is not None:
                self.assertEqual(result, expected, source)
            expected = result

    def test_measured_print_extent_is_not_forced_to_cloth_edges(self):
        xs = np.arange(1000)
        profile = sum(30*np.exp(-.5*((xs-p)/3)**2) for p in (195, 345, 495, 645, 795))
        lines = _measured_lines(profile, 6)
        self.assertIsNotNone(lines)
        np.testing.assert_allclose(lines, 45+np.arange(7)*150, atol=4)
        self.assertIsNone(_measured_lines(np.zeros(1000), 6))
        self.assertIsNone(_measured_lines(profile, 2))

    def test_extremity_remains_available_beyond_old_grabcut_rectangle(self):
        for end in (146, 170, 185, 190, 196):
            with self.subTest(end=end):
                image = np.full((200, 200, 3), 230, np.uint8)
                cv2.ellipse(image, (100, 95), (30, 50), 0, 0, 360, (45, 75, 110), -1)
                cv2.rectangle(image, (95, 110), (105, end), (45, 75, 110), -1)
                result = MotifDetector._local_colour_region(image, 150)
                self.assertIsNotNone(result)
                self.assertEqual(result.bounding_box_px, (70, 45, 61, end-45+1))

    def test_original_pixels_can_contradict_a_truncated_detection(self):
        image = np.full((200, 200, 3), 230, np.uint8)
        cv2.rectangle(image, (70, 45), (130, 170), (45, 75, 110), -1)
        truncated = MotifCandidate((100, 95), (70, 45, 61, 101), .9, 6000)
        complete = replace(truncated, center_px=(100, 108), bounding_box_px=(70, 45, 61, 126))
        result = review_extents(image, (truncated, complete))
        self.assertTrue(result[0].review_reasons)
        self.assertFalse(result[1].review_reasons)
        self.assertEqual(result[0].bounding_box_px, truncated.bounding_box_px)

    def test_neighbour_does_not_automatically_extend_a_complete_motif(self):
        image = np.full((200, 240, 3), 230, np.uint8)
        cv2.rectangle(image, (70, 45), (130, 145), (45, 75, 110), -1)
        cv2.rectangle(image, (140, 45), (200, 145), (45, 75, 110), -1)
        candidate = MotifCandidate((100, 95), (70, 45, 61, 101), .9, 6000)
        self.assertFalse(review_extents(image, (candidate,))[0].review_reasons)

    def test_automatic_fallback_regions_are_explicitly_uncertain(self):
        image = np.full((400, 600, 3), 230, np.uint8)
        candidate = MotifCandidate((100, 95), (70, 45, 61, 101), .9, 6000)
        detector = MotifDetector()
        with patch.object(detector, '_detect_layout', return_value=DetectionResult((candidate,))):
            result = detector.detect_with_layout(image, DetectorSettings())
        self.assertIn('No reliable panel layout', result.candidates[0].review_reasons[0])

    def test_dark_camera_margin_does_not_change_compositions_or_geometry(self):
        image = cv2.imread(str(Path(__file__).parent / 'fixtures/generated/straight/dogs_6x4.png'))
        baseline = None
        for margin in (0, 80, 160):
            expanded = cv2.copyMakeBorder(image, margin, margin, margin, margin,
                                         cv2.BORDER_CONSTANT, value=(20, 20, 20))
            result = MotifDetector().detect_with_layout(expanded, DetectorSettings())
            self.assertEqual(len(result.candidates), 24)
            self.assertEqual((result.panel_grid.columns, result.panel_grid.rows), (6, 4))
            # Compare spatially sorted positions, independent of label order.
            centers = np.array(sorted((c.center_px[0]-margin, c.center_px[1]-margin)
                                      for c in result.candidates))
            if baseline is None:
                baseline = centers
            else:
                np.testing.assert_allclose(centers, baseline, atol=6)


if __name__ == '__main__':
    unittest.main()
