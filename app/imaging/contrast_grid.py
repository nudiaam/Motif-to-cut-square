"""Bounded geometry proposals from local contrast, independent of fabric masks.

These masks are evidence for spacing only, never final artwork bounds. Several
scales and thresholds must agree before the original image is analysed by cell.
"""
from dataclasses import dataclass, replace

import cv2
import numpy as np

from .logical_layout import LayoutObservation, fit_logical_layout
from .panel_grid import PanelGrid
from .pattern_grid import _regions
from .scene_profile import POLICY


@dataclass(frozen=True)
class ContrastGeometry:
    grid: PanelGrid
    diagnostics: dict
    regions: tuple = ()


def _shared_background(lab):
    """Estimate a dominant colour only when it recurs across the whole scene.

    Normalise by measured colour noise instead of assuming a minimum absolute
    ink/background contrast. No brightest/darkest-colour assumption is made.
    """
    step=max(1,int(np.sqrt(lab.shape[0]*lab.shape[1]/12000)))
    samples=lab[::step,::step].reshape(-1,3)
    _,inverse,counts=np.unique((samples/np.array([8,4,4])).astype(np.int16),
                               axis=0,return_inverse=True,return_counts=True)
    seed=np.median(samples[inverse==counts.argmax()],axis=0)
    near=(np.linalg.norm(samples[:,1:]-seed[1:],axis=1)<4)&(abs(samples[:,0]-seed[0])<16)
    if near.mean()<.25: return None
    background=np.median(samples[near],axis=0)
    noise=np.maximum([3.,1.,1.],1.4826*np.median(abs(samples[near]-background),axis=0))
    support=(np.linalg.norm(lab[...,1:]-background[1:],axis=2)<4)&(abs(lab[...,0]-background[0])<16)
    patches=[part for row in np.array_split(support,4,axis=0) for part in np.array_split(row,4,axis=1)]
    if sum(float(p.mean())>=.15 for p in patches)<12: return None
    return background,noise


def infer_contrast_geometry(image, *, channel='dark'):
    h, w = image.shape[:2]
    if min(h,w) < 100:
        return None
    scale = POLICY.max_scene_side / max(h, w)
    small = cv2.resize(image, (round(w*scale), round(h*scale)),
                       interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    shared=None
    if channel=='shared_background':
        lab=cv2.GaussianBlur(lab,(0,0),1.)
        shared=_shared_background(lab)
        if shared is None: return None
    luminance = lab[..., 0]
    if channel == 'light': luminance = 255-luminance
    luminance = cv2.GaussianBlur(luminance, (0, 0), 1.)
    proposals = []
    for fraction in (.025 * 2**(i/2) for i in range(6)):
        size = max(3, round(min(small.shape[:2])*fraction) | 1)
        field = cv2.morphologyEx(luminance, cv2.MORPH_CLOSE, np.ones((size,size), np.uint8))
        # Relative contrast keeps a dark outline visible under attenuated light.
        signal = 255*np.maximum(field-luminance, 0)/np.maximum(field, 30)
        if channel == 'chroma':
            # Signed local colour excursions, independent of which ink is brighter.
            # Broad lighting changes are largely in L; hue differences survive here.
            excursions=[]
            for component in (lab[...,1],lab[...,2]):
                component=cv2.GaussianBlur(component,(0,0),1.)
                kernel=np.ones((size,size),np.uint8)
                upper=cv2.morphologyEx(component,cv2.MORPH_CLOSE,kernel)
                lower=cv2.morphologyEx(component,cv2.MORPH_OPEN,kernel)
                excursions.append(np.maximum(upper-component,component-lower))
            signal=3*np.hypot(*excursions)
        elif channel=='shared_background':
            background,noise=shared
            # Broad ink survives this comparison: unlike morphological local
            # contrast, a leaf's interior cannot become its own background.
            smooth=cv2.GaussianBlur(lab,(0,0),max(1.,size*.025))
            signal=10*np.linalg.norm((smooth-background)/noise,axis=2)
        elif channel not in ('dark','light'):
            raise ValueError('Unknown contrast channel: '+channel)
        for threshold in (35, 45, 55, 65, 75):
            # Geometry uses relative fragment size, not the user's absolute
            # minimum cut-artwork area. Otherwise resizing changes the lattice.
            regions = _regions(signal, threshold, max(25, signal.size*.0003), exclude_frame=True)
            if not 6 <= len(regions) <= 150:
                continue
            layout = fit_logical_layout([
                LayoutObservation(i, (x+rw/2,y+rh/2), region.bounding_box_px, region.center_px)
                for i,region in enumerate(regions)
                for x,y,rw,rh in [region.bounding_box_px]])
            support = sum(m.status == 'matched' for m in layout.matches)/len(regions)
            if layout.confidence < .70 or layout.occupancy < .75 or support < .60:
                continue
            proposals.append((layout, fraction, threshold, support, regions))
    best = None
    for layout, fraction, threshold, support, regions in proposals:
        # A dense anchor is mandatory. Less complete passes may corroborate its
        # geometry (thin ink can fragment after resampling), but cannot create it.
        if layout.confidence < .80 or layout.occupancy < .85 or support < .70:
            continue
        spacing = min(np.linalg.norm(layout.column_vector_px), np.linalg.norm(layout.row_vector_px))
        corners = [(0,0),(layout.columns-1,0),(0,layout.rows-1),(layout.columns-1,layout.rows-1)]
        agreeing = [p for p in proposals
                    if (p[0].columns,p[0].rows) == (layout.columns,layout.rows)
                    and max(np.linalg.norm(np.array(layout.position(c,r))-p[0].position(c,r))
                            for c,r in corners) < spacing*.10]
        if (len(agreeing) < 2 or len({p[1] for p in agreeing}) < 2
                or len({p[2] for p in agreeing}) < 2):
            continue
        strong = sum(p[0].confidence >= .80 and p[0].occupancy >= .85 and p[3] >= .70
                     for p in agreeing)
        if strong < 2 and len(agreeing) < 3:
            continue
        rank = (len(agreeing), layout.confidence*layout.occupancy*support)
        if best is None or rank > best[0]:
            best = rank, layout, agreeing, regions
    if best is None:
        return None
    _, layout, agreeing, regions = best
    origin = tuple(v/scale for v in layout.origin_px)
    column = tuple(v/scale for v in layout.column_vector_px)
    row = tuple(v/scale for v in layout.row_vector_px)
    grid = PanelGrid(
        tuple(origin[0]+(c-.5)*column[0]+(layout.rows-1)*row[0]/2 for c in range(layout.columns+1)),
        tuple(origin[1]+(r-.5)*row[1]+(layout.columns-1)*column[1]/2 for r in range(layout.rows+1)),
        layout.confidence, 'local_contrast', (origin,column,row))
    scaled=tuple(replace(r,bounding_box_px=tuple(round(v/scale) for v in r.bounding_box_px),
                         center_px=tuple(v/scale for v in r.center_px),
                         area_px=round(r.area_px/scale**2)) for r in regions)
    return ContrastGeometry(grid, {
        'analysis_size_px':[small.shape[1],small.shape[0]],
        'agreeing_passes':len(agreeing), 'scales':sorted({p[1] for p in agreeing}),
        'thresholds':sorted({p[2] for p in agreeing}),
        'occupancy':layout.occupancy, 'confidence':layout.confidence,
        'source_pixels_preserved':True,'channel':channel,
        **({'background_lab':shared[0].tolist(),'background_noise_lab':shared[1].tolist()}
           if shared is not None else {})},scaled)
