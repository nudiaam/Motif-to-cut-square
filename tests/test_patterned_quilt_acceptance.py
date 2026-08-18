from __future__ import annotations

import unittest

import cv2
import numpy as np

from app.geometry.coordinate_mapper import CoordinateMapper
from app.imaging.detector import DetectorSettings, MotifDetector
from app.models import (
    Detection,
    center_cuts_on_visual_anchors,
    resolve_cut_overlaps,
)


ROWS = 4
COLUMNS = 6


def _patterned_quilt(width: int = 900, height: int = 600) -> np.ndarray:
    """Build repeatable pastel panels with textured, partly detached motifs."""
    image = np.zeros((height, width, 3), dtype=np.uint8)
    backgrounds = [
        (225, 236, 232),
        (234, 224, 238),
        (224, 234, 242),
        (236, 233, 218),
        (226, 239, 224),
        (239, 226, 226),
    ]
    motif_colors = [(42, 76, 181), (176, 66, 45), (57, 138, 72), (135, 55, 142)]
    cell_width, cell_height = width // COLUMNS, height // ROWS
    for row in range(ROWS):
        for column in range(COLUMNS):
            index = row * COLUMNS + column
            x0, y0 = column * cell_width, row * cell_height
            x1, y1 = (column + 1) * cell_width, (row + 1) * cell_height
            background = backgrounds[index % len(backgrounds)]
            cv2.rectangle(image, (x0, y0), (x1 - 1, y1 - 1), background, -1)
            pattern = tuple(max(0, channel - 10) for channel in background)
            if index % 2:
                for x in range(x0 + 8, x1, 18):
                    cv2.line(image, (x, y0), (min(x + 45, x1), y1), pattern, 2)
            else:
                for y in range(y0 + 12, y1, 24):
                    for x in range(x0 + 12, x1, 24):
                        cv2.circle(image, (x, y), 3, pattern, -1)

            center = (
                x0 + cell_width // 2 + (index % 3 - 1) * 5,
                y0 + cell_height // 2 + (index % 2) * 4,
            )
            color = motif_colors[index % len(motif_colors)]
            if index % 4 == 0:
                cv2.circle(image, center, 40, color, -1)
                cv2.circle(image, (center[0], center[1] - 48), 10, color, -1)
            elif index % 4 == 1:
                cv2.ellipse(image, center, (47, 32), -12, 0, 360, color, -1)
                cv2.circle(image, (center[0] + 40, center[1] - 30), 9, color, -1)
            elif index % 4 == 2:
                points = []
                for point_index in range(10):
                    angle = -np.pi / 2 + point_index * np.pi / 5
                    radius = 46 if point_index % 2 == 0 else 22
                    points.append(
                        (
                            int(center[0] + np.cos(angle) * radius),
                            int(center[1] + np.sin(angle) * radius),
                        )
                    )
                cv2.fillPoly(image, [np.asarray(points, np.int32)], color)
            else:
                cv2.rectangle(
                    image,
                    (center[0] - 38, center[1] - 42),
                    (center[0] + 38, center[1] + 42),
                    color,
                    -1,
                )
            for detail in range(12):
                angle = detail * 2 * np.pi / 12
                point = (
                    int(center[0] + np.cos(angle) * 23),
                    int(center[1] + np.sin(angle) * 23),
                )
                cv2.circle(image, point, 3, (220, 205, 170), -1)
    return image


def _settings(image: np.ndarray) -> DetectorSettings:
    height, width = image.shape[:2]
    return DetectorSettings(
        sensitivity=65,
        minimum_area_px=180,
        morphological_cleanup=0.25,
        merge_distance_px_x=0.35 * width / 36,
        merge_distance_px_y=0.35 * height / 24,
    )


class PatternedQuiltAcceptanceTests(unittest.TestCase):
    def test_one_motif_per_panel_survives_capture_and_file_variations(self) -> None:
        image = _patterned_quilt()
        rng = np.random.default_rng(20260818)
        gradient = np.linspace(
            0.70, 1.08, image.shape[1], dtype=np.float32
        )[None, :, None]
        encoded_ok, encoded = cv2.imencode(
            ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 60]
        )
        self.assertTrue(encoded_ok)
        variants = {
            "original": image,
            "dark": np.clip(image.astype(np.float32) * 0.62, 0, 255).astype(np.uint8),
            "uneven light": np.clip(
                image.astype(np.float32) * gradient, 0, 255
            ).astype(np.uint8),
            "blur": cv2.GaussianBlur(image, (7, 7), 1.3),
            "sensor noise": np.clip(
                image.astype(np.float32) + rng.normal(0, 4, image.shape), 0, 255
            ).astype(np.uint8),
            "JPEG quality 60": cv2.imdecode(encoded, cv2.IMREAD_COLOR),
        }
        expected_cells = {
            (column, row)
            for row in range(ROWS)
            for column in range(COLUMNS)
        }

        for name, variant in variants.items():
            with self.subTest(name=name):
                candidates = MotifDetector().detect(variant, _settings(variant))
                cells = {
                    (
                        int(candidate.center_px[0] * COLUMNS / variant.shape[1]),
                        int(candidate.center_px[1] * ROWS / variant.shape[0]),
                    )
                    for candidate in candidates
                }
                self.assertEqual(len(candidates), ROWS * COLUMNS)
                self.assertEqual(cells, expected_cells)
                mapper = CoordinateMapper(
                    variant.shape[1], variant.shape[0]
                )
                detections = [
                    Detection.from_pixel_center(
                        index,
                        candidate.center_px,
                        mapper,
                        candidate.bounding_box_px,
                        candidate.score,
                    )
                    for index, candidate in enumerate(candidates, 1)
                ]
                _moved, unresolved = resolve_cut_overlaps(
                    detections, mapper
                )
                self.assertEqual(unresolved, [])
                _centered, problems = center_cuts_on_visual_anchors(
                    detections, mapper
                )
                self.assertEqual(problems, [])
                self.assertTrue(all(item.exportable for item in detections))


if __name__ == "__main__":
    unittest.main()
