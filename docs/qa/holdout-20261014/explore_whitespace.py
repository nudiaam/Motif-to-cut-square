"""Explore bounded whole-ink grouping scales on all five holdout originals."""
from pathlib import Path
import json,cv2,numpy as np
from app.imaging.pattern_grid import _cloth_mask
from app.imaging.contrast_grid import _shared_background
from app.imaging.logical_layout import LayoutObservation,fit_logical_layout

ROOT=Path('docs/qa/holdout-20261014');records=[]
for path in ROOT.glob('*.png'):
    image=cv2.imread(str(path));scale=960/max(image.shape[:2]);small=cv2.resize(image,None,fx=scale,fy=scale)
    cloth=_cloth_mask(small);x,y,w,h=cv2.boundingRect(cloth)
    lab=cv2.GaussianBlur(cv2.cvtColor(small,cv2.COLOR_BGR2LAB).astype(np.float32),(0,0),.8)
    model=_shared_background(lab[y:y+h,x:x+w])
    if model is None:print(path.stem,'NO SHARED',flush=True);continue
    bg,noise=model;signal=10*np.linalg.norm((lab-bg)/noise,axis=2)
    found=[]
    for t in (35,45,55):
        ink=((signal>t)&(cloth>0)).astype(np.uint8)
        n,labels,stats,_=cv2.connectedComponentsWithStats(ink);keep=np.zeros(n,bool)
        for i,s in enumerate(stats[1:],1):
            keep[i]=s[4]>=ink.size*.00008 and s[2]<w*.6 and s[3]<h*.6
        ink=keep[labels].astype(np.uint8)
        for kx in (9,15,21,27,33,39,45,51):
            for ky in (9,15,21,27,33):
                closed=cv2.morphologyEx(ink,cv2.MORPH_CLOSE,np.ones((ky,kx),np.uint8))
                n,labels,stats,_=cv2.connectedComponentsWithStats(closed);boxes=[];areas=[]
                for i in range(1,n):
                    ys,xs=np.nonzero((labels==i)&(ink>0))
                    if len(xs)<max(25,ink.size*.0003):continue
                    box=(int(xs.min()),int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1));boxes.append(box);areas.append(len(xs))
                if not 6<=len(boxes)<=80:continue
                layout=fit_logical_layout([LayoutObservation(i,(x+w/2,y+h/2),b) for i,b in enumerate(boxes) for x,y,w,h in [b]])
                support=sum(m.status=='matched' for m in layout.matches)/len(boxes)
                if layout.confidence>=.85 and layout.occupancy>=.9 and support>=.95 and len(boxes)==layout.columns*layout.rows:
                    found.append({'threshold':t,'kernel':[kx,ky],'shape':[layout.columns,layout.rows],'count':len(boxes),'confidence':layout.confidence,'boxes':boxes})
    records.append({'file':path.stem,'proposals':found})
    summary={}
    for p in found:summary.setdefault(tuple(p['shape']),[]).append((p['threshold'],p['kernel']))
    print(path.stem,{str(k):len(v) for k,v in summary.items()}, {str(k):v[:6] for k,v in summary.items()},flush=True)
    (ROOT/'whitespace-prototypes.json').write_text(json.dumps(records,indent=2))
