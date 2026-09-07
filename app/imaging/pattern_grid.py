"""Recover repeated artwork on continuous fabric from complete foreground regions.

Independent foreground thresholds propose lattices. Only agreement in dimensions,
spacing and phase, with dense support, authorizes a global grid. Neither expected
counts nor physical cut sizes enter this analysis.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .logical_layout import LayoutObservation, fit_logical_layout
from .panel_grid import PanelGrid


@dataclass(frozen=True, slots=True)
class PatternRegion:
    bounding_box_px: tuple[int, int, int, int]
    area_px: int
    score: float = 0.
    center_px: tuple[float, float] | None = None


@dataclass(frozen=True, slots=True)
class RepeatedPattern:
    grid: PanelGrid
    regions: tuple[PatternRegion, ...]


def _cloth_mask(image: np.ndarray) -> np.ndarray:
    """Exclude the camera surround while filling holes made by dark artwork."""
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, bright = cv2.threshold(cv2.GaussianBlur(gray, (9, 9), 0), 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.full((h, w), 255, np.uint8)
    contour = max(contours, key=cv2.contourArea) if contours else None
    if contour is not None and cv2.contourArea(contour) >= h * w * .3:
        mask.fill(0)
        cv2.drawContours(mask, [contour], -1, 255, -1)
        inset = max(3, int(min(h, w) * .018) | 1)
        mask = cv2.erode(mask, np.ones((inset, inset), np.uint8))
    return mask


def _regions(signal: np.ndarray, threshold: float, minimum_area: float) -> tuple[PatternRegion, ...]:
    small = min(signal.shape)
    mask = (signal > threshold).astype(np.uint8) * 255
    opening = max(1, int(small * .0027) | 1)
    closing = max(3, int(small * .008) | 1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((opening, opening), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((closing, closing), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    boxes = [tuple(map(int, b)) for b in stats[1:]
             if minimum_area <= b[4] <= signal.size * .15]
    # Nested/overlapping component extents belong to the same region (e.g. an
    # aeroplane wing). The merge does not bridge gaps between separate figures.
    changed = True
    while changed:
        changed = False
        for i, a in enumerate(boxes):
            for j in range(i):
                b = boxes[j]
                if (min(a[0] + a[2], b[0] + b[2]) > max(a[0], b[0])
                        and min(a[1] + a[3], b[1] + b[3]) > max(a[1], b[1])):
                    x, y = min(a[0], b[0]), min(a[1], b[1])
                    right, bottom = max(a[0]+a[2], b[0]+b[2]), max(a[1]+a[3], b[1]+b[3])
                    boxes[j] = (x, y, right-x, bottom-y, a[4]+b[4])
                    boxes.pop(i)
                    changed = True
                    break
            if changed:
                break
    regions = []
    for x, y, w, h, area in boxes:
        region_signal = signal[y:y+h, x:x+w]
        foreground = region_signal > threshold
        values = region_signal[foreground]
        contrast = float(values.mean()) if values.size else threshold
        score = .72 * np.clip((contrast-threshold)/80., 0., 1.) + .28 * min(1., area/(minimum_area*8.))
        rows, columns = np.nonzero(foreground)
        # This centre assigns the region to a logical cell; the complete bounds
        # remain untouched for cut validation.  A 20–80 % trimmed extent keeps
        # smoke, tails, branches, and flags from moving the grid observation.
        center = ((x + w / 2., y + h / 2.) if not len(columns) else
                  (x + (np.quantile(columns, .20) + np.quantile(columns, .80)) / 2.,
                   y + (np.quantile(rows, .20) + np.quantile(rows, .80)) / 2.))
        regions.append(PatternRegion(
            (x, y, w, h), area, float(score), tuple(float(v) for v in center)
        ))
    return tuple(regions)


def infer_repeated_artwork(image_bgr: np.ndarray, sensitivity: int = 65,
                           minimum_area_px: int = 500) -> RepeatedPattern | None:
    h, w = image_bgr.shape[:2]
    if min(h, w) < 100:
        return None
    scale = min(1., 1600. / max(h, w))
    image = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image_bgr
    cloth = _cloth_mask(image)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab = cv2.GaussianBlur(lab, (0, 0), max(.8, min(image.shape[:2]) * .0018))
    background = np.median(lab[cloth > 0], axis=0)
    size = max(3, int(min(image.shape[:2]) * .166) | 1)
    # Closing models illumination without letting the interior of a large dark
    # figure become its own background, which would leave disconnected outlines.
    illumination = cv2.morphologyEx(lab[:, :, 0], cv2.MORPH_CLOSE,
                                  np.ones((size, size), np.uint8))
    signal = np.sqrt(.55 * np.maximum(illumination - lab[:, :, 0], 0) ** 2
                     + np.sum((lab[:, :, 1:] - background[1:]) ** 2, axis=2))
    signal[cloth == 0] = 0
    base = float(np.interp(np.clip(sensitivity, 0, 100), [0, 100], [60, 6]) * .55)
    hypotheses = []
    factors = (.80, .92, 1., 1.08, 1.20)
    for factor in factors:
        regions = _regions(signal, base * factor, max(25, minimum_area_px * scale**2))
        if not 6 <= len(regions) <= 300:
            continue
        observations = [LayoutObservation(
            i,
            (x + rw / 2, y + rh / 2),
            region.bounding_box_px,
            region.center_px,
        ) for i, region in enumerate(regions)
          for x, y, rw, rh in [region.bounding_box_px]]
        layout = fit_logical_layout(observations)
        if layout.columns < 2 or layout.rows < 2 or layout.occupancy < .78:
            continue
        hypotheses.append((layout, regions, factor))
    best = None
    for layout, regions, factor in hypotheses:
        spacing = min(np.linalg.norm(layout.column_vector_px), np.linalg.norm(layout.row_vector_px))
        corners = np.array([layout.position(c, r) for c, r in
                            [(0, 0), (layout.columns-1, 0), (0, layout.rows-1)]])
        agreeing = []
        deviations = []
        for other, _, _ in hypotheses:
            if (other.columns, other.rows) != (layout.columns, layout.rows):
                continue
            points = np.array([other.position(c, r) for c, r in
                               [(0, 0), (other.columns-1, 0), (0, other.rows-1)]])
            deviation = float(np.max(np.linalg.norm(points - corners, axis=1)) / spacing)
            if deviation < .10:
                agreeing.append(other)
                deviations.append(deviation)
        if len(agreeing) < 4:
            continue
        support = sum(m.status == "matched" for m in layout.matches) / len(regions)
        # Consistency is extra image evidence, not a relaxed displacement limit.
        # Sparse grids, many unexplained regions or unstable phase still fail.
        confidence = min(len(agreeing) / len(factors), layout.occupancy, support,
                         .98 - float(np.mean(deviations)))
        if confidence < .78:
            continue
        rank = (confidence, -abs(factor - 1.))
        if best is None or rank > best[0]:
            best = rank, layout, regions
    if best is None:
        return None
    (confidence, _), layout, regions = best
    origin = tuple(v / scale for v in layout.origin_px)
    col = tuple(v / scale for v in layout.column_vector_px)
    row = tuple(v / scale for v in layout.row_vector_px)
    # Axis-aligned guides bound the affine cell centres for the existing editor;
    # the stored lattice defines the exact final centres, including orientation.
    xs = tuple(origin[0] + (c - .5) * col[0] + row[0] * (layout.rows-1)/2
               for c in range(layout.columns+1))
    ys = tuple(origin[1] + (r - .5) * row[1] + col[1] * (layout.columns-1)/2
               for r in range(layout.rows+1))
    grid = PanelGrid(xs, ys, confidence, "pattern", (origin, col, row))
    translated = tuple(PatternRegion(
        tuple(int(round(v / scale)) for v in region.bounding_box_px),
        int(round(region.area_px / scale**2)), region.score,
        tuple(float(v / scale) for v in region.center_px)
        if region.center_px is not None else None,
    ) for region in regions)
    return RepeatedPattern(grid, translated)
