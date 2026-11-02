"""Check cell-based segmentation against independent whole-image evidence.

No expected counts or collection templates: the grid provides spacing, while
foreground surviving a stricter pass supports extensions. Spans additionally
require evidence from a pass without proximity merging.
"""
from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np

from .panel_grid import PanelGrid

if TYPE_CHECKING:
    from .detector import MotifCandidate


def restrict_grid_to_fabric(grid, candidates, mask):
    """Remove only wholly unsupported peripheral strips, never partial motifs.

    A single cloth-supported observation protects its row/column. Printed or
    partially visible source content must remain available for review.
    """
    if grid is None or mask is None or grid.source == 'manual' or not np.any(mask):
        return grid
    from .logical_layout import layout_from_panel_grid
    layout = layout_from_panel_grid([],grid)
    height,width = mask.shape
    supported = np.zeros((grid.rows,grid.columns),bool)
    for r in range(grid.rows):
        for c in range(grid.columns):
            polygon = np.asarray(layout.cell_polygon(c,r))
            points = []
            for v in np.linspace(.05,.95,7):
                for u in np.linspace(.05,.95,7):
                    points.append((1-v)*((1-u)*polygon[0]+u*polygon[1])+
                                  v*((1-u)*polygon[3]+u*polygon[2]))
            pixels = [(int(x),int(y)) for x,y in points if 0 <= x < width and 0 <= y < height]
            supported[r,c] = sum(bool(mask[y,x]) for x,y in pixels) >= 5
    for candidate in candidates:
        x,y = candidate.layout_center_px or candidate.center_px
        if not (0 <= x < width and 0 <= y < height and mask[int(y),int(x)]):
            continue
        c,r = layout.coordinates(x,y)
        c,r = int(np.floor(c+.5)),int(np.floor(r+.5))
        if 0 <= c < grid.columns and 0 <= r < grid.rows:
            supported[r,c] = True
    return _trim_unsupported_strips(grid,supported)


def _trim_unsupported_strips(grid, supported):
    """Drop only wholly unsupported outer rows/columns, keeping lattice phase.

    `supported` is a rows x columns boolean of cells with independent evidence.
    Interior lines are never removed and the grid never shrinks below 2x2.
    """
    left,top,right,bottom = 0,0,grid.columns,grid.rows
    while right-left > 2 and not supported[top:bottom,left].any(): left += 1
    while right-left > 2 and not supported[top:bottom,right-1].any(): right -= 1
    while bottom-top > 2 and not supported[top,left:right].any(): top += 1
    while bottom-top > 2 and not supported[bottom-1,left:right].any(): bottom -= 1
    if (left,top,right,bottom) == (0,0,grid.columns,grid.rows):
        return grid
    lattice = grid.lattice
    if lattice is not None:
        origin,col,row = lattice
        lattice = ((origin[0]+left*col[0]+top*row[0],origin[1]+left*col[1]+top*row[1]),col,row)
    projection = grid.projection
    if projection is not None:
        matrix = np.asarray(projection) @ np.array([[1.,0.,left],[0.,1.,top],[0.,0.,1.]])
        projection = tuple(tuple(float(v) for v in row) for row in matrix)
    return replace(grid,x_lines_px=grid.x_lines_px[left:right+1],
                   y_lines_px=grid.y_lines_px[top:bottom+1],lattice=lattice,projection=projection)


def clip_lattice_off_image(grid, image_shape):
    """Remove phantom outer bands of a regular lattice whose cells fall off frame.

    A lattice fitted to motif anchors can extrapolate a row or column past the
    photographed edge, where no real panel exists (the grey-collection seventh
    column, centred beyond the right image border). A cut placed there would run
    off the cloth onto the laser bed. Only peripheral bands whose every cell
    centre lies outside the image are dropped — a frame-independent test, so an
    uneven shadow that merely darkens real cells never removes them. Interior
    geometry is untouched and non-lattice grids keep their own boundary handling.
    """
    if grid is None or grid.lattice is None or grid.source == 'manual':
        return grid
    from .logical_layout import layout_from_panel_grid
    layout = layout_from_panel_grid([],grid)
    height,width = image_shape[:2]
    supported = np.zeros((grid.rows,grid.columns),bool)
    for r in range(grid.rows):
        for c in range(grid.columns):
            x,y = layout.position(c,r)
            supported[r,c] = 0 <= x < width and 0 <= y < height
    if supported.all():
        return grid
    return _trim_unsupported_strips(grid,supported)


