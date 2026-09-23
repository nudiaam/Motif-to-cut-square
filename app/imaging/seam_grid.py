"""Propose printed divisions from sustained colour changes at two scales.

These are hypotheses, not cuts. No foreground count or camera extent fixes the
number of cells. The coordinator must corroborate them with local artwork.
"""
import cv2
import numpy as np

from .panel_grid import PanelGrid
from .scene_profile import POLICY


def _axis_lines(profile):
    length = len(profile)
    floor = float(np.median(profile))
    mad = float(np.median(abs(profile-floor)))
    threshold = max(floor+5*mad, float(profile.max())*.45, .6)
    peaks = np.flatnonzero((profile > np.roll(profile,1)) &
                          (profile >= np.roll(profile,-1)) & (profile > threshold))
    # Suppress adjacent peaks from one cloth seam, not by expected cell size.
    accepted=[]
    for p in sorted(peaks, key=lambda p: -profile[p]):
        if all(abs(p-q) > length*.025 for q in accepted): accepted.append(int(p))
    peaks=np.array(sorted(accepted))
    if len(peaks) < 3 or len(peaks) > 24: return None
    best=None
    for start,stop in zip(peaks[:-1],peaks[1:]):
        step=float(stop-start)
        if not length*.06 < step < length*.45: continue
        indexes=np.rint((peaks-start)/step).astype(int)
        residual=abs(peaks-(start+indexes*step))/step
        good=residual < .09
        positions=peaks[good]; ids=indexes[good]
        if len(positions) < 3 or len(set(ids)) != len(ids): continue
        if np.any(np.diff(ids) != 1): continue
        origin,spacing=np.linalg.lstsq(np.column_stack([np.ones(len(ids)),ids]),positions,rcond=None)[0]
        if (positions[-1]-positions[0])/length < .45: continue
        lines=list(origin+np.arange(ids[0],ids[-1]+1)*spacing)
        # An outer line is admitted only when its pixels support the extrapolation.
        for side in (-1,1):
            expected=lines[0]-spacing if side < 0 else lines[-1]+spacing
            radius=max(2,round(spacing*.10))
            a=max(1,round(expected)-radius); b=min(length-1,round(expected)+radius+1)
            if b <= a: continue
            p=a+int(np.argmax(profile[a:b]))
            if profile[p] < max(floor+2*mad,float(profile.max())*.20): continue
            if side < 0: lines.insert(0,float(p))
            else: lines.append(float(p))
        coverage=(lines[-1]-lines[0])/length
        if coverage < .72 or len(lines) < 4: continue
        # More observed span beats an equally tidy subset of the same partition.
        rank=(coverage, len(positions), -float(np.mean(residual[good])))
        if best is None or rank > best[0]: best=(rank,tuple(lines))
    return None if best is None else best[1]


def infer_seam_grid(image):
    h,w=image.shape[:2]
    if min(h,w) < 100: return None
    scale=min(1.,POLICY.max_scene_side/max(h,w))
    small=cv2.resize(image,(round(w*scale),round(h*scale)))
    lab=cv2.cvtColor(small,cv2.COLOR_BGR2LAB).astype(np.float32)
    passes=[]
    for fraction in (.006,.009):
        smooth=cv2.GaussianBlur(lab,(0,0),max(1.,min(small.shape[:2])*fraction))
        axes=[]
        for axis in (1,0):
            change=np.linalg.norm(np.diff(smooth,axis=axis),axis=2)
            lines=_axis_lines(np.percentile(change,50,axis=1-axis))
            if lines is None: return None
            axes.append(lines)
        passes.append(axes)
    for a,b in zip(*passes):
        if len(a)!=len(b) or np.max(abs(np.array(a)-b)) > np.median(np.diff(a))*.08:
            return None
    xs,ys=passes[0]
    if (len(xs)-1)*(len(ys)-1)>150: return None
    return PanelGrid(tuple(v/scale for v in xs),tuple(v/scale for v in ys),
                     .92,'seam_consensus')
