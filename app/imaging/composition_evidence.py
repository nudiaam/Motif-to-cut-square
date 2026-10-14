"""Whole-image ink evidence, collected before assigning parts to a grid.

Only used with a corroborated shared fabric colour. Detached letters, stems and
accessories remain components of the source, not background learned from a crop.
No collection names, expected counts or physical cut sizes enter this analysis.
"""
import cv2
import numpy as np

from .logical_layout import layout_from_panel_grid
from .pattern_grid import _cloth_mask


def shared_compositions(image, grid, background_model, minimum_area):
    colour, noise = (np.asarray(v, np.float32) for v in background_model)
    h, w = image.shape[:2]
    layout = layout_from_panel_grid([], grid)
    pitch = min(np.linalg.norm(layout.column_vector_px), np.linalg.norm(layout.row_vector_px))
    lab = cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32),
                          (0, 0), max(.6, min(h,w)/1024.))
    signal = 10*np.linalg.norm((lab-colour)/noise, axis=2)
    mask = ((signal > 35) & (_cloth_mask(image) > 0)).astype(np.uint8)
    count, labels, stats, centres = cv2.connectedComponentsWithStats(mask)
    # Relative size preserves small detached ink across resolutions. Tiny weave
    # dots cannot accumulate into a figure just by sharing its cell.
    component_min = max(6, pitch*pitch*.0015)
    selected = []
    for index in range(1, count):
        x,y,bw,bh,area = stats[index]
        if area < component_min:
            continue
        strong = np.count_nonzero((labels[y:y+bh,x:x+bw] == index) & (signal[y:y+bh,x:x+bw] > 55))
        if strong < max(4, area*.20):
            continue
        selected.append((index, (int(x),int(y),int(bw),int(bh)), int(area)))
    if not selected or len(selected) > grid.columns*grid.rows*10:
        return None
    # Large connected fields can be background or spanning artwork. They need
    # the existing local/spanning analysis, not assignment by their centroid.
    if any(max(box[2:]) > 1.5*pitch for _,box,_ in selected):
        return None
    groups = {}
    unexplained = []
    for index, box, area in selected:
        col, row = layout.coordinates(*centres[index])
        cell = (int(np.floor(col+.5)), int(np.floor(row+.5)))
        if not (0 <= cell[0] < grid.columns and 0 <= cell[1] < grid.rows):
            unexplained.append((box,area))
            continue
        groups.setdefault(cell, []).append((box,area))
    if any(area < max(minimum_area, pitch*pitch*.005) for _,area in unexplained):
        # Sparse border marks are insufficient to validate a global foreground
        # mask. Let local analysis decide, rather than inventing extra cuts.
        return None
    output = []
    for cell, parts in sorted(groups.items(), key=lambda item: item[0][::-1]):
        if sum(a for _,a in parts) < minimum_area:
            continue
        left = min(b[0] for b,_ in parts); top = min(b[1] for b,_ in parts)
        right = max(b[0]+b[2] for b,_ in parts); bottom = max(b[1]+b[3] for b,_ in parts)
        # Never crop the evidence to its assigned cell. A crossing composition
        # remains whole and carries an explicit ownership warning.
        corners = [layout.coordinates(x,y) for x,y in ((left,top),(right,top),(right,bottom),(left,bottom))]
        crossing = any(abs(c-cell[0])>.65 or abs(r-cell[1])>.65 for c,r in corners)
        output.append({'cell':cell,'box':(left,top,right-left,bottom-top), 'area':sum(a for _,a in parts),
                       'anchor':layout.position(*cell), 'parts':len(parts),
                       'issues':('Detached parts cross the proposed cell; check ownership',) if crossing else ()})
    # Evidence outside the layout must remain visible; it cannot be thrown away
    # to improve occupancy or make a competing proposal appear complete.
    for box,area in unexplained:
        if area >= minimum_area:
            output.append({'cell':None,'box':box,'area':area,'anchor':None,'parts':1,
                           'issues':('Artwork outside the proposed printed grid',)})
    return output
