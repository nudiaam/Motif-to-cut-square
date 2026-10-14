"""Write optional human-readable diagnostics beside an SVG export."""

from __future__ import annotations

import json
import zipfile
import tempfile
from dataclasses import asdict
from pathlib import Path

from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import LengthUnit, from_inches
from app.models import Detection, recalculate_cut_overlaps
from app.imaging.logical_layout import LogicalLayout
from app.geometry.review_summary import review_counts


def export_debug_json(
    path: str | Path,
    mapper: CoordinateMapper,
    detections: list[Detection],
    working_unit: LengthUnit = LengthUnit.INCHES,
    export_unit: LengthUnit = LengthUnit.INCHES,
    machine_name: str = "Epilog Fusion Maker 36",
    logical_layout: LogicalLayout | None = None,
    detection_run: dict | None = None,
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
        "logical_layout": asdict(logical_layout) if logical_layout is not None else None,
        "detection_run": detection_run,
        "review_counts": review_counts(detections, mapper, logical_layout),
        "bed_in_working_units": {
            "width": from_inches(mapper.bed_width_in, working_unit),
            "height": from_inches(mapper.bed_height_in, working_unit),
            "unit": working_unit.value,
        },
        "detections": [
            {
                "id": detection.id,
                "original_center_px": detection.original_center_px,
                "bounding_box_px": detection.bounding_box_px,
                "preferred_center_px": detection.preferred_center_px,
                "layout_anchor_px": detection.layout_anchor_px,
                "layout_cell": detection.layout_cell,
                "position_source": ("manual" if detection.manual else "grid" if detection.grid_positioned else "individual"),
                "inferred": detection.inferred,
                "artwork_clipped": detection.artwork_clipped,
                "review_reasons": detection.review_reasons,
                "source_incomplete": detection.source_incomplete,
                "cut_block_reason": detection.cut_block_reason(mapper),
                "manual": detection.manual,
                "score": detection.score,
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


def export_detection_bundle(path, image, reference, mapper, detections, **kwargs):
    """Lossless inputs plus JSON. Refuse to pair a run with a different image."""
    import cv2
    from app.imaging.run_diagnostics import image_identity
    run = kwargs.get('detection_run') or {}
    identity = run.get('identity') or {}
    if identity.get('image') != image_identity(image):
        raise ValueError('Run detection on this image before saving a diagnostic package.')
    output = Path(path)
    # Keep temporary files beside the destination, with atomic final replacement.
    with tempfile.TemporaryDirectory(dir=output.parent) as directory:
        directory = Path(directory)
        report = export_debug_json(directory/'report.json', mapper, detections, **kwargs)
        archive = directory/'package.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
            bundle.write(report, 'report.json')
            ok, encoded = cv2.imencode('.png', image)
            if not ok:
                raise ValueError('Could not encode the original image.')
            bundle.writestr('source.png', encoded.tobytes())
            reference_note = 'No reference was selected for this run.'
            if identity.get('reference') is not None:
                reference_note = 'The run reference is no longer loaded; its identity is preserved in report.json.'
                if identity['reference'] == image_identity(reference):
                    ok, encoded = cv2.imencode('.png', reference)
                    if not ok:
                        raise ValueError('Could not encode the bed reference.')
                    bundle.writestr('reference.png', encoded.tobytes())
                    reference_note = 'reference.png is the exact reference selected for this run (whether matched or rejected).'
            bundle.writestr('README.txt', 'Diagnostic package. source.png preserves the original decoded pixels, without overlays.\n'
                             'report.json contains detection-time settings and the currently reviewed cuts.\n'+reference_note+'\n')
        archive.replace(output)
    return output
