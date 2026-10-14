"""Propose whole-group spacing from stable whitespace at several ink scales.

Geometry is inferred before assigning all source components. No expected group
count, symbol class, or selected cut size enters the proposal.
"""
import cv2
import numpy as np
from .contrast_grid import _shared_background
from .pattern_grid import _cloth_mask
from .logical_layout import LayoutObservation,fit_logical_layout,layout_from_panel_grid
from .panel_grid import PanelGrid
from .detection_plan import grid_distance


def infer_ink_lattice(image):
    result=_infer_ink_lattice(image)
    if result is not None:return result
    from .bed_reference import locate_bright_fabric
    from .scene_profile import illumination_view
    mask=locate_bright_fabric(image).mask
    if mask is None or illumination_view(image,mask) is None:return None
    _,_,w,h=cv2.boundingRect(mask);gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32)
    readings=[]
    for fraction in (.15,.20):
        size=round(min(w,h)*fraction)|1
        field=cv2.morphologyEx(gray,cv2.MORPH_CLOSE,np.ones((size,size),np.uint8))
        field=cv2.GaussianBlur(field,(0,0),min(w,h)*.025)
        gain=np.clip(np.percentile(field[mask>0],85)/np.maximum(field,30),.75,1.8)
        proposal=_infer_ink_lattice(np.clip(image.astype(np.float32)*gain[:,:,None],0,255).astype(np.uint8))
        if proposal is None:return None
        readings.append(proposal)
    if grid_distance(readings[0][0],readings[1][0])>=.08:return None
    grid,groups,support,ink=readings[0]
    return grid,groups,{**support,'illumination_compensated':True,'illumination_readings':2},ink|readings[1][3]


