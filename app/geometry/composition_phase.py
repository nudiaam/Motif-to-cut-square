"""Compatibility entry point: artwork cannot translate measured fabric cells."""


def contain_automatic_compositions(layout, detections, mapper, width_inches, height_inches):
    """Keep section geometry; infeasible artwork/size combinations need review.

    Retained for callers of the former phase fitting API. Automatic placement
    uses the geometric section centre, independently of artwork and cut size.
    """
    return layout
