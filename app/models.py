"""Application data models independent of the user interface."""

from __future__ import annotations

from dataclasses import dataclass

from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.cut_square import CutSquare


@dataclass(slots=True)
class Detection:
    id: int
    center_px: tuple[float, float]
    preferred_center_px: tuple[float, float]
    center_inches: tuple[float, float]
    bounding_box_px: tuple[int, int, int, int] | None
    score: float
    enabled: bool
    valid_cut: bool
    overlaps_cut: bool = False
    manual: bool = False
    cut_width_inches: float = 5.0
    cut_height_inches: float = 5.0

    @classmethod
    def from_pixel_center(
        cls,
        detection_id: int,
        center_px: tuple[float, float],
        mapper: CoordinateMapper,
        bounding_box_px: tuple[int, int, int, int] | None = None,
        score: float = 1.0,
        enabled: bool = True,
        manual: bool = False,
        cut_width_inches: float = 5.0,
        cut_height_inches: float = 5.0,
    ) -> "Detection":
        center_inches = mapper.pixel_to_inches(*center_px)
        square = CutSquare.centered_at(
            *center_inches, cut_width_inches, cut_height_inches
        )
        return cls(
            id=detection_id,
            center_px=(float(center_px[0]), float(center_px[1])),
            preferred_center_px=(float(center_px[0]), float(center_px[1])),
            center_inches=center_inches,
            bounding_box_px=bounding_box_px,
            score=float(max(0.0, min(1.0, score))),
            enabled=enabled,
            valid_cut=square.is_valid(mapper.bed_width_in, mapper.bed_height_in),
            manual=manual,
            cut_width_inches=cut_width_inches,
            cut_height_inches=cut_height_inches,
        )

    @property
    def square_inches(self) -> CutSquare:
        return CutSquare.centered_at(
            *self.center_inches, self.cut_width_inches, self.cut_height_inches
        )

    @property
    def exportable(self) -> bool:
        """Whether this cut is enabled, inside the bed, and collision-free."""
        return self.enabled and self.valid_cut and not self.overlaps_cut

    def set_cut_size(
        self, width_inches: float, height_inches: float, mapper: CoordinateMapper
    ) -> None:
        self.cut_width_inches = float(width_inches)
        self.cut_height_inches = float(height_inches)
        self._update_validity(mapper)

    def recalculate_for_mapper(self, mapper: CoordinateMapper) -> None:
        self.center_inches = mapper.pixel_to_inches(*self.center_px)
        self._update_validity(mapper)

    def move_to_pixel(
        self, center_px: tuple[float, float], mapper: CoordinateMapper
    ) -> None:
        clamped_x = min(max(float(center_px[0]), 0.0), float(mapper.image_width_px))
        clamped_y = min(max(float(center_px[1]), 0.0), float(mapper.image_height_px))
        self.center_px = clamped_x, clamped_y
        self.preferred_center_px = self.center_px
        self.center_inches = mapper.pixel_to_inches(clamped_x, clamped_y)
        self._update_validity(mapper)
        self.manual = True

    def move_to_inches(
        self,
        center_inches: tuple[float, float],
        mapper: CoordinateMapper,
        preserve_preferred_center: bool = False,
    ) -> None:
        """Move a cut in bed coordinates and keep its image coordinates in sync."""
        self.center_inches = float(center_inches[0]), float(center_inches[1])
        self.center_px = mapper.inches_to_pixel(*self.center_inches)
        if not preserve_preferred_center:
            self.preferred_center_px = self.center_px
            self.manual = True
        self._update_validity(mapper)

    def _update_validity(self, mapper: CoordinateMapper) -> None:
        self.valid_cut = self.square_inches.is_valid(
            mapper.bed_width_in, mapper.bed_height_in
        )


