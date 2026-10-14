"""An original-pixel check that can contradict a candidate's own bounds.

This is evidence of uncertainty, not a second claim of semantic recognition.
Never expand or shrink a motif merely to make a fixed-size cut appear valid.
"""
from dataclasses import replace

import cv2
import numpy as np
from .scene_profile import background_evidence


def review_extents(image, candidates, grid=None):
    from .logical_layout import layout_from_panel_grid
    layout = layout_from_panel_grid([], grid) if grid is not None else None
    if grid is not None:
        spacing = min(float(np.median(np.diff(grid.x_lines_px))),
                      float(np.median(np.diff(grid.y_lines_px))))
    else:
        spacing = None
    reviewed = []
    ih, iw = image.shape[:2]
    for candidate in candidates:
        x, y, w, h = candidate.bounding_box_px
        scale = spacing if spacing is not None else max(w, h)
        pad = max(6, int(round(scale*.18)))
        left, top = max(0, x-pad), max(0, y-pad)
        right, bottom = min(iw, x+w+pad), min(ih, y+h+pad)
        core = None
        partial_cell = False
        if grid is not None:
            cx, cy = candidate.layout_center_px or candidate.center_px
            column = int(np.searchsorted(grid.x_lines_px,cx)-1)
            row = int(np.searchsorted(grid.y_lines_px,cy)-1)
            if grid.lattice is not None:
                gc, gr = layout.coordinates(cx,cy)
                column, row = int(np.floor(gc+.5)), int(np.floor(gr+.5))
            if 0 <= column < grid.columns and 0 <= row < grid.rows:
                gx0, gx1 = grid.x_lines_px[column:column+2]
                gy0, gy1 = grid.y_lines_px[row:row+2]
                if grid.lattice is not None:
                    corners = np.asarray([layout.position(column+dc,row+dr)
                                          for dc,dr in ((-.5,-.5),(.5,-.5),(.5,.5),(-.5,.5))])
                    gx0, gy0 = corners.min(axis=0)
                    gx1, gy1 = corners.max(axis=0)
                partial_cell = not layout.cell_inside_image(column, row, iw, ih)
                if partial_cell and grid.source in ('pattern','observations','local_contrast'):
                    # Extrapolated artwork spacing is not a printed panel edge.
                    # Require nearby ink before declaring the source truncated.
                    margin=max(2.,scale*.10)
                    partial_cell=((gx0<0 and x<margin) or (gy0<0 and y<margin) or
                                  (gx1>iw and x+w>iw-margin) or (gy1>ih and y+h>ih-margin))
                # Inspect the owning cell even if segmentation found only a head.
                left,top=max(0,min(left,int(gx0)-pad)),max(0,min(top,int(gy0)-pad))
                right,bottom=min(iw,max(right,int(gx1)+pad)),min(ih,max(bottom,int(gy1)+pad))
                core=(max(0,round(gx0)-left),max(0,round(gy0)-top),
                      min(right-left,round(gx1)-left),min(bottom-top,round(gy1)-top))
        issues = list(candidate.review_reasons)
        boundary_artwork = x <= 0 or y <= 0 or x+w >= iw or y+h >= ih
        if partial_cell:
            issues.append('Panel is only partly inside the source image; verify the complete composition')
        if boundary_artwork:
            issues.append('Artwork reaches the source-image boundary')
        candidate = replace(candidate, source_incomplete=(candidate.source_incomplete or partial_cell or boundary_artwork),
                            review_reasons=tuple(dict.fromkeys(issues)))
        crop = image[top:bottom, left:right]
        if min(crop.shape[:2]) < 8:
            reviewed.append(candidate)
            continue
        evidence=background_evidence(crop,core)
        if evidence is None:
            reviewed.append(replace(candidate,review_reasons=tuple(dict.fromkeys(
                (*candidate.review_reasons,'Insufficient image evidence to check artwork extent')))))
            continue
        signal=evidence['distance']
        threshold=evidence['stats']['foreground_threshold']
        inner = np.zeros(signal.shape, bool)
        inner[max(0,y-top):min(bottom-top,y+h-top), max(0,x-left):min(right-left,x+w-left)] = True
        tolerance = max(2, int(round(scale*.015)))
        beyond = np.ones(signal.shape, bool)
        beyond[max(0,y-top-tolerance):min(bottom-top,y+h-top+tolerance),
               max(0,x-left-tolerance):min(right-left,x+w-left+tolerance)] = False
        extension = False
        for factor in (1., 1.5):
            mask = (signal > threshold*factor).astype(np.uint8)
            count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
            inside_counts = np.bincount(labels[inner], minlength=count)
            outside_counts = np.bincount(labels[beyond], minlength=count)
            # A neighbouring object outside the box is not automatically part
            # of this motif. Require substantial connected support inside it.
            supported = ((inside_counts >= max(20, candidate.area_px*.15))
                         & (outside_counts >= np.maximum(12, inside_counts*.02)))
            supported[0] = False
            if np.any(supported):
                extension = True
                break
        issues = list(candidate.review_reasons)
        if core is not None:
            cell_area = max(1, (core[2]-core[0])*(core[3]-core[1]))
            if (w*h < cell_area*.12 and evidence['stats']['fine_detail_fraction'] > .12):
                issues.append('Small foreground on a textured panel; check for missing faint or detached details')
        if not evidence['stats']['background_reliable']:
            issues.append('Background is ambiguous; artwork extent needs review')
        if extension:
            issues.append("Image evidence continues beyond the detected artwork; check its full extent")
        reviewed.append(replace(candidate, review_reasons=tuple(dict.fromkeys(issues))))
    return tuple(reviewed)
