from __future__ import annotations

import unittest
import copy
import json
import tempfile
from pathlib import Path

import numpy as np
import cv2

from app.imaging.logical_layout import LayoutObservation, fit_logical_layout
from app.imaging.detector import MotifDetector, DetectorSettings
from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import LengthUnit
from app.models import Detection, apply_logical_layout, center_cuts_on_visual_anchors, resolve_cut_overlaps
from app.export.debug_exporter import export_debug_json
from app.export.svg_exporter import SVGExporter, SVG_NAMESPACE
from app.export.verifier import verify_export_geometry


def observations(columns=5, rows=4, missing=(), noise=0.0, rotation=0.0, shear=0.0):
    rng = np.random.default_rng(19)
    angle = np.deg2rad(rotation)
    basis = np.array([[np.cos(angle), -np.sin(angle) + shear],
                      [np.sin(angle), np.cos(angle)]])
    result = []
    for row in range(rows):
        for column in range(columns):
            if (column, row) in missing:
                continue
            center = np.array([130., 120.]) + basis @ [150. * column, 140. * row]
            center += rng.normal(0, noise, 2)
            result.append(LayoutObservation(row * columns + column + 1, tuple(center)))
    return result


class LogicalLayoutTests(unittest.TestCase):
    def test_real_detector_on_uniform_fabric_needs_no_visible_panel_lines(self):
        image = np.full((650, 900, 3), (232, 240, 241), dtype=np.uint8)
        for observation in observations(missing=((2, 2),)):
            center = tuple(int(v) for v in observation.center_px)
            cv2.ellipse(image, center, (44 if observation.detection_id % 2 else 27, 27),
                        0, 0, 360, (77, 125, 202), -1)
        result = MotifDetector().detect_with_layout(image, DetectorSettings())
        self.assertEqual(len(result.candidates), 19)
        self.assertEqual(result.panel_grid.source, "pattern")
        original = result.candidates
        data = []
        for i, candidate in enumerate(result.candidates):
            x, y, width, height = candidate.bounding_box_px
            data.append(LayoutObservation(i, (x + width / 2, y + height / 2)))
        layout = fit_logical_layout(data)
        self.assertEqual((layout.columns, layout.rows), (5, 4))
        self.assertTrue(layout.reliable)
        self.assertEqual([(p.column, p.row) for p in layout.missing], [(2, 2)])
        self.assertEqual(result.candidates, original)

    def test_auto_dimensions_rotation_shear_and_noise(self):
        for columns, rows, angle, shear in [(5, 4, 0, 0), (4, 6, 8, 0), (8, 3, -7, .08)]:
            with self.subTest(columns=columns, angle=angle):
                result = fit_logical_layout(observations(columns, rows, noise=2, rotation=angle, shear=shear))
                self.assertTrue(result.reliable, result)
                self.assertEqual((result.columns, result.rows), (columns, rows))
                self.assertTrue(all(match.status == "matched" for match in result.matches))
                self.assertLess(result.mean_residual_px, 4)

    def test_shape_dependent_centres_missing_cell_and_outliers_keep_consensus(self):
        """BBox-centre variation must not count as a broken panel geometry."""
        rng = np.random.default_rng(42)
        angle = np.deg2rad(5.0)
        basis = np.array([
            [150.0 * np.cos(angle), -140.0 * np.sin(angle) + 10.0],
            [150.0 * np.sin(angle), 140.0 * np.cos(angle)],
        ])
        data = []
        detection_id = 1
        for row in range(4):
            for column in range(6):
                if (column, row) == (2, 1):
                    continue
                centre = np.array([160.0, 140.0]) + basis @ [column, row]
                # Represents different illustration silhouettes moving the
                # bounding-box centre within an otherwise regular cell.
                centre += rng.uniform(-15.0, 15.0, 2)
                data.append(LayoutObservation(detection_id, tuple(centre)))
                detection_id += 1
        for index in range(5):
            data.append(LayoutObservation(100 + index, tuple(rng.uniform([0, 0], [1100, 800]))))

        result = fit_logical_layout(data)

        self.assertTrue(result.reliable, result)
        self.assertEqual((result.columns, result.rows), (6, 4))
        self.assertEqual([(item.column, item.row) for item in result.missing], [(2, 1)])
        self.assertEqual(sum(match.status == "matched" for match in result.matches), 23)
        self.assertGreaterEqual(sum(match.status == "outlier" for match in result.matches), 4)

    def test_larger_bbox_centre_offsets_remain_assignable_without_lowering_reliability_gate(self):
        rng = np.random.default_rng(7)
        data = observations(6, 4, rotation=7.0, shear=0.06)
        varied = []
        for item in data:
            offset = rng.uniform(-22.0, 22.0, 2)
            varied.append(LayoutObservation(item.detection_id, tuple(np.asarray(item.center_px) + offset)))

        result = fit_logical_layout(varied)

        self.assertEqual(result.reliable, result.confidence >= 0.78)
        self.assertTrue(result.reliable, result)
        self.assertEqual((result.columns, result.rows), (6, 4))
        self.assertEqual(sum(match.status == "matched" for match in result.matches), 24)

    def test_missing_is_explicit_and_outlier_cannot_extend_grid(self):
        data = observations(missing=((2, 2),), rotation=6)
        data.append(LayoutObservation(80, (1050., 900.)))
        result = fit_logical_layout(data)
        self.assertTrue(result.reliable, result)
        self.assertEqual((result.columns, result.rows), (5, 4))
        self.assertEqual([(p.column, p.row, p.source) for p in result.missing], [(2, 2, "inferred")])
        self.assertEqual(result.matches[-1].status, "outlier")

    def test_duplicate_has_no_second_assignment(self):
        data = observations()
        data.append(LayoutObservation(80, (132., 121.)))
        result = fit_logical_layout(data)
        self.assertTrue(result.reliable)
        self.assertEqual(sum(m.status == "matched" for m in result.matches), 20)
        self.assertEqual(result.matches[-1].status, "duplicate")

    def test_sparse_irregular_and_single_line_do_not_authorize_correction(self):
        rng = np.random.default_rng(7)
        cases = [observations(2, 2), observations(8, 1), observations(1, 8),
                 [LayoutObservation(i, tuple(p)) for i, p in enumerate(rng.uniform(0, 800, (20, 2)))],
                 observations(missing=((1, 1), (2, 2), (3, 1), (3, 3), (0, 2), (4, 0), (0, 0))) ]
        for data in cases:
            with self.subTest(count=len(data)):
                result = fit_logical_layout(data)
                self.assertFalse(result.reliable, result)
                self.assertTrue(all(p.review_state == "pending" for p in result.missing))

    def test_unassignable_outlier_does_not_acquire_a_grid_cut(self):
        data = observations()
        data[7] = LayoutObservation(8, (470., 298.))
        result = fit_logical_layout(data)
        self.assertTrue(result.reliable)
        match = result.matches[7]
        self.assertEqual(match.status, "outlier")
        self.assertIsNone(match.proposed_px)

    def test_missing_entire_row_is_not_invented_without_row_evidence(self):
        result = fit_logical_layout(observations(missing=tuple((c, 2) for c in range(5))))
        self.assertEqual((result.columns, result.rows), (5, 4))
        self.assertEqual(len(result.missing), 5)
        self.assertTrue(all(p.review_state == "pending" for p in result.missing))

    def test_one_aligned_outer_detection_confirms_the_next_row(self):
        missing = tuple((column, 3) for column in range(6) if column != 2)
        result = fit_logical_layout(observations(6, 4, missing=missing, noise=2, rotation=4))

        self.assertTrue(result.reliable, result)
        self.assertEqual((result.columns, result.rows), (6, 4))
        self.assertEqual(sum(match.status == "matched" for match in result.matches), 19)
        self.assertEqual([(gap.column, gap.row) for gap in result.missing],
                         [(0, 3), (1, 3), (3, 3), (4, 3), (5, 3)])
        self.assertTrue(all(gap.review_state == "pending" for gap in result.missing))

    def test_robust_edge_anchor_can_extend_grid_without_refitting_the_core(self):
        core = observations(6, 3)
        expected = (130.0 + 2 * 150.0, 120.0 + 3 * 140.0)
        # A long one-sided detail shifts the complete bounding-box centre by
        # more than the global consensus permits.  Its trimmed centre may
        # confirm the adjacent row, but must not alter any fitted grid line.
        shifted = (expected[0] + 58.0, expected[1])
        data = core + [LayoutObservation(
            90, shifted, (int(shifted[0] - 90), int(shifted[1] - 45), 180, 90), expected,
        )]

        without_hint = fit_logical_layout(core + [LayoutObservation(90, shifted)])
        result = fit_logical_layout(data)

        self.assertEqual((without_hint.columns, without_hint.rows), (6, 3))
        self.assertTrue(result.reliable, result)
        self.assertEqual((result.columns, result.rows), (6, 4))
        self.assertEqual(sum(match.status == "matched" for match in result.matches), 19)
        np.testing.assert_allclose(result.position(0, 0), without_hint.position(0, 0))
        np.testing.assert_allclose(result.column_vector_px, without_hint.column_vector_px)
        np.testing.assert_allclose(result.row_vector_px, without_hint.row_vector_px)

    def test_misaligned_edge_outlier_cannot_create_a_new_row(self):
        data = observations(6, 3, noise=1.0)
        # Correct next-row height, but halfway between two columns.
        data.append(LayoutObservation(90, (130.0 + 2.5 * 150.0, 120.0 + 3 * 140.0)))
        result = fit_logical_layout(data)

        self.assertTrue(result.reliable, result)
        self.assertEqual((result.columns, result.rows), (6, 3))
        self.assertEqual(result.matches[-1].status, "outlier")


