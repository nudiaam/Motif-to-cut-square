"""Separate a printed section's composition from weave, rules and illumination.

The printed divisions own the composition. Two independent foreground readings
retain detached details; neither cut size nor motif centre is an input.
"""
import cv2
import numpy as np
from .region_analysis import segment_zone


def _diffuse_texture_only(ink,core):
    """Abstain on dispersed tiny weave fragments after rules are removed.

    This is only a veto for a failed silhouette reading. A coherent faint
    component is retained irrespective of its absolute colour contrast.
    """
    left,top,right,bottom=core;crop=ink[top:bottom,left:right]
    height,width=crop.shape[:2]
    n,_,stats,_=cv2.connectedComponentsWithStats(crop.astype(np.uint8))
    if n<9:return False
    for x,y,w,h,area in stats[1:]:
        if min(w,h)>=min(width,height)*.12 and area>=width*height*.001:
            return False
    occupied=sum(bool(part.any()) for row in np.array_split(crop,3,axis=0)
                 for part in np.array_split(row,3,axis=1))
    return occupied>=6


def segment_printed_composition(image,core):
    left,top,right,bottom=core;cw,ch=right-left,bottom-top
    if min(cw,ch)<12:
        return None
    # A smoothed colour reading avoids making individual weave threads into
    # foreground classes. The original reading remains available for fine parts.
    original=segment_zone(image,20,core,preserve_detached=True,include_mask=True)
    smooth=cv2.GaussianBlur(image,(0,0),1.2)
    inset=max(2,round(min(cw,ch)*.065))
    rect=(left+inset,top+inset,cw-2*inset,ch-2*inset)
    mask=np.zeros(image.shape[:2],np.uint8)
    bg,fg=np.zeros((1,65),float),np.zeros((1,65),float)
    cv2.setRNGSeed(0)
    cv2.grabCut(smooth,mask,rect,bg,fg,8,cv2.GC_INIT_WITH_RECT)
    selected=np.isin(mask,(cv2.GC_FGD,cv2.GC_PR_FGD))
    n,labels,stats,_=cv2.connectedComponentsWithStats(selected.astype(np.uint8))
    keep=(stats[:,cv2.CC_STAT_AREA]>=max(8,cw*ch*.001));keep[0]=False
    selected=keep[labels]
    silhouette=selected.copy()
    corroborated=np.zeros(selected.shape,bool)
    if original is not None:
        ink=original['foreground_mask'].astype(np.uint8)
        yy,xx=np.indices(ink.shape)
        rim=(abs(xx-left)<cw*.06)|(abs(xx-(right-1))<cw*.06)|(
            abs(yy-top)<ch*.06)|(abs(yy-(bottom-1))<ch*.06)
        # Remove sustained rules before grouping: a weave bridge can otherwise
        # join a thin frame to a real body and give it the entire cell's bounds.
        horizontal=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((1,max(8,round(cw*.60))),np.uint8))
        vertical=cv2.morphologyEx(ink,cv2.MORPH_OPEN,np.ones((max(8,round(ch*.60)),1),np.uint8))
        rules=cv2.dilate(((horizontal|vertical)>0).astype(np.uint8)*rim.astype(np.uint8),np.ones((3,3),np.uint8))>0
        ink[rules]=0
        n,labels,stats,_=cv2.connectedComponentsWithStats(ink)
        rim_support=np.bincount(labels[rim],minlength=n)
        radius=max(2,round(min(cw,ch)*.05))
        nearby=cv2.dilate(selected.astype(np.uint8),np.ones((2*radius+1,2*radius+1),np.uint8))>0
        nearby_support=np.bincount(labels[nearby],minlength=n)
        for i,(x,y,w,h,area) in enumerate(stats[1:],1):
            # A large bounding box alone is not a frame: real flowers can fill
            # most of their section. Require foreground pixels on its border.
            frame=w>cw*.65 and h>ch*.65 and rim_support[i]>area*.45
            rule=((w>cw*.70 and h<ch*.07) or (h>ch*.70 and w<cw*.07)) and rim_support[i]>area*.5
            if frame or rule:
                continue
            # Keep fine independent parts too. A small leaf is not disposable
            # simply because the main body has much more foreground area.
            substantial=area>=cw*ch*.003 and w*h>=cw*ch*.02
            connected=nearby_support[i]>=max(4,area*.05)
            if area>=max(4,cw*ch*.0004) and (substantial or connected):
                selected|=labels==i
                corroborated|=(labels==i)&silhouette
    if selected.sum()<max(20,cw*ch*.025):
        # A failed silhouette reading cannot certify that the pale body vanished.
        # Keep the original extent and expose the uncertainty for inspection.
        if original is None:
            return None
        if _diffuse_texture_only(ink,core):
            return None
        return {**original,'issues':(*original['issues'],'Fine artwork extent is uncertain; inspect its complete outline'),
                'extent_checked':True,'extent_uncertain':True,'support_contours':()}
    ys,xs=np.nonzero(selected);x,y=int(xs.min()),int(ys.min());x1,y1=int(xs.max()+1),int(ys.max()+1)
    issues=[]
    inside=smooth[top:bottom,left:right]
    gray=cv2.cvtColor(inside,cv2.COLOR_BGR2GRAY)
    chroma=cv2.cvtColor(inside,cv2.COLOR_BGR2LAB)[:,:,1:]
    chroma_range=np.ptp(np.percentile(chroma,[5,95],axis=(0,1)),axis=0)
    sparse_extent=(x1-x)<cw*.60 or (y1-y)<ch*.60
    chroma_contrast=np.linalg.norm(chroma_range)
    weak_extent=(sparse_extent and chroma_contrast<16.) or (
        np.ptp(np.percentile(gray,[10,90]))<28. and chroma_contrast<12.)
    if weak_extent:
        # Colour mixtures can erase pale ears while retaining a strong body,
        # especially after downsampling. Preserve independent weak ink and
        # expose ambiguity instead of silently certifying that smaller box.
        from .printed_partition import include_faint_ink
        prior=(x,y,x1-x,y1-y)
        if original is not None:
            ox,oy,ow,oh=original['box']
            x,y,x1,y1=min(x,ox),min(y,oy),max(x1,ox+ow),max(y1,oy+oh)
        checked=include_faint_ink(image,(x,y,x1-x,y1-y),core_bounds=core)
        if max(abs(a-b) for a,b in zip(checked,prior))>min(cw,ch)*.03:
            issues.append('Fine artwork extent is uncertain; inspect its complete outline')
        x,y,bw,bh=checked;x1,y1=x+bw,y+bh
    # The second reading includes real parts outside the rectangle initialization:
    # it is context, not an irreversible clipping boundary.
    if x<=0 or y<=0 or x1>=image.shape[1] or y1>=image.shape[0]:
        issues.append('Foreground reaches the analysis boundary; inspect complete artwork')
    # Keep the conservative extent for inspection, but do not call uncertain
    # background outside it a proven cut through artwork. Only ink supported by
    # both readings establishes a definite clipping conflict in that case.
    support_contours=[]
    n,labels,stats,_=cv2.connectedComponentsWithStats(corroborated.astype(np.uint8))
    for i,(bx,by,bw,bh,area) in enumerate(stats[1:],1):
        if area<max(4,cw*ch*.0004):
            continue
        component=(labels[by:by+bh,bx:bx+bw]==i).astype(np.uint8)
        contours,_=cv2.findContours(component,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE,
                                   offset=(int(bx),int(by)))
        support_contours.extend(tuple(tuple(int(v) for v in point) for point in contour[:,0,:])
                                for contour in contours)
    uncertain=bool(issues) or not support_contours
    if support_contours:
        points=np.asarray([p for contour in support_contours for p in contour],np.int32)
        sx,sy,sw,sh=cv2.boundingRect(points)
        uncertain|=max(abs(a-b) for a,b in zip((x,y,x1-x,y1-y),(sx,sy,sw,sh)))>min(cw,ch)*.04
        uncertain|=corroborated.sum()<selected.sum()*.5
    if uncertain:
        issues.append('Artwork outline is uncertain; check faint details and background')
    return {'box':(x,y,x1-x,y1-y),'area':int(selected.sum()),'score':.85,
            'issues':tuple(dict.fromkeys(issues)),'extent_checked':True,
            'extent_uncertain':bool(uncertain),'support_contours':tuple(support_contours)}
