"""Reconstruct exportable SVG geometry back in image pixels."""

from __future__ import annotations

from dataclasses import dataclass

from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import LengthUnit, from_inches, to_inches
from app.models import Detection, recalculate_cut_overlaps


@dataclass(frozen=True, slots=True)
class VerificationResult:
    overlay_rectangles_px: dict[int, tuple[float, float, float, float]]
    maximum_error_x_px: float
    maximum_error_y_px: float


def verify_export_geometry(
    mapper: CoordinateMapper,
    detections: list[Detection],
    export_unit: LengthUnit = LengthUnit.INCHES,
) -> VerificationResult:
    """Perform pixel -> canonical inches -> SVG units -> pixel verification."""
    recalculate_cut_overlaps(detections)
    overlays: dict[int, tuple[float, float, float, float]] = {}
    max_error_x = 0.0
    max_error_y = 0.0
    for detection in detections:
        if not detection.exportable:
            continue
        square = detection.square_inches
        exported = tuple(from_inches(value, export_unit) for value in square.as_tuple())
        reconstructed = tuple(to_inches(value, export_unit) for value in exported)
        overlays[detection.id] = mapper.inches_rect_to_pixel(reconstructed)
        exported_center = tuple(
            from_inches(value, export_unit) for value in detection.center_inches
        )
        canonical_center = tuple(
            to_inches(value, export_unit) for value in exported_center
        )
        reconstructed_center = mapper.inches_to_pixel(*canonical_center)
        max_error_x = max(max_error_x, abs(reconstructed_center[0] - detection.center_px[0]))
        max_error_y = max(max_error_y, abs(reconstructed_center[1] - detection.center_px[1]))
    return VerificationResult(overlays, max_error_x, max_error_y)
