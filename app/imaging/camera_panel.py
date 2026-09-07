"""Find touching patchwork panels in a camera photograph.

Rectification is an analysis image only. All returned geometry is mapped back
to the original photo; bed calibration and the displayed image stay unchanged.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from .panel_grid import PanelGrid


@dataclass(frozen=True, slots=True)
class CameraPanel:
    image: np.ndarray
    grid: PanelGrid
    to_source: np.ndarray


def _axis_choices(profile: np.ndarray, minimum_cell: int):
    length = len(profile)
    edge = max(1, int(length * .07))
    profile = profile.copy()
    profile[:edge] = profile[-edge:] = np.median(profile[edge:-edge])
    baseline, high = np.percentile(profile, [50, 96])
    if high - baseline < .5:
        return []
    excess = np.maximum(0, profile - np.percentile(profile, 60))
    fits = []
    for count in range(2, length // minimum_cell + 1):
        step = length / count
        radius = max(2, int(step * .13))
        strengths, offsets = [], []
        near = np.zeros(length, bool)
        for index in range(1, count):
            expected = index * step
            start, stop = max(0, int(expected)-radius), min(length, int(expected)+radius+1)
            xs = np.arange(start, stop)
            normalized = np.clip((profile[start:stop]-baseline)/(high-baseline), 0, 1.5)
            penalty = abs(xs-expected)/radius
            chosen = int(np.argmax(normalized - .2 * penalty))
            position = xs[chosen]
            strengths.append(normalized[chosen])
            offsets.append(abs(position-expected)/step)
            near[max(0, int(position-step*.065)):min(length, int(position+step*.065)+1)] = True
        strength = .58*np.mean(strengths) + .32*np.quantile(strengths, .25) - .1*np.mean(offsets)/.13
        coverage = float(excess[near].sum()/max(1e-6, excess.sum()))
        if strength < .4 or coverage < .16 or np.mean(offsets) > .10:
            continue
        fits.append((count, float(strength * coverage)))
    return fits


def infer_camera_panel(image_bgr: np.ndarray) -> CameraPanel | None:
    height, width = image_bgr.shape[:2]
    if min(height, width) < 160:
        return None
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    _, bright = cv2.threshold(cv2.GaussianBlur(gray, (9, 9), 0), 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < height * width * .25:
        return None
    hull = cv2.convexHull(contour)
    polygon = cv2.approxPolyDP(hull, cv2.arcLength(hull, True)*.02, True).reshape(-1, 2)
    if len(polygon) != 4 or cv2.contourArea(polygon) < cv2.contourArea(hull)*.94:
        return None
    points = polygon.astype(np.float32)
    sums, diffs = points.sum(1), np.diff(points, axis=1).ravel()
    quad = np.array([points[np.argmin(sums)], points[np.argmin(diffs)],
                     points[np.argmax(sums)], points[np.argmax(diffs)]])
    if len(np.unique(quad, axis=0)) != 4:
        return None
    w = max(np.linalg.norm(quad[1]-quad[0]), np.linalg.norm(quad[2]-quad[3]))
    h = max(np.linalg.norm(quad[3]-quad[0]), np.linalg.norm(quad[2]-quad[1]))
    scale = min(1., 1400/max(w, h))
    w, h = int(w*scale), int(h*scale)
    if min(w, h) < 100:
        return None
    transform = cv2.getPerspectiveTransform(quad, np.float32([[0,0], [w-1,0], [w-1,h-1], [0,h-1]]))
    rectified = cv2.warpPerspective(image_bgr, transform, (w, h))
    lab = cv2.cvtColor(rectified, cv2.COLOR_BGR2LAB).astype(np.float32)
    votes = []
    for smoothing in (.006, .010, .014):
        softened = cv2.GaussianBlur(lab, (0, 0), min(w,h)*smoothing)
        axes = []
        delta = max(4, int(min(w,h)*.014)//2*2)
        for axis in (1, 0):
            along = np.swapaxes(softened, 0, axis)
            difference = np.linalg.norm(along[delta:]-along[:-delta], axis=2)
            # Seams must be supported over most of the perpendicular direction.
            # A high percentile would mistake repeated motif edges for divisions.
            profile = np.pad(np.percentile(difference, 40, axis=1), (delta//2, delta//2))
            profile = cv2.GaussianBlur(profile.reshape(1,-1), (0,0), max(1., min(w,h)*.003)).ravel()
            axes.append(_axis_choices(profile, max(30, int(min(w,h)*.04))))
        choices = [(float(np.sqrt(sx*sy)), c, r) for c, sx in axes[0] for r, sy in axes[1]
                   if c*r >= 6 and .60 <= (w/c)/(h/r) <= 1.7]
        choices.sort(reverse=True)
        if not choices or choices[0][0] < .18:
            continue
        best = choices[0]
        separation = (best[0]-choices[1][0])/best[0] if len(choices) > 1 else 1.
        if separation >= .15:
            votes.append((best[1], best[2], separation))
    if len(votes) < 2:
        return None
    dimensions = max({v[:2] for v in votes}, key=lambda cr: sum(v[:2] == cr for v in votes))
    agreement = [v for v in votes if v[:2] == dimensions]
    if len(agreement) < 2:
        return None
    confidence = float(min(.96, .80 + .10*len(agreement)/3 + .06*np.mean([v[2] for v in agreement])))
    grid = PanelGrid.regular(w, h, *dimensions, confidence=confidence, source="camera")
    return CameraPanel(rectified, grid, np.linalg.inv(transform))


def project_points(points, transform):
    return cv2.perspectiveTransform(np.asarray(points, dtype=np.float64).reshape(-1,1,2), transform).reshape(-1,2)


def source_grid(panel: CameraPanel) -> PanelGrid:
    """Project a regular lattice back through one global camera transform."""
    grid = panel.grid
    cells = [(c, r) for r in range(grid.rows) for c in range(grid.columns)]
    centers = [((grid.x_lines_px[c]+grid.x_lines_px[c+1])/2,
                (grid.y_lines_px[r]+grid.y_lines_px[r+1])/2) for c, r in cells]
    projected = project_points(centers, panel.to_source)
    model = np.linalg.lstsq(np.column_stack([np.ones(len(cells)), cells]), projected, rcond=None)[0]
    origin, col, row = model
    xs = tuple(float(origin[0] + (c-.5)*col[0] + (grid.rows-1)*row[0]/2) for c in range(grid.columns+1))
    ys = tuple(float(origin[1] + (r-.5)*row[1] + (grid.columns-1)*col[1]/2) for r in range(grid.rows+1))
    step_x, step_y = grid.x_lines_px[1]-grid.x_lines_px[0], grid.y_lines_px[1]-grid.y_lines_px[0]
    cell_to_rectified = np.array([[step_x,0,step_x/2], [0,step_y,step_y/2], [0,0,1.]])
    projection = panel.to_source @ cell_to_rectified
    projection /= projection[2,2]
    return PanelGrid(xs, ys, grid.confidence, "camera", tuple(tuple(float(v) for v in p) for p in model),
                     tuple(tuple(float(v) for v in p) for p in projection))
