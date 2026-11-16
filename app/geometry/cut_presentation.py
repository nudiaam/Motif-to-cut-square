"""User-facing cut state, independent of artwork segmentation confidence."""
from dataclasses import dataclass
import math

READY_COLOR='#39d6a4'
REVIEW_COLOR='#ba9cff'
INVALID_COLOR='#ff5364'
EXCLUDED_COLOR='#9199a3'
OVERLAP_COLOR='#ff8a3d'  # Historical diagnostic colour; not a final cut state.


@dataclass(frozen=True)
class CutPresentation:
    state: str
    color: str
    reason: str


def present_cut(detection,mapper=None):
    if not detection.enabled:
        return CutPresentation('EXCLUDED',EXCLUDED_COLOR,'Unchecked: omitted from the SVG')
    square=detection.square_inches
    impossible=(not all(math.isfinite(v) for v in square.as_tuple()) or
                square.width<=0 or square.height<=0)
    if impossible or (mapper and not square.is_valid(mapper.bed_width_in,mapper.bed_height_in)):
        return CutPresentation('IMPOSSIBLE',INVALID_COLOR,'The rectangle does not fit the machine bed')
    if mapper and detection.panel_boundary_reason(mapper):
        return CutPresentation('SECTION CROSSING',REVIEW_COLOR,
            'The cut crosses its section boundary; its centre and requested size are retained')
    return CutPresentation('READY',READY_COLOR,'No measured section crossing detected')
