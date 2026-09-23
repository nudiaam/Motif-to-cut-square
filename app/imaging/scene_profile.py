"""Bounded, non-destructive measurements; no motif classes or collection presets."""
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class AnalysisPolicy:
    max_scene_side: int = 960
    context_fraction: float = .15
    sample_inset: float = .035
    sample_band: float = .06
    palette_radius: float = 16.
    max_background_colours: int = 4
    max_region_side: int = 320
    max_shadow_gain: float = 1.6


POLICY = AnalysisPolicy()


def illumination_view(image, fabric_mask):
    """A row-wise alternative supported by several colour-consistent strips.

    This view is never exported or used to change physical calibration. It also
    inspects rows outside a tentative bright-fabric mask, where shadows may have
    erased the apparent boundary. Dark bed pixels cannot supply cloth evidence.
    """
    if fabric_mask is None or not np.any(fabric_mask):return None
    h,w=image.shape[:2]
    x,y,cw,ch=cv2.boundingRect(fabric_mask)
    scale=min(1.,POLICY.max_scene_side/max(h,w))
    small=cv2.resize(image,(max(1,round(w*scale)),max(1,round(h*scale)))).astype(np.float32)
    left,right=round((x+cw*.08)*scale),round((x+cw*.92)*scale)
    if right-left < 40:return None
    brightness=[];chromas=[]
    for a,b in zip(np.linspace(left,right,6,dtype=int)[:-1],np.linspace(left,right,6,dtype=int)[1:]):
        strip=small[:,a:b]
        level=np.mean(strip,axis=2)
        q=np.percentile(level,70,axis=1)
        colors=[]
        for row in range(len(q)):
            pixels=strip[row][level[row] >= q[row]]
            color=np.median(pixels,axis=0)
            colors.append(color[:2]/max(1.,float(color.sum())))
        brightness.append(q);chromas.append(colors)
    brightness=np.array(brightness);chromas=np.array(chromas)
    gains=[];votes=[]
    for levels,colors in zip(brightness,chromas):
        valid=levels > 80
        if np.count_nonzero(valid) < len(levels)*.25:return None
        differences=np.linalg.norm(colors[:,None,:]-colors[None,:,:],axis=2)
        references=[];agreement=[]
        for row in range(len(levels)):
            peers=(differences[row] < .025) & valid
            agreement.append(np.count_nonzero(peers) >= max(8,len(levels)*.04))
            references.append(float(np.percentile(levels[peers],85)) if np.any(peers) else levels[row])
        ratio=np.array(references)/np.maximum(levels,1.)
        votes.append(np.array(agreement) & (levels > 55) & (ratio > 1.18))
        gains.append(ratio)
    votes=np.array(votes);gains=np.array(gains)
    accepted=(votes.sum(axis=0) >= 3) & (np.std(gains,axis=0)/np.maximum(1.,np.median(gains,axis=0)) < .12)
    accepted=cv2.morphologyEx(accepted.astype(np.uint8)[:,None],cv2.MORPH_CLOSE,
                              np.ones((max(3,round(small.shape[0]*.018)),1),np.uint8))[:,0]>0
    # Artwork can interrupt colour matches inside a coherent dark band. Extend
    # from confirmed colour matches only through a shared luminance drop, never
    # through the near-black bed or across a bright separating band.
    reference=np.array([np.percentile(v[v>80],85) for v in brightness])
    broad_gains=reference[:,None]/np.maximum(brightness,1.)
    broad=(np.median(broad_gains,axis=0)>1.18) & (np.median(brightness,axis=0)>55)
    broad &= np.std(broad_gains,axis=0)/np.maximum(1.,np.median(broad_gains,axis=0)) < .12
    count,labels,_,_=cv2.connectedComponentsWithStats(broad.astype(np.uint8)[:,None])
    supported=np.zeros(count,bool)
    for label in range(1,count):
        supported[label]=np.count_nonzero(accepted & (labels[:,0]==label)) >= max(3,small.shape[0]*.025)
    extension=supported[labels[:,0]]
    gains[:,extension]=broad_gains[:,extension]
    accepted |= extension
    # Ignore narrow printed lines, isolated folds and frame boundaries.
    count,labels,stats,_=cv2.connectedComponentsWithStats(accepted.astype(np.uint8)[:,None])
    keep=np.zeros(count,bool)
    for label in range(1,count):
        if stats[label,cv2.CC_STAT_HEIGHT] >= small.shape[0]*.07:keep[label]=True
    accepted=keep[labels[:,0]]
    if not np.any(accepted):return None
    gain=np.ones(len(accepted),np.float32)
    gain[accepted]=np.clip(np.median(gains[:,accepted],axis=0),1.,POLICY.max_shadow_gain)
    full=cv2.resize(gain[:,None],(1,h),interpolation=cv2.INTER_LINEAR)[:,0]
    corrected=np.clip(image.astype(np.float32)*full[:,None,None],0,255).astype(np.uint8)
    return corrected,{'row_gain_min':float(full.min()),'row_gain_max':float(full.max()),
                      'affected_row_fraction':float(np.mean(full>1.01)),
                      'affected_y_px':np.flatnonzero(full>1.01)[[0,-1]].tolist(),
                      'evidence':'coherent luminance drop in at least three colour-consistent strips'}


