"""Independent luminance-and-colour evidence for preserving known compositions.

Geometry may change ownership and merge fragments, but cannot certify itself by
retaining only its own preferred contrast channel. Unreliable backgrounds return
no verdict, leaving the established texture and spanning-artwork checks active.
"""
import cv2
import numpy as np
from .contrast_grid import _shared_background
from .pattern_grid import _cloth_mask


def foreground_mask(image):
    cloth=_cloth_mask(image)
    if not np.any(cloth):return None
    x,y,w,h=cv2.boundingRect(cloth)
    lab=cv2.GaussianBlur(cv2.cvtColor(image,cv2.COLOR_BGR2LAB).astype(np.float32),(0,0),1.)
    model=_shared_background(lab[y:y+h,x:x+w])
    if model is None:return None
    colour,noise=model
    # A dominant global colour can still coexist with broad shadows. Compare
    # recurring local background modes before interpreting their luminance
    # difference as ink; uncertain fields retain the established local routes.
    levels=[]
    crop=lab[y:y+h,x:x+w]
    for row in np.array_split(crop,4,axis=0):
        for part in np.array_split(row,4,axis=1):
            local=_shared_background(part)
            if local is not None and np.linalg.norm(local[0][1:]-colour[1:])<6:
                levels.append(local[0][0])
    if len(levels)>=6 and np.ptp(np.percentile(levels,[15,85]))>max(18.,noise[0]*3):
        return None
    signal=10*np.linalg.norm((lab-colour)/noise,axis=2)
    mask=((signal>35)&(cloth>0)).astype(np.uint8)
    count,labels,stats,_=cv2.connectedComponentsWithStats(mask)
    keep=np.zeros(count,bool)
    for i in range(1,count):
        bx,by,bw,bh,area=stats[i]
        if area>=max(8,image.shape[0]*image.shape[1]*.00005) and bw<w*.8 and bh<h*.8:
            keep[i]=True
    return keep[labels]


def preservation(reference,candidates,mask,tolerance=3):
    """Every reference composition must retain its ink in one owning result.

    Several input fragments may share an output; one input may not be split over
    outputs. Bounding-box padding only tolerates subpixel/threshold differences.
    """
    if mask is None:return None
    ih,iw=mask.shape
    integral=cv2.integral(mask.astype(np.uint8))
    def ink(left,top,right,bottom):
        left,top=max(0,int(left)),max(0,int(top))
        right,bottom=min(iw,int(right)),min(ih,int(bottom))
        if right<=left or bottom<=top:return 0
        return int(integral[bottom,right]-integral[top,right]-integral[bottom,left]+integral[top,left])
    retained=[];counts=[]
    for c in reference:
        x,y,w,h=c.bounding_box_px
        if w>iw*.8 or h>ih*.8:continue
        at_edge=(x<=0 or y<=0 or x+w>=iw or y+h>=ih or c.source_incomplete)
        total=w*h if at_edge else ink(x,y,x+w,y+h)
        if total<20:continue
        overlaps=[]
        for output in candidates:
            bx,by,bw,bh=output.bounding_box_px
            left,top=max(x,bx-tolerance),max(y,by-tolerance)
            right,bottom=min(x+w,bx+bw+tolerance),min(y+h,by+bh+tolerance)
            overlaps.append(max(0,right-left)*max(0,bottom-top) if at_edge else ink(left,top,right,bottom))
        retained.append(max(overlaps,default=0)/total);counts.append(total)
    if not retained:return None
    lost=[i for i,fraction in enumerate(retained) if fraction<.98]
    return {'approved':not lost,'reference_compositions':len(retained),
            'lost_compositions':lost,'minimum_ink_retained':float(min(retained)),
            'ink_retained_fraction':float(np.average(retained,weights=counts))}
