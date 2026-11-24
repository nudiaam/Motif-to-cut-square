"""Locate repeated printed panels inside a photographed piece of fabric.

No motif centres or expected row/column counts are used here. Broad print bands
are measured independently on both axes; fabric margins and the laser bed are
not assumed to be cells. Images without that evidence use the motif layout.
"""

from __future__ import annotations

import cv2
import numpy as np
from dataclasses import replace

from .panel_grid import PanelGrid
from .scene_profile import POLICY


def _observed_outer_frame(crop, axis, expected, pitch, cloth_bounds):
    """Read a sustained dark stroke, independently of its two gradient flanks.

    Neighbouring measured divisions only place the search window. They never
    supply the returned border: both readings must locate the same narrow,
    continuous printed stroke, away from the cloth/bed transition.
    """
    from .printed_partition import _profiles, _response_center

    lo, hi = cloth_bounds
    inset = max(3., pitch*.035)
    length = crop.shape[axis]
    start = max(1, int(np.ceil(lo+inset)), int(expected-pitch*.18))
    stop = min(length-1, int(np.floor(hi-inset))+1, int(expected+pitch*.18)+1)
    if stop-start < 5:
        return None
    indices = np.arange(start, stop)
    readings = []
    for sigma in (.5, .8):
        profile = _profiles(crop, 'frames', sigma)[1-axis]
        values = profile[indices]
        floor = float(np.median(values))
        mad = float(np.median(abs(values-floor)))
        high = float(values.max())
        if high < max(4., floor+6*mad):
            return None
        peak = _response_center(profile, indices, floor, high, .6)
        if peak is None or not start <= peak[0] < stop:
            return None
        # Separate strokes of comparable strength do not identify one border.
        rivals = indices[(abs(indices-peak[0]) > max(5., pitch*.08)) &
                         (values >= floor+(high-floor)*.65)]
        if len(rivals):
            return None
        readings.append(peak[0])
    if abs(readings[0]-readings[1]) > 2.:
        return None
    return float(np.mean(readings)), abs(readings[0]-readings[1])/2


