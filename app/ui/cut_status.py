"""Shared status colours for canvas outlines, labels and the cut list."""

OVERLAP_COLOR = "#ff8a3d"
REVIEW_COLOR = "#ba9cff"
INVALID_COLOR = "#ff5364"
READY_COLOR = "#39d6a4"
EXCLUDED_COLOR = "#9199a3"


def cut_status_color(detection, assignment_warning=False):
    if not detection.enabled:
        return EXCLUDED_COLOR
    if detection.overlaps_cut:
        return OVERLAP_COLOR
    if not detection.valid_cut:
        return INVALID_COLOR
    if detection.artwork_clipped or detection.review_reasons or assignment_warning:
        return REVIEW_COLOR
    return READY_COLOR
