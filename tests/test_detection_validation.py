"""Regressions for aliased grids, camera edges and misleading clean counts.

The new customer inputs are annotated screenshots, not source photographs.
Controlled image cases exercise the failure mechanisms; the original camera
fixtures in the other suites remain the real-photograph regression baseline.
"""
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from app.imaging.bed_reference import locate_bright_fabric
from app.imaging.detector import (
    DetectionResult, DetectorSettings, MotifCandidate, MotifDetector,
    _consolidate_grid_candidates,
)
from app.imaging.panel_grid import PanelGrid
from tests.test_visual_grid import printed_fabric


class DetectionValidationTests(unittest.TestCase):
    def test_wrong_visual_proposals_cannot_hide_stable_rows_or_columns(self):
        for columns, rows, bad_columns, bad_rows in ((6, 4, 4, 4), (7, 3, 5, 3), (4, 5, 4, 3)):
            with self.subTest(columns=columns, rows=rows):
                image = printed_fabric(columns, rows, panels=False)
                original = image.copy()
                h, w = image.shape[:2]
                wrong = PanelGrid.regular(w, h, bad_columns, bad_rows,
                                         bounds_px=(50, 50, w-50, h-50),
                                         confidence=.95, source="visual")
                detector = MotifDetector()
                # Inject only the bad proposal: foreground extraction, stability
                # checks, alternative fitting and cleanup all process real pixels.
                with patch("app.imaging.detector.infer_panel_grid", return_value=wrong):
                    result = detector.detect_with_layout(image, DetectorSettings(minimum_area_px=150))
                self.assertEqual((result.panel_grid.columns, result.panel_grid.rows), (columns, rows))
                self.assertEqual(len(result.candidates), columns * rows)
                self.assertTrue(detector.last_diagnostics["grid_notes"])
                np.testing.assert_array_equal(image, original)

    def test_fragmented_raw_foreground_does_not_veto_correct_visual_panels(self):
        image = cv2.imread(str(Path(__file__).parent / "fixtures/pastel_panels_camera.png"))
        detector = MotifDetector()
        result = detector.detect_with_layout(image, DetectorSettings())
        self.assertEqual(result.panel_grid.source, "visual")
        self.assertEqual((result.panel_grid.columns, result.panel_grid.rows), (6, 4))
        self.assertEqual(len(result.candidates), 24)
        self.assertFalse(detector.last_diagnostics["grid_notes"])

    def test_cleanup_does_not_require_a_matching_bed_reference(self):
        image = printed_fabric(6, 4, panels=False)
        candidates = tuple(MotifCandidate((105+c*110, 105+r*110),
                                          (85+c*110, 85+r*110, 40, 40), .8, 900)
                           for r in range(4) for c in range(6))
        fragment = MotifCandidate((115, 105), (100, 95, 30, 20), .5, 300)
        bed_mark = MotifCandidate((6, 170), (0, 155, 12, 30), .8, 300)
        grid = PanelGrid.regular(760, 540, 6, 4, bounds_px=(50, 50, 710, 490),
                                 confidence=.95, source="visual")
        for reference in (None, np.zeros((100, 100, 3), np.uint8)):
            with self.subTest(reference=reference is not None):
                detector = MotifDetector()
                detector.bed_reference = reference
                with patch.object(detector, "_detect_layout", return_value=DetectionResult(
                        candidates + (fragment, bed_mark), grid)):
                    result = detector.detect_with_layout(image, DetectorSettings())
                self.assertEqual(len(result.candidates), 24)
                self.assertFalse(detector.last_diagnostics["reference_applied"])
                self.assertEqual(detector.last_diagnostics["candidates_before_cleanup"], 26)
                self.assertGreater(result.candidates[0].area_px, 900)

    def test_distinct_artwork_in_one_cell_is_preserved_for_review(self):
        grid = PanelGrid.regular(600, 400, 4, 4, confidence=.95, source="visual")
        first = MotifCandidate((30, 50), (20, 40, 20, 20), .8, 400)
        second = MotifCandidate((120, 50), (110, 40, 20, 20), .8, 400)
        result = _consolidate_grid_candidates((first, second), grid)
        self.assertEqual(len(result), 2)
        self.assertEqual({c.bounding_box_px for c in result}, {first.bounding_box_px, second.bounding_box_px})

    def test_fabric_extent_does_not_discard_unexplained_edge_artwork(self):
        grid = PanelGrid.regular(600, 400, 4, 4, bounds_px=(50, 50, 450, 350),
                                 confidence=.95, source="fabric")
        edge = MotifCandidate((500, 100), (485, 85, 30, 30), .8, 700)
        result = _consolidate_grid_candidates((edge,), grid)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].bounding_box_px, edge.bounding_box_px)
        self.assertEqual(result[0].center_px, edge.center_px)
        self.assertIn("Artwork outside the proposed printed grid", result[0].review_reasons)

    def test_bright_fabric_mask_rejects_ambiguous_and_full_frame_inputs(self):
        for image in (np.full((400, 600, 3), 230, np.uint8),
                      np.full((400, 600, 3), 20, np.uint8),
                      printed_fabric(6, 4)[20:-20, 20:-20]):
            with self.subTest(shape=image.shape):
                self.assertIsNone(locate_bright_fabric(image).mask)

    def test_bright_fabric_keeps_dark_motifs_and_excludes_disconnected_bed_marks(self):
        image = printed_fabric(6, 4, panels=False)
        cv2.rectangle(image, (1, 80), (14, 130), (180, 180, 180), -1)
        cv2.rectangle(image, (746, 200), (757, 255), (180, 180, 180), -1)
        mask = locate_bright_fabric(image).mask
        self.assertIsNotNone(mask)
        self.assertEqual(mask[100, 6], 0)
        self.assertEqual(mask[225, 752], 0)
        self.assertEqual(mask[105, 105], 255)
        result = MotifDetector().detect_with_layout(image, DetectorSettings(minimum_area_px=150))
        self.assertEqual(len(result.candidates), 24)
        self.assertEqual((result.panel_grid.columns, result.panel_grid.rows), (6, 4))

    def test_fallback_does_not_drop_a_second_piece_of_fabric(self):
        image = np.full((500, 800, 3), 20, np.uint8)
        image[30:470, 30:450] = 230
        image[100:400, 500:760] = 220
        self.assertIsNone(locate_bright_fabric(image).mask)

    def test_blank_cloth_margin_does_not_generate_an_unseen_outer_row(self):
        image = printed_fabric(6, 4, panels=False, missing=tuple((c, 3) for c in range(6)))
        result = MotifDetector().detect_with_layout(image, DetectorSettings(minimum_area_px=150))
        self.assertEqual((result.panel_grid.columns, result.panel_grid.rows), (6, 3))
        self.assertEqual(len(result.candidates), 18)

    def test_manual_panel_mode_is_not_overridden_by_automatic_alternative(self):
        image = printed_fabric(6, 4, panels=False)
        manual = PanelGrid.regular(760, 540, 4, 4, confidence=1, source="manual")
        with patch("app.imaging.detector.infer_panel_grid", return_value=manual):
            result = MotifDetector().detect_with_layout(image, DetectorSettings(layout_mode="panels"))
        self.assertEqual(result.panel_grid, manual)

    def test_weak_geometry_never_enables_consolidation(self):
        grid = PanelGrid.regular(600, 400, 6, 4, confidence=.70, source="visual")
        candidates = (MotifCandidate((100, 100), (85, 85, 30, 30), .8, 600),
                      MotifCandidate((110, 100), (95, 85, 30, 30), .8, 600))
        self.assertEqual(_consolidate_grid_candidates(candidates, grid), candidates)
        self.assertEqual(len(_consolidate_grid_candidates(candidates, replace(grid, confidence=.95, source="pattern"))), 1)


if __name__ == "__main__":
    unittest.main()
