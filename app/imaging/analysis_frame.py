"""Keep detector coordinates independent of irrelevant camera surround."""
from dataclasses import replace

import cv2
import numpy as np

from .panel_grid import PanelGrid


def fabric_analysis_bounds(mask: np.ndarray) -> tuple[int, int, int, int]:
    """A fixed cloth-relative surround, without altering source calibration."""
    x, y, w, h = cv2.boundingRect(mask)
    padding = max(4, round(min(w, h) * .025))
    ih, iw = mask.shape
    left, top = max(0, x-padding), max(0, y-padding)
    right, bottom = min(iw, x+w+padding), min(ih, y+h+padding)
    return left, top, right, bottom


def translate_grid(grid: PanelGrid | None, x: float, y: float) -> PanelGrid | None:
    if grid is None:
        return None
    lattice = grid.lattice
    if lattice is not None:
        origin, col, row = lattice
        lattice = ((origin[0]+x, origin[1]+y), col, row)
    projection = grid.projection
    if projection is not None:
        matrix = np.array([[1., 0., x], [0., 1., y], [0., 0., 1.]]) @ np.asarray(projection)
        projection = tuple(tuple(float(v) for v in line) for line in matrix)
    return replace(grid, x_lines_px=tuple(v+x for v in grid.x_lines_px),
                   y_lines_px=tuple(v+y for v in grid.y_lines_px),
                   lattice=lattice, projection=projection)
