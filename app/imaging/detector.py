"""Classical OpenCV motif detection for the prototype."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class DetectorSettings:
    sensitivity: int = 65
    minimum_area_px: int = 500
    morphological_cleanup: float = 0.25
    merge_distance_px_x: float = 14.0
    merge_distance_px_y: float = 14.0


@dataclass(frozen=True, slots=True)
class MotifCandidate:
    center_px: tuple[float, float]
    bounding_box_px: tuple[int, int, int, int]
    score: float
    area_px: int


@dataclass(frozen=True, slots=True)
class _RawComponent:
    bounding_box_px: tuple[int, int, int, int]
    center_px: tuple[float, float]
    area_px: int
    contrast: float


class MotifDetector:
    """Locate visually distinct connected regions without classifying them."""

    def detect(
        self, image_bgr: np.ndarray, settings: DetectorSettings
    ) -> list[MotifCandidate]:
        self._validate_image(image_bgr)
        sensitivity = int(np.clip(settings.sensitivity, 0, 100))
        cleanup = float(np.clip(settings.morphological_cleanup, 0.0, 1.0))

        lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        background_lab = self._estimate_background(lab)

        # Color distance is intentionally generic: the detector asks only whether
        # a region differs from the dominant border/fabric color.
        delta = lab - background_lab.reshape(1, 1, 3)
        distance = np.sqrt(
            0.35 * np.square(delta[:, :, 0])
            + np.square(delta[:, :, 1])
            + np.square(delta[:, :, 2])
        )
        distance_u8 = np.clip(distance, 0, 255).astype(np.uint8)
        distance_u8 = cv2.GaussianBlur(distance_u8, (5, 5), 0)

        threshold = int(round(np.interp(sensitivity, [0, 100], [70, 12])))
        _, mask = cv2.threshold(distance_u8, threshold, 255, cv2.THRESH_BINARY)

        if cleanup > 0:
            open_size = _odd_size(1.0 + cleanup * 12.0)
            close_size = _odd_size(3.0 + cleanup * 32.0)
            open_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (open_size, open_size)
            )
            close_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (close_size, close_size)
            )
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)

        candidates = self._components(
            mask,
            distance,
            max(1, int(settings.minimum_area_px)),
            image_bgr.shape[1] * image_bgr.shape[0],
            threshold,
            max(0.0, float(settings.merge_distance_px_x)),
            max(0.0, float(settings.merge_distance_px_y)),
        )
        return sorted(candidates, key=lambda item: (item.center_px[1], item.center_px[0]))

    @staticmethod
    def _validate_image(image_bgr: np.ndarray) -> None:
        if not isinstance(image_bgr, np.ndarray):
            raise TypeError("image_bgr must be a NumPy array")
        if image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
            raise ValueError("image_bgr must have shape (height, width, 3)")
        if image_bgr.size == 0:
            raise ValueError("image_bgr cannot be empty")

    @staticmethod
    def _estimate_background(lab: np.ndarray) -> np.ndarray:
        height, width = lab.shape[:2]
        border = max(3, int(round(min(height, width) * 0.04)))
        samples = np.concatenate(
            (
                lab[:border].reshape(-1, 3),
                lab[-border:].reshape(-1, 3),
                lab[:, :border].reshape(-1, 3),
                lab[:, -border:].reshape(-1, 3),
            ),
            axis=0,
        )
        return np.median(samples, axis=0)

    @staticmethod
    def _components(
        mask: np.ndarray,
        distance: np.ndarray,
        minimum_area_px: int,
        total_area_px: int,
        threshold: int,
        merge_distance_px_x: float,
        merge_distance_px_y: float,
    ) -> list[MotifCandidate]:
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask, connectivity=8
        )
        components: list[_RawComponent] = []
        maximum_area = total_area_px * 0.30
        fragment_floor = max(4, int(round(minimum_area_px * 0.04)))
        for label in range(1, count):
            x, y, width, height, area = (int(value) for value in stats[label])
            if area < fragment_floor or area > maximum_area:
                continue
            component_values = distance[labels == label]
            contrast = float(component_values.mean()) if component_values.size else 0.0
            components.append(
                _RawComponent(
                    (x, y, width, height),
                    (float(centroids[label][0]), float(centroids[label][1])),
                    area,
                    contrast,
                )
            )

        groups = _group_nearby_components(
            components, merge_distance_px_x, merge_distance_px_y
        )
        result: list[MotifCandidate] = []
        for group in groups:
            area = sum(item.area_px for item in group)
            if area < minimum_area_px or area > maximum_area:
                continue
            x = min(item.bounding_box_px[0] for item in group)
            y = min(item.bounding_box_px[1] for item in group)
            right = max(
                item.bounding_box_px[0] + item.bounding_box_px[2] for item in group
            )
            bottom = max(
                item.bounding_box_px[1] + item.bounding_box_px[3] for item in group
            )
            center = (
                sum(item.center_px[0] * item.area_px for item in group) / area,
                sum(item.center_px[1] * item.area_px for item in group) / area,
            )
            contrast = sum(item.contrast * item.area_px for item in group) / area
            contrast_score = np.clip((contrast - threshold) / 80.0, 0.0, 1.0)
            area_score = np.clip(area / max(minimum_area_px * 8.0, 1.0), 0.0, 1.0)
            score = float(0.72 * contrast_score + 0.28 * area_score)
            result.append(
                MotifCandidate(center, (x, y, right - x, bottom - y), score, area)
            )
        return result


def _odd_size(value: float) -> int:
    rounded = max(1, int(round(value)))
    return rounded if rounded % 2 == 1 else rounded + 1


def _group_nearby_components(
    components: list[_RawComponent],
    merge_distance_px_x: float,
    merge_distance_px_y: float,
) -> list[list[_RawComponent]]:
    """Union fragments whose bounding boxes are close in calibrated X/Y pixels."""
    if not components:
        return []
    parents = list(range(len(components)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(first: int, second: int) -> None:
        root_first, root_second = find(first), find(second)
        if root_first != root_second:
            parents[root_second] = root_first

    for first in range(len(components)):
        for second in range(first + 1, len(components)):
            gap_x, gap_y = _bounding_box_gap(
                components[first].bounding_box_px,
                components[second].bounding_box_px,
            )
            if gap_x == 0.0 and gap_y == 0.0:
                union(first, second)
                continue
            if merge_distance_px_x <= 0.0 or merge_distance_px_y <= 0.0:
                continue
            normalized_distance = (
                (gap_x / merge_distance_px_x) ** 2
                + (gap_y / merge_distance_px_y) ** 2
            )
            if normalized_distance <= 1.0:
                union(first, second)

    grouped: dict[int, list[_RawComponent]] = {}
    for index, component in enumerate(components):
        grouped.setdefault(find(index), []).append(component)
    return list(grouped.values())


def _bounding_box_gap(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int]
) -> tuple[float, float]:
    first_x, first_y, first_width, first_height = first
    second_x, second_y, second_width, second_height = second
    gap_x = max(
        first_x - (second_x + second_width),
        second_x - (first_x + first_width),
        0,
    )
    gap_y = max(
        first_y - (second_y + second_height),
        second_y - (first_y + first_height),
        0,
    )
    return float(gap_x), float(gap_y)
