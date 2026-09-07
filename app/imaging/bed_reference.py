"""Registered empty-bed comparison and lattice extent from physical fabric."""
from dataclasses import dataclass

import cv2
import numpy as np

from .logical_layout import LogicalLayout
from .panel_grid import PanelGrid


@dataclass(frozen=True)
class FabricEvidence:
    mask: np.ndarray | None
    reason: str


def locate_fabric(image: np.ndarray, reference: np.ndarray) -> FabricEvidence:
    """Require visible matching bed before trusting foreground differences.

    Different camera photographs must not be interpreted as a whole-bed piece.
    Registration is restricted to small camera movement; source pixels and
    physical calibration are never transformed.
    """
    h, w = image.shape[:2]
    rh, rw = reference.shape[:2]
    if abs((w / h) / (rw / rh) - 1) > .025:
        return FabricEvidence(None, "Reference framing does not match this image")
    scale = min(1., 1000 / max(h, w))
    size = (round(w * scale), round(h * scale))
    current = cv2.resize(image, size).astype(np.float32)
    empty = cv2.resize(reference, size).astype(np.float32)
    gray = cv2.cvtColor(current.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    refgray = cv2.cvtColor(empty.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    # Feature registration can recover a small shift despite foreground cover.
    orb = cv2.ORB_create(nfeatures=4000, fastThreshold=12)
    ka, da = orb.detectAndCompute(refgray, None)
    kb, db = orb.detectAndCompute(gray, None)
    if da is not None and db is not None:
        pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da, db, k=2)
        good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < .65 * p[1].distance]
        if len(good) >= 16:
            a = np.float32([ka[m.queryIdx].pt for m in good])
            b = np.float32([kb[m.trainIdx].pt for m in good])
            transform, inliers = cv2.estimateAffinePartial2D(a, b, method=cv2.RANSAC,
                                                          ransacReprojThreshold=2)
            if transform is not None and inliers.sum() >= 12:
                corners = np.float32([[0, 0], [size[0], 0], [0, size[1]], size])
                moved = cv2.transform(corners[None], transform)[0]
                if np.max(np.linalg.norm(moved-corners, axis=1)) < min(size) * .025:
                    empty = cv2.warpAffine(empty, transform, size, borderMode=cv2.BORDER_REFLECT)
    # Robust photometric fit uses only pixels already close to the reference.
    a = cv2.GaussianBlur(empty, (3, 3), 0)
    b = cv2.GaussianBlur(current, (3, 3), 0)
    for _ in range(3):
        distance = np.mean(abs(a-b), axis=2)
        keep = distance <= np.percentile(distance, 20)
        for channel in range(3):
            x, y = a[..., channel][keep], b[..., channel][keep]
            design = np.column_stack([x, np.ones(len(x))])
            gain, offset = np.linalg.lstsq(design, y, rcond=None)[0]
            if .75 <= gain <= 1.3 and abs(offset) <= 30:
                a[..., channel] = a[..., channel]*gain + offset
    difference = np.mean(abs(a-b), axis=2)
    # Low-frequency colour alone is insufficient: confirm the bed's fine texture.
    ag = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    bg = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    ah = ag-cv2.GaussianBlur(ag, (0, 0), 3)
    bh = bg-cv2.GaussianBlur(bg, (0, 0), 3)
    covariance = cv2.GaussianBlur(ah*bh, (0, 0), 5)
    variance = np.sqrt(cv2.GaussianBlur(ah*ah, (0, 0), 5)
                       * cv2.GaussianBlur(bh*bh, (0, 0), 5))
    correlation = covariance / np.maximum(variance, 1)
    matching = (difference < 14) & (correlation > .65) & (variance > 3)
    sh, sw = gray.shape
    # Visible matching texture must be distributed, not one accidental patch.
    tiles = [matching[y:y+sh//4, x:x+sw//4].mean()
             for y in range(0, sh-sh//4+1, sh//4)
             for x in range(0, sw-sw//4+1, sw//4)]
    if matching.mean() < .08 or sum(v > .12 for v in tiles) < 4:
        return FabricEvidence(None, "Reference could not be matched to the visible bed")
    noise = float(np.median(difference[matching]))
    changed = ((difference > max(16., noise*4))
               | ((correlation < .25) & (variance > 3))).astype(np.uint8)*255
    radius = max(3, round(min(size)*.012) | 1)
    changed = cv2.morphologyEx(changed, cv2.MORPH_CLOSE, np.ones((radius, radius), np.uint8))
    changed = cv2.morphologyEx(changed, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(changed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.zeros(gray.shape, np.uint8)
    # Fill print holes inside physical pieces; do not join separate pieces.
    for contour in contours:
        if cv2.contourArea(contour) >= gray.size*.025:
            cv2.drawContours(mask, [contour], -1, 255, -1)
    return FabricEvidence(cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST),
                          "Empty-bed reference applied")


def extend_to_fabric(layout: LogicalLayout, mask: np.ndarray) -> PanelGrid | None:
    """Extend integer cell bounds without changing spacing, phase or projection."""
    if not layout.reliable:
        return None
    _, labels = cv2.connectedComponents((mask > 0).astype(np.uint8))
    h, w = mask.shape
    def label_at(x, y):
        return labels[int(y), int(x)] if 0 <= x < w and 0 <= y < h else 0
    votes = [label_at(*layout.position(c, r)) for r in range(layout.rows)
             for c in range(layout.columns)]
    positive = [v for v in votes if v]
    if len(positive) < len(votes)*.8:
        return None
    component = int(np.bincount(positive).argmax())
    if votes.count(component) < len(votes)*.8:
        return None
    def inside(c, r):
        # Sample almost the full logical cell, independently of cut inches.
        points = [layout.position(c+dx, r+dy)
                  for dx in np.linspace(-.46, .46, 7)
                  for dy in np.linspace(-.46, .46, 7)]
        return (label_at(*layout.position(c, r)) == component
                and sum(label_at(*p) == component for p in points)/len(points) >= .94)
    left, right, top, bottom = 0, layout.columns-1, 0, layout.rows-1
    for _ in range(30):
        before = left, right, top, bottom
        if all(inside(left-1, r) for r in range(top, bottom+1)): left -= 1
        if all(inside(right+1, r) for r in range(top, bottom+1)): right += 1
        if all(inside(c, top-1) for c in range(left, right+1)): top -= 1
        if all(inside(c, bottom+1) for c in range(left, right+1)): bottom += 1
        if before == (left, right, top, bottom): break
    columns, rows = right-left+1, bottom-top+1
    origin = layout.position(left, top)
    col, row = layout.column_vector_px, layout.row_vector_px
    projection = None
    if layout.projection is not None:
        p = np.asarray(layout.projection) @ np.array([[1,0,left],[0,1,top],[0,0,1]])
        projection = tuple(tuple(float(v) for v in line) for line in p)
    return PanelGrid(
        tuple(origin[0]+(c-.5)*col[0]+row[0]*(rows-1)/2 for c in range(columns+1)),
        tuple(origin[1]+(r-.5)*row[1]+col[1]*(columns-1)/2 for r in range(rows+1)),
        layout.confidence, "reference", (origin, col, row), projection)