def refine_printed_boundaries(image_bgr,grid):
    """Refine sustained touching seams locally, without fitting a mean pitch.

    Gutter pairs and artwork-only edges do not establish a single seam. This
    refinement never changes dimensions or overrides manual/projective guides.
    A nearly axis-aligned artwork lattice may also yield to independently
    observed print seams; motif centres are not precise panel boundaries.
    """
    if grid is not None and grid.source in {'local_contrast','observations'}:
        from .section_evidence import refine_artwork_sections
        return refine_artwork_sections(image_bgr,grid)
    if grid is not None and grid.source=='printed' and grid.cell_regions_px:
        from .section_evidence import refine_projected_sections
        return refine_projected_sections(image_bgr,grid)
    if grid is None or grid.source == 'manual' or grid.projection is not None:
        return grid
    h,w = image_bgr.shape[:2]
    scale = min(1.,POLICY.max_scene_side/max(h,w))
    artwork_lattice = grid.lattice is not None
    if artwork_lattice:
        if grid.source not in ('pattern','fabric','ink_lattice'):
            return grid
        _,column,row = grid.lattice
        # Only discard fitting noise below the seam measurement resolution.
        # A genuinely rotated/sheared lattice keeps its original geometry.
        drift = max(abs(column[1])*grid.columns,abs(row[0])*grid.rows)
        if drift*scale > 2.:
            return grid
    elif grid.source not in ('visual','seam_consensus'):
        return grid
    small = cv2.resize(image_bgr,(round(w*scale),round(h*scale)),interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(small,cv2.COLOR_BGR2LAB).astype(np.float32)
    fx,fy,fw,fh = _fabric_bounds(small)
    lines = (np.asarray(grid.x_lines_px)*scale,np.asarray(grid.y_lines_px)*scale)
    refined = []
    outer_unconfirmed = False
    frame_spread = 0.
    for axis,expected in zip((1,0),lines):
        perpendicular = lines[1 if axis == 1 else 0]
        a,b = int(np.ceil(perpendicular[0])),int(np.floor(perpendicular[-1]))
        crop = lab[max(0,a):min(small.shape[0],b)] if axis == 1 else lab[:,max(0,a):min(small.shape[1],b)]
        bgr_crop = (small[max(0,a):min(small.shape[0],b)] if axis == 1 else
                    small[:,max(0,a):min(small.shape[1],b)])
        if min(crop.shape[:2]) < 20:
            return grid
        readings = []
        pitch = float(np.median(np.diff(expected)))
        for gap in (2,4):
            softened = cv2.GaussianBlur(crop,(0,0),1.)
            along = np.swapaxes(softened,0,axis)
            difference = np.linalg.norm(along[gap:]-along[:-gap],axis=2)
            profile = np.pad(np.percentile(difference,20,axis=1),(gap//2,gap//2))
            measured = []
            for boundary_index,position in enumerate(expected):
                signal = profile
                left,right = max(1,int(position-pitch*.18)),min(len(profile)-1,int(position+pitch*.18)+1)
                if right <= left:
                    measured.append(None);continue
                peaks = [p for p in range(left,right) if signal[p]>=signal[p-1] and signal[p]>signal[p+1]]
                if boundary_index in (0,len(expected)-1):
                    # A bed/cloth transition is often stronger than the print
                    # edge. It must not expand a printed cell into the border.
                    cloth_lo,cloth_hi = (fx,fx+fw) if axis == 1 else (fy,fy+fh)
                    inset = max(3.,pitch*.035)
                    peaks = [p for p in peaks if cloth_lo+inset < p < cloth_hi-inset]
                    noise = signal[max(left,int(np.ceil(cloth_lo+inset))):min(right,int(np.floor(cloth_hi-inset))+1)]
                else:
                    noise = signal
                if not len(noise):
                    measured.append(None);continue
                # The outer cloth band has a different noise floor from the
                # illustrated interior; use its local baseline, still requiring
                # the same seam at two scales.
                floor = float(np.median(noise))
                mad = float(np.median(abs(noise-floor)))
                peaks.sort(key=lambda p:signal[p],reverse=True)
                if not peaks or signal[peaks[0]] < max(1.5,floor+4*mad):
                    measured.append(None);continue
                strongest = peaks[0]
                if any(abs(p-strongest)>gap*2 and signal[p]>=signal[strongest]*.65 for p in peaks[1:]):
                    measured.append(None);continue
                measured.append(float(strongest))
            readings.append(measured)
        chosen = expected.copy()
        accepted = []
        for i,(a,b) in enumerate(zip(*readings)):
            if a is not None and b is not None and abs(a-b)<=2.:
                chosen[i]=(a+b)/2
                accepted.append(i)
        # Both axes need repeated independent seam evidence. Avoid turning a
        # few motif edges into a replacement for a supported global layout.
        if sum(0<i<len(expected)-1 for i in accepted) < max(1,int(np.ceil((len(expected)-2)*.75))):
            return grid
        for edge, neighbours in ((0, (1, 2)), (len(chosen)-1, (len(chosen)-2, len(chosen)-3))):
            if edge in accepted or not all(i in accepted for i in neighbours):
                continue
            near, farther = neighbours
            proposal = 2*chosen[near]-chosen[farther]
            # Re-open an exterior search only when measured adjacent seams
            # contradict its old phase. Leave already consistent grids alone.
            if abs(proposal-chosen[edge]) <= pitch*.08:
                continue
            bounds = (fx, fx+fw) if axis == 1 else (fy, fy+fh)
            observed = _observed_outer_frame(bgr_crop, axis, proposal,
                                            abs(chosen[near]-chosen[farther]), bounds)
            if observed is None:
                outer_unconfirmed = True
            else:
                chosen[edge] = observed[0]
                frame_spread = max(frame_spread, observed[1]/scale)
        if np.any(np.diff(chosen)<pitch*.65):
            return grid
        refined.append(tuple(float(v/scale) for v in chosen))
    issues = grid.review_reasons
    if outer_unconfirmed:
        issues = tuple(dict.fromkeys((*issues,
            'Outer printed boundary could not be confirmed; check section guides')))
    return replace(grid,x_lines_px=refined[0],y_lines_px=refined[1],
                   lattice=None if artwork_lattice else grid.lattice,
                   source='visual' if artwork_lattice else grid.source,
                   review_reasons=issues,
                   boundary_uncertainty_px=(max(grid.boundary_uncertainty_px or
                       POLICY.boundary_uncertainty_px/scale, frame_spread)
                       if frame_spread else grid.boundary_uncertainty_px))


def _fabric_bounds(image: np.ndarray) -> tuple[int, int, int, int]:
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, bright = cv2.threshold(cv2.GaussianBlur(gray, (9, 9), 0), 0, 255,
                              cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, _, stats, _ = cv2.connectedComponentsWithStats(bright)
    if len(stats) <= 1:
        return 0, 0, width, height
    x, y, w, h, area = stats[1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])]
    if area < image.shape[0] * image.shape[1] * 0.20:
        return 0, 0, width, height
    return int(x), int(y), int(w), int(h)


def _print_bands(profile: np.ndarray) -> list[tuple[float, tuple[float, ...]]]:
    """Fit regularly spaced wide bands without anchoring them to image edges."""
    length = len(profile)
    profile = cv2.GaussianBlur(profile.reshape(1, -1), (0, 0), max(1., length * .003)).ravel()
    low, high = np.percentile(profile, [15, 85])
    if high - low < 3.0:
        return []
    fits = []
    for fraction in (.10, .15, .20, .25, .35, .45, .55):
        mask = (profile > low + fraction * (high - low)).astype(np.uint8)
        # Close small interruptions inside a print; retain the wider gutters.
        kernel = np.ones((1, max(3, int(length * .018) | 1)), np.uint8)
        mask = cv2.morphologyEx(mask.reshape(1, -1), cv2.MORPH_CLOSE, kernel).ravel()
        bands = np.flatnonzero(np.diff(np.r_[0, mask, 0])).reshape(-1, 2)
        bands = np.array([(a, b) for a, b in bands
                          if a > 0 and b < length and b - a >= max(4, length * .025)])
        if len(bands) < 2:
            continue
        widths = bands[:, 1] - bands[:, 0]
        # An isolated residual bed edge or small pattern stripe is not a panel.
        bands = bands[widths >= np.median(widths) * .5]
        if len(bands) < 2:
            continue
        centers = bands.mean(axis=1)
        origin, step = np.linalg.lstsq(
            np.column_stack([np.ones(len(centers)), np.arange(len(centers))]), centers, rcond=None,
        )[0]
        if step <= 0:
            continue
        residual = np.abs(centers - (origin + np.arange(len(centers)) * step)) / step
        duty = (bands[:, 1] - bands[:, 0]) / step
        if (np.max(residual) > .14 or np.mean(residual) > .07
                or np.median(duty) < .55 or np.median(duty) > .94
                or step * len(centers) < length * .65):
            continue
        lines = origin + (np.arange(len(centers) + 1) - .5) * step
        if lines[0] < 0 or lines[-1] > length:
            continue
        width_cv = np.std(duty) / np.mean(duty)
        if width_cv > .30:
            continue
        score = float(np.clip(.99 - 2 * np.mean(residual) - .15 * width_cv
                              - (.06 if len(centers) == 2 else 0), 0, .98))
        fits.append((score, tuple(float(v) for v in lines)))
    # Prefer a model explaining all visible bands over a tidier subset that
    # drops a pale outer row or column (common in pastel collections).
    return sorted(fits, key=lambda fit: fit[0] + .35 * (fit[1][-1] - fit[1][0]) / length,
                  reverse=True)


def infer_printed_panel_grid(image_bgr: np.ndarray) -> PanelGrid | None:
    """Return only a visually supported grid, independent of motif detection."""
    height, width = image_bgr.shape[:2]
    if min(height, width) < 100:
        return None
    scale = min(1.0, 1100.0 / max(height, width))
    image = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image_bgr
    x, y, w, h = _fabric_bounds(image)
    if min(w, h) < 80:
        return None
    lab = cv2.cvtColor(image[y:y+h, x:x+w], cv2.COLOR_BGR2LAB).astype(np.float32)
    lab = cv2.GaussianBlur(lab, (0, 0), max(1.0, min(w, h) * .005))
    size = max(3, int(min(w, h) * .32) | 1)
    illumination = cv2.morphologyEx(lab[:, :, 0], cv2.MORPH_CLOSE, np.ones((size, size), np.uint8))
    # The bright part of the fabric border estimates the unprinted cloth tone.
    by, bx = max(2, h // 30), max(2, w // 30)
    border = np.concatenate([lab[:by].reshape(-1, 3), lab[-by:].reshape(-1, 3),
                             lab[:, :bx].reshape(-1, 3), lab[:, -bx:].reshape(-1, 3)])
    background = np.median(border[border[:, 0] >= np.median(border[:, 0])], axis=0)
    print_signal = (np.maximum(illumination - lab[:, :, 0], 0) * .55
                    + np.linalg.norm(lab[:, :, 1:] - background[1:], axis=2))
    # A motif occupies only part of each cell; broad printed backgrounds repeat
    # over most of the perpendicular axis, surviving this percentile projection.
    x_fits = _print_bands(np.percentile(print_signal, 55, axis=0))
    y_fits = _print_bands(np.percentile(print_signal, 55, axis=1))
    for x_score, xs in x_fits:
        for y_score, ys in y_fits:
            aspect = (xs[1] - xs[0]) / (ys[1] - ys[0])
            confidence = min(x_score, y_score)
            if not .55 <= aspect <= 1.8 or confidence < .82 or (len(xs)-1)*(len(ys)-1) < 6:
                continue
            return PanelGrid(tuple((v + x) / scale for v in xs),
                             tuple((v + y) / scale for v in ys), confidence, "visual")
    return None