def _infer_ink_lattice(image):
    ih,iw=image.shape[:2]
    if min(ih,iw)<120:return None
    scale=960/max(ih,iw);small=cv2.resize(image,(round(iw*scale),round(ih*scale)),interpolation=cv2.INTER_AREA)
    cloth=_cloth_mask(small)
    if not np.any(cloth):return None
    level=float(np.percentile(cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)[cloth>0],85))
    if 80<level<190:
        # Uniform exposure is an analysis property, not a different cut layout.
        small=np.clip(small.astype(np.float32)*(220/level),0,255).astype(np.uint8)
    fx,fy,fw,fh=cv2.boundingRect(cloth)
    lab=cv2.GaussianBlur(cv2.cvtColor(small,cv2.COLOR_BGR2LAB).astype(np.float32),(0,0),.8)
    model=_shared_background(lab[fy:fy+fh,fx:fx+fw])
    if model is None:return None
    colour,noise=model;signal=10*np.linalg.norm((lab-colour)/noise,axis=2)
    readings=[];masks={};base_parts={}
    for threshold in (35,45,55):
        mask=((signal>threshold)&(cloth>0)).astype(np.uint8)
        count,labels,stats,_=cv2.connectedComponentsWithStats(mask);keep=np.zeros(count,bool)
        for i,s in enumerate(stats[1:],1):
            x,y,w,h,area=s
            strong=np.count_nonzero((labels[y:y+h,x:x+w]==i)&(signal[y:y+h,x:x+w]>75))
            keep[i]=(area>=mask.size*.00008 and w<fw*.6 and h<fh*.6
                and strong>=max(4,area*.10))
        mask=keep[labels].astype(np.uint8);masks[threshold]=mask
        base_parts[threshold]=stats[np.flatnonzero(keep)]
        for kx in (9,15,21,27,33,39,45,51):
            for ky in (9,15,21,27,33):
                closed=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((ky,kx),np.uint8))
                n,labels,stats,_=cv2.connectedComponentsWithStats(closed);boxes=[]
                for i,(x,y,w,h,_) in enumerate(stats[1:],1):
                    ys,xs=np.nonzero((labels[y:y+h,x:x+w]==i)&(mask[y:y+h,x:x+w]>0))
                    if len(xs)<max(25,mask.size*.0003):continue
                    boxes.append((x+int(xs.min()),y+int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)))
                if not 6<=len(boxes)<=100:continue
                layout=fit_logical_layout([LayoutObservation(i,(x+w/2,y+h/2),(x,y,w,h)) for i,(x,y,w,h) in enumerate(boxes)])
                matched=sum(m.status=='matched' for m in layout.matches)/len(boxes)
                if (layout.confidence<.88 or layout.occupancy<.90 or matched<.80
                        or len(boxes)<layout.columns*layout.rows or min(layout.columns,layout.rows)<2):continue
                readings.append((layout,threshold,kx,ky))
    best=None
    for layout,threshold,kx,ky in readings:
        pitch=min(np.linalg.norm(layout.column_vector_px),np.linalg.norm(layout.row_vector_px))
        corners=((0,0),(layout.columns-1,0),(0,layout.rows-1),(layout.columns-1,layout.rows-1))
        peers=[r for r in readings if (r[0].columns,r[0].rows)==(layout.columns,layout.rows)
            and max(np.linalg.norm(np.asarray(layout.position(c,y))-r[0].position(c,y)) for c,y in corners)<pitch*.08]
        if len({r[1] for r in peers})<2 or len({(r[2],r[3]) for r in peers})<3:continue
        origin=np.asarray(layout.origin_px);col=np.asarray(layout.column_vector_px);row=np.asarray(layout.row_vector_px)
        # Recover bounds at the same independent foreground readings. Keep
        # complete components; a proposed boundary cannot cut through known ink.
        groups=[];valid=True;retentions=[]
        for t in (45,55):
            parts=base_parts[t]
            if not len(parts):valid=False;break
            centres=parts[:,:2]+parts[:,2:4]/2
            logical=(centres-origin)@np.linalg.inv(np.column_stack([col,row])).T
            cells=np.floor(logical+.5).astype(int)
            inside=(cells[:,0]>=0)&(cells[:,0]<layout.columns)&(cells[:,1]>=0)&(cells[:,1]<layout.rows)
            if not np.all(inside):valid=False;break
            lo=parts[:,:2];hi=lo+parts[:,2:4]
            corners_px=np.stack([lo,hi,np.column_stack([lo[:,0],hi[:,1]]),np.column_stack([hi[:,0],lo[:,1]])],axis=1)
            coords=(corners_px-origin)@np.linalg.inv(np.column_stack([col,row])).T
            contained=np.max(abs(coords-cells[:,None,:]),axis=(1,2))<=.65
            retained=float(parts[contained,4].sum()/parts[:,4].sum())
            if retained<.98 or contained.mean()<.95:valid=False;break
            retentions.append(retained);boxes=[]
            for y in range(layout.rows):
                for c in range(layout.columns):
                    selected=parts[np.all(cells==[c,y],axis=1)]
                    if not len(selected):valid=False;break
                    a=selected[:,:2].min(axis=0);b=(selected[:,:2]+selected[:,2:4]).max(axis=0)
                    boxes.append((a,b,int(selected[:,4].sum())))
                if not valid:break
            if not valid:break
            groups.append(boxes)
        if not valid:continue
        rank=(len(peers),min(retentions),layout.confidence)
        if best is None or rank>best[0]:best=(rank,layout,groups,peers,retentions)
    if best is None:return None
    _,layout,views,peers,retained=best;groups=[]
    keys=[(c,r) for r in range(layout.rows) for c in range(layout.columns)]
    for i,key in enumerate(keys):
        a=np.minimum(views[0][i][0],views[1][i][0])/scale
        b=np.maximum(views[0][i][1],views[1][i][1])/scale
        left,top=np.floor(a).astype(int);right,bottom=np.ceil(b).astype(int)
        groups.append(((int(left),int(top),int(right-left),int(bottom-top)),round(max(views[0][i][2],views[1][i][2])/scale**2)))
    # One shared lattice is fitted from full groups, never individual cut moves.
    centres=np.asarray([(x+w/2,y+h/2) for (x,y,w,h),_ in groups])
    coeff=np.linalg.lstsq(np.column_stack([np.ones(len(keys)),np.asarray(keys)]),centres,rcond=None)[0]
    origin,col,row=coeff
    grid=PanelGrid(tuple(origin[0]+(c-.5)*col[0]+(layout.rows-1)*row[0]/2 for c in range(layout.columns+1)),
        tuple(origin[1]+(r-.5)*row[1]+(layout.columns-1)*col[1]/2 for r in range(layout.rows+1)),
        float(layout.confidence),'ink_lattice',(tuple(origin),tuple(col),tuple(row)))
    return grid,tuple((box,area,tuple(origin+c*col+r*row)) for (box,area),(c,r) in zip(groups,keys)),{
        'method':'multiscale_whitespace','agreeing_readings':len(peers),
        'thresholds':sorted({r[1] for r in peers}),'horizontal_scales':sorted({r[2] for r in peers}),
        'vertical_scales':sorted({r[3] for r in peers}),'retained_ink_fraction':min(retained),
        'exposure_gain':220/level if 80<level<190 else 1.},cv2.resize(
            masks[45]|masks[55],(iw,ih),interpolation=cv2.INTER_NEAREST)>0
