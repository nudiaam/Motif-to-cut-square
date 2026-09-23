"""Local segmentation with revisable context and explicit background evidence."""
import cv2
import numpy as np

from .scene_profile import POLICY, background_evidence


def segment_zone(image, minimum_area, core_bounds, *, shadow_gain=1., background_model=None):
    h,w=image.shape[:2]
    scale=min(1.,POLICY.max_region_side/max(h,w))
    size=(max(1,round(w*scale)),max(1,round(h*scale)))
    small=cv2.resize(image,size,interpolation=cv2.INTER_AREA) if scale < 1 else image
    core=tuple(round(v*scale) for v in core_bounds)
    left,top,right,bottom=core
    if min(right-left,bottom-top) < 8:return None
    evidence=background_evidence(small,core)
    if evidence is not None and background_model is not None:
        colour,noise=(np.asarray(v,np.float32) for v in background_model)
        lab=cv2.GaussianBlur(cv2.cvtColor(small,cv2.COLOR_BGR2LAB).astype(np.float32),(0,0),1.)
        distance=10*np.linalg.norm((lab-colour)/noise,axis=2)
        safe=(evidence['sample_sides']>0)&(distance<20)
        evidence['distance']=distance
        evidence['safe_background']=safe
        evidence['stats']['foreground_threshold']=35.
        evidence['stats']['background_reliable']=bool(safe.sum()>=8 and
            len(np.unique(evidence['sample_sides'][safe]))>=2)
        evidence['stats']['shared_background_used']=True
    if evidence is None or not evidence['stats']['background_reliable']:return None
    distance=evidence['distance'];threshold=evidence['stats']['foreground_threshold']
    mask=np.full(small.shape[:2],cv2.GC_PR_BGD,np.uint8)
    inside=np.zeros(mask.shape,bool);inside[top:bottom,left:right]=True
    mask[(distance > threshold)&inside]=cv2.GC_PR_FGD
    # Background seeds live inside the owning cell, not solely on the rim of
    # a context window whose colours may belong to different neighbours.
    mask[evidence['safe_background']]=cv2.GC_BGD
    if np.count_nonzero(mask==cv2.GC_PR_FGD) < max(4,minimum_area*scale*scale):return None
    pixels=small
    if shadow_gain > 1.:
        lab=cv2.cvtColor(small,cv2.COLOR_BGR2LAB)
        lab[...,0]=np.clip(lab[...,0].astype(np.float32)*shadow_gain,0,255).astype(np.uint8)
        pixels=cv2.cvtColor(lab,cv2.COLOR_LAB2BGR)
    bg,fg=np.zeros((1,65),np.float64),np.zeros((1,65),np.float64)
    cv2.setRNGSeed(0)
    cv2.grabCut(pixels,mask,None,bg,fg,3,cv2.GC_INIT_WITH_MASK)
    selected=np.isin(mask,(cv2.GC_FGD,cv2.GC_PR_FGD))
    if background_model is not None:
        # GrabCut can absorb a thin, weakly coloured stem into its background
        # mixture. Retain colour evidence connected to an accepted composition;
        # isolated texture specks cannot extend its bounds just by crossing a
        # threshold. This uses the original context, not a crop of its current box.
        supported=selected | ((distance > threshold)&inside)
        n,components,_,_=cv2.connectedComponentsWithStats(supported.astype(np.uint8))
        anchors=np.bincount(components[selected],minlength=n)
        connected=anchors>=4;connected[0]=False
        selected=connected[components]
    count,labels,stats,_=cv2.connectedComponentsWithStats(selected.astype(np.uint8))
    support=np.bincount(labels[inside],minlength=count)
    keep=(support >= np.maximum(4,stats[:,cv2.CC_STAT_AREA]*.55))
    keep[0]=False
    selected=keep[labels]
    area=int(selected.sum())
    if area < minimum_area*scale*scale or area > inside.sum()*.70:return None
    ys,xs=np.nonzero(selected)
    x,y,x1,y1=xs.min(),ys.min(),xs.max()+1,ys.max()+1
    box=(int(np.floor(x/scale)),int(np.floor(y/scale)),
         int(np.ceil(x1/scale)-np.floor(x/scale)),int(np.ceil(y1/scale)-np.floor(y/scale)))
    issues=[]
    if selected[0].any() or selected[-1].any() or selected[:,0].any() or selected[:,-1].any():
        issues.append('Foreground reaches the analysis boundary')
    if np.count_nonzero(selected & ~inside) > area*.08:
        issues.append('Artwork or background continues into a neighbouring cell; check ownership')
    return {'box':box,'area':int(area/(scale*scale)),
            'score':float(np.clip(np.median(distance[selected])/80,.15,.95)),
            'issues':tuple(issues),'measurements':evidence['stats']}
