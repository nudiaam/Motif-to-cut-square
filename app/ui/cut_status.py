"""One shared presentation for canvas, navigator, list and export diagnostics."""
from app.geometry.cut_presentation import (
    present_cut,OVERLAP_COLOR,REVIEW_COLOR,INVALID_COLOR,READY_COLOR,EXCLUDED_COLOR,
)


def cut_status_color(detection,assignment_warning=False,geometry_warning=False,
                     review_warning=False,*,mapper=None):
    # Old flags describe segmentation/packing evidence, not the final cut's
    # section status. Keep the signature for callers; use measured geometry.
    return present_cut(detection,mapper).color
