"""Application data models independent of the user interface."""

from __future__ import annotations

from dataclasses import dataclass

from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.cut_square import CutSquare


@dataclass(slots=True)
class Detection:
    id: int
    center_px: tuple[float, float]
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
        self.center_inches = mapper.pixel_to_inches(clamped_x, clamped_y)
        self._update_validity(mapper)
        self.manual = True

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
