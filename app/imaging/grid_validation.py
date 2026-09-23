"""Cross-check a visual grid against independently stable artwork geometry."""
from .logical_layout import LayoutObservation, layout_from_panel_grid
from .panel_grid import PanelGrid
from .pattern_grid import RepeatedPattern


def contradicts_artwork(grid: PanelGrid, pattern: RepeatedPattern) -> bool:
    """Reject aliases/subsets only when stable artwork explains more regions.

    Raw fragments alone must not veto a panel: pale and patterned photographs
    can have many fragments even when their visual panel boundaries are right.
    The alternative has already passed multi-threshold stability checks.
    """
    observations = [LayoutObservation(i, region.center_px or (x + w / 2, y + h / 2),
                                      region.bounding_box_px, region.center_px)
                    for i, region in enumerate(pattern.regions)
                    for x, y, w, h in [region.bounding_box_px]]
    proposed = layout_from_panel_grid(observations, grid)
    alternative = layout_from_panel_grid(observations, pattern.grid)
    supported = sum(m.status == "matched" for m in alternative.matches)
    explained = sum(m.status == "matched" for m in proposed.matches)
    # Require a net gain, not merely exchanging duplicates for outliers. An
    # alternative that loses different artwork is not stronger evidence.
    return supported - explained >= max(2, supported * .15)
