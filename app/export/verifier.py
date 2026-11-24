"""Reconstruct exportable SVG geometry back in image pixels."""

from __future__ import annotations

from dataclasses import dataclass
import math
import xml.etree.ElementTree as ET

from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import LengthUnit, to_inches
from app.models import Detection, recalculate_cut_overlaps
from app.export.svg_exporter import SVGExporter, SVG_NAMESPACE


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
    """Re-read serialized SVG numbers, including rectangle corners and sizes.

    This verifies the file geometry, not a receiving program or camera scale.
    """
    recalculate_cut_overlaps(detections)
    overlays: dict[int, tuple[float, float, float, float]] = {}
    max_error_x = 0.0
    max_error_y = 0.0
    enabled = [d for d in detections if d.enabled and d.square_inches.is_valid(
        mapper.bed_width_in, mapper.bed_height_in)]
    root = SVGExporter().build_tree(mapper, detections, export_unit).getroot()
    root = ET.fromstring(ET.tostring(root, encoding='utf-8'))
    page = []
    for key in ('width', 'height'):
        value = root.attrib[key]
        if not value.endswith(export_unit.value):
            raise ValueError('SVG page units differ from the selected export units')
        page.append(to_inches(float(value.removesuffix(export_unit.value)), export_unit))
    view_box = [to_inches(float(value), export_unit) for value in root.attrib['viewBox'].split()]
    expected = (mapper.bed_width_in, mapper.bed_height_in)
    if (len(view_box) != 4 or any(not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-9)
            for a, b in zip((*page, *view_box), (*expected, 0., 0., *expected)))):
        raise ValueError('SVG page size or origin differs from the machine bed')
    rectangles = root.findall(f'{{{SVG_NAMESPACE}}}rect')
    for detection, rectangle in zip(enabled, rectangles, strict=True):
        square = detection.square_inches
        reconstructed = tuple(to_inches(float(rectangle.attrib[key]), export_unit)
                              for key in ('x', 'y', 'width', 'height'))
        overlays[detection.id] = mapper.inches_rect_to_pixel(reconstructed)
        original = mapper.inches_rect_to_pixel(square.as_tuple())
        rebuilt = overlays[detection.id]
        max_error_x = max(max_error_x, abs(rebuilt[0]-original[0]),
                          abs(rebuilt[0]+rebuilt[2]-original[0]-original[2]))
        max_error_y = max(max_error_y, abs(rebuilt[1]-original[1]),
                          abs(rebuilt[1]+rebuilt[3]-original[1]-original[3]))
    return VerificationResult(overlays, max_error_x, max_error_y)
