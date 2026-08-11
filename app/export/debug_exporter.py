"""Write optional human-readable diagnostics beside an SVG export."""

from __future__ import annotations

import json
from pathlib import Path

from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import LengthUnit, from_inches
from app.models import Detection, recalculate_cut_overlaps


def export_debug_json(
    path: str | Path,
    mapper: CoordinateMapper,
    detections: list[Detection],
    working_unit: LengthUnit = LengthUnit.INCHES,
    export_unit: LengthUnit = LengthUnit.INCHES,
    machine_name: str = "Epilog Fusion Maker 36",
) -> Path:
    output_path = Path(path)
    recalculate_cut_overlaps(detections)
    payload = {
        "bed_width_inches": mapper.bed_width_in,
        "bed_height_inches": mapper.bed_height_in,
        "image_width_px": mapper.image_width_px,
        "image_height_px": mapper.image_height_px,
        "px_per_inch_x": mapper.px_per_inch_x,
        "px_per_inch_y": mapper.px_per_inch_y,
        "image_placement_inches": {
            "x": mapper.image_x_in,
            "y": mapper.image_y_in,
            "width": mapper.image_width_in,
            "height": mapper.image_height_in,
        },
        "machine_name": machine_name,
        "working_unit": working_unit.value,
        "export_unit": export_unit.value,
        "bed_in_working_units": {
            "width": from_inches(mapper.bed_width_in, working_unit),
            "height": from_inches(mapper.bed_height_in, working_unit),
            "unit": working_unit.value,
        },
        "detections": [
            {
                "id": detection.id,
                "center_px": {
                    "x": detection.center_px[0],
                    "y": detection.center_px[1],
                },
                "center_inches": {
                    "x": detection.center_inches[0],
                    "y": detection.center_inches[1],
                },
                "square_inches": {
                    "x": detection.square_inches.x,
                    "y": detection.square_inches.y,
                    "width": detection.square_inches.width,
                    "height": detection.square_inches.height,
                },
                "square_export_units": {
                    "x": from_inches(detection.square_inches.x, export_unit),
                    "y": from_inches(detection.square_inches.y, export_unit),
                    "width": from_inches(detection.square_inches.width, export_unit),
                    "height": from_inches(detection.square_inches.height, export_unit),
                    "unit": export_unit.value,
                },
                "valid": detection.valid_cut,
                "overlaps_cut": detection.overlaps_cut,
                "exportable": detection.exportable,
                "enabled": detection.enabled,
            }
            for detection in detections
        ],
    }
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return output_path