def _intersection(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return max(0, min(ax+aw, bx+bw)-max(ax, bx)) * max(0, min(ay+ah, by+bh)-max(ay, by))


def _stable(candidate, strict):
    box = candidate.bounding_box_px
    for other in strict:
        other_box = other.bounding_box_px
        intersection = _intersection(box, other_box)
        union = box[2]*box[3] + other_box[2]*other_box[3] - intersection
        if intersection / max(1, union) >= .55:
            return True
    return False


def _has_stable_core(candidate, strict):
    # Pale ink contracts at the stricter threshold. It is enough for a
    # substantial core to survive; complete bounds need not remain identical.
    box = candidate.bounding_box_px
    for other in strict:
        other_box = other.bounding_box_px
        small, large = sorted((box[2]*box[3], other_box[2]*other_box[3]))
        if small >= .15*large and _intersection(box, other_box) >= .70*small:
            return True
    return False


def extend_visual_grid(
    grid: PanelGrid, candidates: list[MotifCandidate], strict: list[MotifCandidate],
    image_shape: tuple[int, ...], fabric_mask: np.ndarray | None,
) -> PanelGrid:
    """Recover one adjacent band per edge only with several stable motifs.

    Blank cloth, a lone accessory, and fragments repeating inside one cell
    cannot extend a grid. Existing lines stay fixed. Perspective/manual grids
    are left to their own geometry rather than extrapolated axis-aligned.
    """
    if grid.source != "visual" or grid.confidence < .82 or grid.lattice is not None or grid.projection is not None:
        return grid
    axes = [list(grid.x_lines_px), list(grid.y_lines_px)]
    for axis in (0, 1):
        step = float(np.median(np.diff(axes[axis])))
        perpendicular = axes[1-axis]
        centers = (np.asarray(perpendicular[:-1]) + perpendicular[1:]) / 2
        cross_step = float(np.median(np.diff(perpendicular)))
        for direction in (-1, 1):
            edge = axes[axis][0 if direction < 0 else -1]
            outer = edge + direction * step
            if not 0 <= outer <= image_shape[1-axis]:
                continue
            expected = edge + direction * step / 2
            supported = set()
            for candidate in candidates:
                x, y, w, h = candidate.bounding_box_px
                point = (x+w/2, y+h/2)
                extent = (w, h)
                if not (.18*step <= extent[axis] <= 1.15*step
                        and .12*cross_step <= extent[1-axis] <= 1.15*cross_step):
                    continue
                if abs(point[axis]-expected) > .40*step:
                    continue
                index = int(np.argmin(abs(centers-point[1-axis])))
                if abs(centers[index]-point[1-axis]) > .40*cross_step:
                    continue
                target = (expected, centers[index]) if axis == 0 else (centers[index], expected)
                if fabric_mask is not None and not fabric_mask[int(target[1]), int(target[0])]:
                    continue
                if _has_stable_core(candidate, strict):
                    supported.add(index)
            if len(supported) >= max(2, int(np.ceil(len(centers)*.30))):
                axes[axis].insert(0, outer) if direction < 0 else axes[axis].append(outer)
    return replace(grid, x_lines_px=tuple(axes[0]), y_lines_px=tuple(axes[1]))


def preserve_spanning_artwork(
    local: list[MotifCandidate], whole: list[MotifCandidate],
    strict: list[MotifCandidate], grid: PanelGrid,
) -> list[MotifCandidate]:
    """Restore a complete narrow illustration cut in two by cell analysis.

    The stricter pass must contain the same tall/wide region without proximity
    merging. This avoids joining separate neighbours merely because their
    loose boxes touch. Large two-dimensional clusters remain unresolved.
    """
    if grid.confidence < .78 or grid.lattice is not None or grid.projection is not None:
        return local
    dx, dy = float(np.median(np.diff(grid.x_lines_px))), float(np.median(np.diff(grid.y_lines_px)))
    result = list(local)
    for candidate in whole:
        x, y, w, h = candidate.bounding_box_px
        vertical = 1.35*dy < h < 2.4*dy and w < .95*dx
        horizontal = 1.35*dx < w < 2.4*dx and h < .95*dy
        if not (vertical or horizontal) or not _stable(candidate, strict):
            continue
        if not (grid.x_lines_px[0] <= x and x+w <= grid.x_lines_px[-1]
                and grid.y_lines_px[0] <= y and y+h <= grid.y_lines_px[-1]):
            continue
        indexes, cells = [], []
        for index, item in enumerate(result):
            bx, by, bw, bh = item.bounding_box_px
            cx, cy = bx+bw/2, by+bh/2
            if (x <= cx <= x+w and y <= cy <= y+h
                    and _intersection(candidate.bounding_box_px, item.bounding_box_px) >= .60*bw*bh):
                indexes.append(index)
                cells.append((int(np.searchsorted(grid.x_lines_px, cx)-1),
                              int(np.searchsorted(grid.y_lines_px, cy)-1)))
        if len(indexes) != 2 or len(set(cells)) != 2:
            continue
        c1, c2 = cells
        if not ((vertical and c1[0] == c2[0] and abs(c1[1]-c2[1]) == 1)
                or (horizontal and c1[1] == c2[1] and abs(c1[0]-c2[0]) == 1)):
            continue
        result = [item for index, item in enumerate(result) if index not in indexes]
        result.append(candidate)
    return sorted(result, key=lambda item: (item.center_px[1], item.center_px[0]))
