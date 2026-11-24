"""Export every enabled physical cut as SVG geometry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import LengthUnit, from_inches
from app.models import Detection, recalculate_cut_overlaps


SVG_NAMESPACE = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NAMESPACE)


def cuts_for_output(mapper: CoordinateMapper, detections: list[Detection]) -> list[Detection]:
    """Return checked cuts within the bed, in their display order."""
    return [
        detection for detection in detections
        if detection.enabled and detection.square_inches.is_valid(mapper.bed_width_in, mapper.bed_height_in)
    ]


@dataclass(frozen=True, slots=True)
class SVGExportResult:
    path: Path
    rectangle_count: int
    unit: LengthUnit


class SVGExporter:
    def build_tree(
        self,
        mapper: CoordinateMapper,
        detections: list[Detection],
        unit: LengthUnit = LengthUnit.INCHES,
    ) -> ET.ElementTree:
        # Panel/source issues are warnings. Rectangles outside the physical
        # machine bed are omitted, including for callers outside the UI.
        recalculate_cut_overlaps(detections)
        bed_width = from_inches(mapper.bed_width_in, unit)
        bed_height = from_inches(mapper.bed_height_in, unit)
        root = ET.Element(
            f"{{{SVG_NAMESPACE}}}svg",
            {
                "width": f"{_format_number(bed_width)}{unit.value}",
                "height": f"{_format_number(bed_height)}{unit.value}",
                "viewBox": (
                    f"0 0 {_format_number(bed_width)} "
                    f"{_format_number(bed_height)}"
                ),
            },
        )
        # Request the physical bed page without browser margins. The print
        # dialog and device driver must also use that size and 100% scaling;
        # CSS cannot enforce printer settings or camera calibration.
        style = ET.SubElement(root, f"{{{SVG_NAMESPACE}}}style")
        style.text = (f"@page {{ size: {_format_number(bed_width)}{unit.value} "
                      f"{_format_number(bed_height)}{unit.value}; margin: 0; }}")
        for detection in cuts_for_output(mapper, detections):
            square = detection.square_inches
            x = from_inches(square.x, unit)
            y = from_inches(square.y, unit)
            width = from_inches(square.width, unit)
            height = from_inches(square.height, unit)
            stroke_width = from_inches(0.001, unit)
            ET.SubElement(
                root,
                f"{{{SVG_NAMESPACE}}}rect",
                {
                    "x": _format_number(x),
                    "y": _format_number(y),
                    "width": _format_number(width),
                    "height": _format_number(height),
                    "fill": "none",
                    "stroke": "#ff0000",
                    "stroke-width": _format_number(stroke_width),
                },
            )
        return ET.ElementTree(root)

    def export(
        self,
        path: str | Path,
        mapper: CoordinateMapper,
        detections: list[Detection],
        unit: LengthUnit = LengthUnit.INCHES,
    ) -> SVGExportResult:
        output_path = Path(path)
        tree = self.build_tree(mapper, detections, unit)
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        count = len(tree.getroot().findall(f"{{{SVG_NAMESPACE}}}rect"))
        return SVGExportResult(output_path, count, unit)


def _format_number(value: float) -> str:
    return f"{value:.12f}".rstrip("0").rstrip(".") or "0"