def profile_scene(image):
    h, w = image.shape[:2]
    scale = min(1., POLICY.max_scene_side / max(h, w))
    small = cv2.resize(image, (max(1, round(w*scale)), max(1, round(h*scale))))
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    gray = lab[..., 0]
    fine = np.abs(gray-cv2.GaussianBlur(gray, (0, 0), 1.2))
    return {
        'analysis_size_px': [small.shape[1], small.shape[0]],
        'source_scale': scale,
        'luminance_percentiles': np.percentile(gray, [10, 50, 90]).tolist(),
        'fine_detail_fraction': float(np.mean(fine > 5)),
        'original_preserved': True,
    }


def background_evidence(image, core_bounds=None):
    """Use multiple colours supported on separate sides of this cell.

    Context from a different cell is not silently considered the same background.
    Arrays remain local to analysis and are not included in JSON diagnostics.
    """
    h, w = image.shape[:2]
    left, top, right, bottom = core_bounds or (0, 0, w, h)
    left, top, right, bottom = max(0,left), max(0,top), min(w,right), min(h,bottom)
    span = min(right-left, bottom-top)
    inset = max(1, round(span*POLICY.sample_inset))
    band = max(1, round(span*POLICY.sample_band))
    x0, y0, x1, y1 = left+inset, top+inset, right-inset, bottom-inset
    if x1 <= x0 or y1 <= y0:
        x0,y0,x1,y1 = left,top,right,bottom
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB).astype(np.float32)
    sides = np.zeros((h,w), np.uint8)
    sides[y0:min(y0+band,y1),x0:x1] = 1
    sides[max(y0,y1-band):y1,x0:x1] = 2
    sides[y0:y1,x0:min(x0+band,x1)] = 3
    sides[y0:y1,max(x0,x1-band):x1] = 4
    samples = lab[sides > 0]
    labels = sides[sides > 0]
    if not len(samples):
        return None
    # Deterministic colour modes, bounded sample count; no random clustering.
    stride = max(1, len(samples)//1600)
    sampled, side_ids = samples[::stride], labels[::stride]
    bins, inverse, counts = np.unique((sampled/12).astype(np.int16), axis=0,
                                      return_inverse=True, return_counts=True)
    palette = []
    for index in np.argsort(-counts):
        colour = np.median(sampled[inverse == index], axis=0)
        if any(np.linalg.norm(colour-p) < POLICY.palette_radius for p in palette):
            continue
        near = np.linalg.norm(sampled-colour, axis=1) <= POLICY.palette_radius
        if near.mean() < .06 or len(np.unique(side_ids[near])) < 2:
            continue
        palette.append(np.median(sampled[near], axis=0))
        if len(palette) == POLICY.max_background_colours:
            break
    reliable = bool(palette)
    if not palette:
        palette = [np.median(sampled, axis=0)]
    distance = np.minimum.reduce([np.linalg.norm(lab-p, axis=2) for p in palette])
    noise = distance[sides > 0]
    median = float(np.median(noise))
    mad = float(np.median(abs(noise-median)))
    threshold = max(8., median+3*mad)
    # Keep the lower background modes as safe samples, never a fixed foreground.
    safe = (sides > 0) & (distance <= max(3., float(np.percentile(noise, 30))))
    coverage = float(np.mean(noise <= max(12., threshold)))
    gray = lab[...,0]
    fine = np.abs(gray-cv2.GaussianBlur(gray, (0,0), 1.2))
    core = (slice(top,bottom),slice(left,right))
    stats = {
        'background_colours': [p.tolist() for p in palette],
        'background_reliable': reliable and coverage >= .65,
        'background_coverage': coverage,
        'background_noise': median,
        'foreground_threshold': threshold,
        'contrast_p90': float(np.percentile(distance[core],90)),
        'fine_detail_fraction': float(np.mean(fine[core] > 5)),
        'background_luminance': float(np.median(samples[:,0])),
        'background_chroma': np.median(samples[:,1:],axis=0).tolist(),
    }
    return {'distance':distance, 'safe_background':safe, 'sample_sides':sides,
            'stats':stats}