def recalculate_cut_overlaps(
    detections: list[Detection], tolerance: float = 1e-9
) -> None:
    """Mark enabled cut rectangles that touch or overlap one another."""
    for detection in detections:
        detection.overlaps_cut = False

    enabled = [detection for detection in detections if detection.enabled]
    for index, first in enumerate(enabled):
        first_square = first.square_inches
        for second in enabled[index + 1 :]:
            second_square = second.square_inches
            separated = (
                first_square.x + first_square.width < second_square.x - tolerance
                or second_square.x + second_square.width < first_square.x - tolerance
                or first_square.y + first_square.height < second_square.y - tolerance
                or second_square.y + second_square.height < first_square.y - tolerance
            )
            if not separated:
                first.overlaps_cut = True
                second.overlaps_cut = True


def resolve_cut_overlaps(
    detections: list[Detection],
    mapper: CoordinateMapper,
    clearance_inches: float = 0.01,
) -> tuple[list[int], list[int]]:
    """Separate collisions while keeping every cut close to its visual centre.

    Each detection retains a preferred image centre. Colliding pairs share the
    minimum separation movement whenever possible, avoiding the arbitrary result
    of pinning one cut and moving the other by the entire overlap. Collision-free
    cuts remain fixed. Sizes and enabled states are never changed.
    """
    recalculate_cut_overlaps(detections)
    conflicting = [
        detection
        for detection in detections
        if detection.enabled and detection.valid_cut and detection.overlaps_cut
    ]
    if not conflicting:
        return [], []

    movable_ids = {detection.id for detection in conflicting}
    preferred_centres: dict[int, tuple[float, float]] = {}
    for detection in conflicting:
        preferred = mapper.pixel_to_inches(*detection.preferred_center_px)
        preferred = _clamp_center_to_bed(preferred, detection, mapper)
        preferred_centres[detection.id] = preferred
        detection.move_to_inches(
            preferred, mapper, preserve_preferred_center=True
        )

    active = [
        detection
        for detection in detections
        if detection.enabled and detection.valid_cut
    ]
    maximum_passes = max(100, len(active) * len(active) * 20)
    for _pass in range(maximum_passes):
        changed = False
        for index, first in enumerate(active):
            for second in active[index + 1 :]:
                if (
                    first.id not in movable_ids
                    and second.id not in movable_ids
                ):
                    continue
                if not _cut_rectangles_collide(
                    first.square_inches, second.square_inches
                ):
                    continue
                plans = [
                    plan
                    for axis in (0, 1)
                    if (
                        plan := _axis_separation_plan(
                            first,
                            second,
                            axis,
                            movable_ids,
                            preferred_centres,
                            mapper,
                            clearance_inches,
                        )
                    )
                    is not None
                ]
                if not plans:
                    continue
                _cost, first_center, second_center = min(
                    plans, key=lambda plan: plan[0]
                )
                if first_center != first.center_inches:
                    first.move_to_inches(
                        first_center, mapper, preserve_preferred_center=True
                    )
                    changed = True
                if second_center != second.center_inches:
                    second.move_to_inches(
                        second_center, mapper, preserve_preferred_center=True
                    )
                    changed = True
        recalculate_cut_overlaps(detections)
        if not any(
            detection.overlaps_cut and detection.id in movable_ids
            for detection in detections
        ):
            break
        if not changed:
            break

    recalculate_cut_overlaps(detections)
    moved_ids = [
        detection.id
        for detection in conflicting
        if _distance_squared(
            detection.center_inches, preferred_centres[detection.id]
        )
        > 1e-12
    ]
    unresolved_ids = [
        detection.id
        for detection in detections
        if detection.enabled and detection.overlaps_cut
    ]
    return moved_ids, unresolved_ids