def cut_fixture(missing=()):
    mapper = CoordinateMapper(900, 650)
    data = observations(missing=missing)
    detections = []
    for point in data:
        x, y = point.center_px
        if point.detection_id == 8:
            x += 10
            y -= 3
        width = 90 if point.detection_id % 2 else 50
        box = (int(x - width / 2), int(y - 30), width, 60)
        detections.append(Detection.from_pixel_center(point.detection_id, (x, y), mapper, box, .9))
    layout = fit_logical_layout([LayoutObservation(d.id, d.artwork_center_px()) for d in detections])
    return mapper, detections, layout


class LayoutCutIntegrationTests(unittest.TestCase):
    def test_exact_grid_centres_preserve_observations_size_and_export_round_trip(self):
        mapper, detections, layout = cut_fixture(missing=((2, 2),))
        original = copy.deepcopy(detections)
        moved, blocked = apply_logical_layout(detections, mapper, layout)
        self.assertIn(8, moved)
        self.assertEqual(blocked, [])
        self.assertEqual(len(detections), 19)
        self.assertEqual(len(layout.missing), 1)
        for before, after in zip(original, detections):
            self.assertEqual(before.bounding_box_px, after.bounding_box_px)
            self.assertEqual(before.original_center_px, after.original_center_px)
            self.assertEqual(before.preferred_center_px, after.preferred_center_px)
            self.assertEqual((before.score, before.enabled, before.manual), (after.score, after.enabled, after.manual))
            self.assertEqual((after.square_inches.width, after.square_inches.height), (5., 5.))
            self.assertTrue(after.valid_cut)
            self.assertFalse(after.overlaps_cut)
            self.assertEqual(after.center_px, layout.position(*after.layout_cell))
        accepted = [d.center_px for d in detections]
        center_cuts_on_visual_anchors(detections, mapper)
        for actual, expected in zip(detections, accepted):
            np.testing.assert_allclose(actual.center_px, expected)
        for unit in LengthUnit:
            check = verify_export_geometry(mapper, detections, unit)
            self.assertLess(check.maximum_error_x_px, 1e-8)
            self.assertLess(check.maximum_error_y_px, 1e-8)
            tree = SVGExporter().build_tree(mapper, detections, unit)
            self.assertEqual(len(tree.findall(f"{{{SVG_NAMESPACE}}}rect")), 19)
        with tempfile.TemporaryDirectory() as directory:
            path = export_debug_json(Path(directory) / "layout.json", mapper, detections, logical_layout=layout)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["logical_layout"]["missing"][0]["source"], "inferred")
            self.assertEqual(len(payload["detections"]), 19)
            self.assertIn("original_center_px", payload["detections"][0])

    def test_low_confidence_does_not_change_any_cut(self):
        mapper, detections, _ = cut_fixture()
        before = copy.deepcopy(detections)
        layout = fit_logical_layout(observations(2, 2))
        self.assertEqual(apply_logical_layout(detections, mapper, layout), ([], []))
        self.assertEqual(detections, before)

    def test_manual_and_disabled_preserved_but_oversized_artwork_cannot_override_grid(self):
        mapper, detections, layout = cut_fixture()
        detections[0].move_to_pixel((120., 115.), mapper)
        detections[1].enabled = False
        detections[2].bounding_box_px = (350, 75, 200, 80)
        untouched = copy.deepcopy(detections[:3])
        moved, blocked = apply_logical_layout(detections, mapper, layout)
        self.assertNotIn(1, moved)
        self.assertNotIn(2, moved)
        self.assertNotIn(3, blocked)
        self.assertEqual(detections[2].center_px, layout.position(2, 0))
        self.assertTrue(detections[2].artwork_clipped)
        self.assertTrue(detections[2].exportable)
        for before, after in zip(untouched[:2], detections[:2]):
            self.assertEqual(before.center_px, after.center_px)
            self.assertIsNone(after.layout_anchor_px)

    def test_artwork_extent_does_not_limit_grid_target(self):
        mapper, detections, layout = cut_fixture()
        target = detections[7]
        # A wide illustration leaves only a small interval for safe centring.
        # The grid centre must remain exact even when part of the box is cropped.
        target.bounding_box_px = (379, 225, 122, 60)
        moved, _ = apply_logical_layout(detections, mapper, layout)
        self.assertIn(target.id, moved)
        self.assertFalse(target.contains_artwork(mapper))
        self.assertTrue(target.artwork_clipped)
        self.assertTrue(target.exportable)
        self.assertEqual(target.center_px, layout.position(2, 1))
        center_cuts_on_visual_anchors(detections, mapper)
        self.assertEqual(target.center_px, layout.position(2, 1))

    def test_collision_is_reported_without_deforming_grid(self):
        mapper, detections, layout = cut_fixture()
        obstacle = Detection.from_pixel_center(99, (420., 255.), mapper, manual=True)
        detections.append(obstacle)
        before = detections[7].center_px
        _, blocked = apply_logical_layout(detections, mapper, layout)
        self.assertIn(8, blocked)
        self.assertNotEqual(detections[7].center_px, before)
        self.assertEqual(detections[7].center_px, layout.position(2, 1))
        self.assertEqual(obstacle.center_px, (420., 255.))
        resolve_cut_overlaps(detections, mapper)
        center_cuts_on_visual_anchors(detections, mapper)
        for d in detections[:-1]:
            self.assertEqual(d.center_px, layout.position(*d.layout_cell))

    def test_grid_centre_outside_bed_is_reported_without_clamping(self):
        mapper = CoordinateMapper(900, 650)
        detections = [Detection.from_pixel_center(
            p.detection_id, (p.center_px[0] - 75, p.center_px[1]), mapper,
            (int(p.center_px[0] - 100), int(p.center_px[1] - 25), 50, 50),
        ) for p in observations()]
        layout = fit_logical_layout([LayoutObservation(d.id, d.artwork_center_px()) for d in detections])
        self.assertFalse(detections[0].valid_cut)
        moved, blocked = apply_logical_layout(detections, mapper, layout)
        self.assertEqual(blocked, [1, 6, 11, 16])
        self.assertFalse(detections[0].valid_cut)
        self.assertAlmostEqual(detections[0].center_inches[0], 2.2)
        self.assertEqual(detections[0].cut_width_inches, 5.0)
        center_cuts_on_visual_anchors(detections, mapper)
        self.assertEqual(detections[0].center_px, layout.position(0, 0))

    def test_existing_cut_displacement_has_no_limit_and_packing_cannot_move_grid(self):
        mapper, detections, layout = cut_fixture()
        detections[7].move_to_inches((4., 3.), mapper, preserve_preferred_center=True)
        apply_logical_layout(detections, mapper, layout)
        self.assertEqual(detections[7].center_px, layout.position(2, 1))
        for d in detections:
            d.set_cut_size(7., 7., mapper)
        expected = [d.center_px for d in detections]
        moved, problems = resolve_cut_overlaps(detections, mapper)
        self.assertEqual(moved, [])
        self.assertEqual(len(problems), 20)
        center_cuts_on_visual_anchors(detections, mapper)
        self.assertEqual([d.center_px for d in detections], expected)

    def test_rotated_sheared_grid_is_exact_after_every_geometry_action(self):
        mapper = CoordinateMapper(1100, 950)
        data = observations(6, 4, noise=3., rotation=7., shear=.03)
        detections = [Detection.from_pixel_center(p.detection_id, p.center_px, mapper,
                      (round(p.center_px[0] - 30), round(p.center_px[1] - 25), 60, 50)) for p in data]
        layout = fit_logical_layout([LayoutObservation(d.id, d.artwork_center_px()) for d in detections])
        self.assertTrue(layout.reliable)
        apply_logical_layout(detections, mapper, layout)
        resolve_cut_overlaps(detections, mapper)
        center_cuts_on_visual_anchors(detections, mapper)
        for d in detections:
            self.assertEqual(d.center_px, layout.position(*d.layout_cell))


if __name__ == "__main__":
    unittest.main()
