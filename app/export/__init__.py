"""SVG, debug data, and round-trip verification."""

from .debug_exporter import export_debug_json
from .svg_exporter import SVGExporter, SVGExportResult
from .verifier import VerificationResult, verify_export_geometry

__all__ = [
    "SVGExporter",
    "SVGExportResult",
    "VerificationResult",
    "export_debug_json",
    "verify_export_geometry",
]