def _axis_separation_plan(
    first: Detection,
    second: Detection,
    axis: int,
    movable_ids: set[int],
    preferred_centres: dict[int, tuple[float, float]],
    mapper: CoordinateMapper,
    clearance_inches: float,
) -> tuple[
    float, tuple[float, float], tuple[float, float]
] | None:
    """Find the lowest-anchor-error separation plan along one axis."""
    first_center = first.center_inches
    second_center = second.center_inches
    first_half = (
        first.cut_width_inches / 2.0
        if axis == 0
        else first.cut_height_inches / 2.0
    )
    second_half = (
        second.cut_width_inches / 2.0
        if axis == 0
        else second.cut_height_inches / 2.0
    )
    distance = second_center[axis] - first_center[axis]
    natural_direction = 1.0 if distance >= 0.0 else -1.0
    if abs(distance) <= 1e-12:
        preferred_delta = (
            preferred_centres.get(second.id, second_center)[axis]
            - preferred_centres.get(first.id, first_center)[axis]
        )
        if abs(preferred_delta) > 1e-12:
            natural_direction = 1.0 if preferred_delta > 0.0 else -1.0
        else:
            natural_direction = 1.0 if second.id > first.id else -1.0

    plans = []
    for direction in (natural_direction, -natural_direction):
        current_signed_distance = direction * distance
        required = (
            first_half
            + second_half
            + clearance_inches
            - current_signed_distance
        )
        if required <= 0.0:
            continue
        first_direction = -direction
        second_direction = direction
        first_available = (
            _available_axis_movement(first, axis, first_direction, mapper)
            if first.id in movable_ids
            else 0.0
        )
        second_available = (
            _available_axis_movement(second, axis, second_direction, mapper)
            if second.id in movable_ids
            else 0.0
        )
        split = _minimum_squared_split(
            required, first_available, second_available
        )
        if split is None:
            continue
        first_movement, second_movement = split
        new_first = list(first_center)
        new_second = list(second_center)
        new_first[axis] += first_direction * first_movement
        new_second[axis] += second_direction * second_movement
        first_result = (new_first[0], new_first[1])
        second_result = (new_second[0], new_second[1])
        anchor_cost = 0.0
        if first.id in movable_ids:
            anchor_cost += _distance_squared(
                first_result, preferred_centres[first.id]
            )
        if second.id in movable_ids:
            anchor_cost += _distance_squared(
                second_result, preferred_centres[second.id]
            )
        plans.append((anchor_cost, first_result, second_result))
    return min(plans, key=lambda plan: plan[0]) if plans else None


def _minimum_squared_split(
    required: float, first_available: float, second_available: float
) -> tuple[float, float] | None:
    """Split movement as evenly as bounds allow to minimise squared distance."""
    if first_available + second_available + 1e-12 < required:
        return None
    first = min(required / 2.0, first_available)
    second = min(required / 2.0, second_available)
    remaining = max(0.0, required - first - second)
    if remaining:
        first_extra = min(remaining, first_available - first)
        first += first_extra
        remaining -= first_extra
    if remaining:
        second_extra = min(remaining, second_available - second)
        second += second_extra
        remaining -= second_extra
    return (first, second) if remaining <= 1e-9 else None


def _available_axis_movement(
    detection: Detection,
    axis: int,
    direction: float,
    mapper: CoordinateMapper,
) -> float:
    half_size = (
        detection.cut_width_inches / 2.0
        if axis == 0
        else detection.cut_height_inches / 2.0
    )
    bed_size = mapper.bed_width_in if axis == 0 else mapper.bed_height_in
    position = detection.center_inches[axis]
    return (
        max(0.0, bed_size - half_size - position)
        if direction > 0.0
        else max(0.0, position - half_size)
    )


def _clamp_center_to_bed(
    center: tuple[float, float],
    detection: Detection,
    mapper: CoordinateMapper,
) -> tuple[float, float]:
    half_width = detection.cut_width_inches / 2.0
    half_height = detection.cut_height_inches / 2.0
    return (
        min(max(center[0], half_width), mapper.bed_width_in - half_width),
        min(max(center[1], half_height), mapper.bed_height_in - half_height),
    )


def _distance_squared(
    first: tuple[float, float], second: tuple[float, float]
) -> float:
    return (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2


def _cut_rectangles_collide(
    first: CutSquare, second: CutSquare, tolerance: float = 1e-9
) -> bool:
    """Return true when two cuts overlap or touch, matching export validation."""
    return not (
        first.x + first.width < second.x - tolerance
        or second.x + second.width < first.x - tolerance
        or first.y + first.height < second.y - tolerance
        or second.y + second.height < first.y - tolerance
    )
