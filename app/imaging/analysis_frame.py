"""Keep detector coordinates independent of irrelevant camera surround."""
from dataclasses import replace

import cv2
import numpy as np

from .panel_grid import PanelGrid


def scale_grid(grid: PanelGrid | None, sx: float, sy: float) -> PanelGrid | None:
    """Scale all grid geometry, including vectors and projective translation."""
    if grid is None:
        return None
    lattice = (tuple((p[0]*sx,p[1]*sy) for p in grid.lattice)
               if grid.lattice is not None else None)
    projection = grid.projection
    if projection is not None:
        matrix = np.diag([sx,sy,1.]) @ np.asarray(projection)
        projection = tuple(tuple(float(v) for v in row) for row in matrix)
    return replace(grid,x_lines_px=tuple(x*sx for x in grid.x_lines_px),
                   y_lines_px=tuple(y*sy for y in grid.y_lines_px),
                   lattice=lattice,projection=projection)


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
