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
