"""Recover nested compositions from repeated anchors and all foreground parts.

An optional unresolved-scene route. No OCR, expected count or collection names:
several foreground/size readings must agree on anchor spacing, and a common
phase must preserve the small components across the complete image.
"""
import cv2
import numpy as np
from .contrast_grid import _shared_background
from .logical_layout import LayoutObservation, fit_logical_layout
from .panel_grid import PanelGrid
from .pattern_grid import _cloth_mask


def infer_hierarchical_compositions(image):
    result=_infer_hierarchy(image)
    if result is not None:return result
    from .bed_reference import locate_bright_fabric
    from .scene_profile import illumination_view
    from .detection_plan import grid_distance
    mask=locate_bright_fabric(image).mask
    if mask is None or illumination_view(image,mask) is None:return None
    _,_,w,h=cv2.boundingRect(mask)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32)
    readings=[]
    for fraction in (.15,.20):
        size=round(min(w,h)*fraction)|1
        field=cv2.morphologyEx(gray,cv2.MORPH_CLOSE,np.ones((size,size),np.uint8))
        field=cv2.GaussianBlur(field,(0,0),min(w,h)*.025)
        target=np.percentile(field[mask>0],85)
        gain=np.clip(target/np.maximum(field,30),.75,1.8)
        view=np.clip(image.astype(np.float32)*gain[:,:,None],0,255).astype(np.uint8)
        proposal=_infer_hierarchy(view)
        if proposal is None:return None
        readings.append(proposal)
    if grid_distance(readings[0][0],readings[1][0])>=.10:return None
    grid,groups,diagnostics=readings[0]
    return grid,groups,{**diagnostics,'illumination_compensated':True,'illumination_readings':2}


def _infer_hierarchy(image):
    ih,iw=image.shape[:2]
    scale=min(1.,960/max(ih,iw))
    small=cv2.resize(image,(round(iw*scale),round(ih*scale)),interpolation=cv2.INTER_AREA)
    cloth=_cloth_mask(small)
    if not np.any(cloth):return None
    x,y,w,h=cv2.boundingRect(cloth)
    lab=cv2.GaussianBlur(cv2.cvtColor(small,cv2.COLOR_BGR2LAB).astype(np.float32),(0,0),1.)
    model=_shared_background(lab[y:y+h,x:x+w])
    if model is None:return None
    background,noise=model
    signal=10*np.linalg.norm((lab-background)/noise,axis=2)
    readings=[]
    for threshold in (35,45,55):
        mask=((signal>threshold)&(cloth>0)).astype(np.uint8)
        _,_,stats,_=cv2.connectedComponentsWithStats(mask)
        parts=np.asarray([s for s in stats[1:] if
            small.shape[0]*small.shape[1]*.00008<=s[4]<w*h*.12
            and s[2]<w*.4 and s[3]<h*.4])
        if not 30<=len(parts)<=600:continue
        # Area scales distinguish repeated primary marks from their tiny details.
        for quantile in (.75,.80,.85,.87,.89,.91):
            anchors=parts[parts[:,4]>=np.quantile(parts[:,4],quantile)]
            layout=fit_logical_layout([LayoutObservation(i,(x+bw/2,y+bh/2),(x,y,bw,bh))
                for i,(x,y,bw,bh,_) in enumerate(anchors)])
            support=sum(m.status=='matched' for m in layout.matches)/max(1,len(anchors))
            if (layout.confidence<.80 or layout.occupancy<.85 or support<.75
                    or len(parts)<layout.columns*layout.rows*2):continue
            readings.append((layout,threshold,quantile,parts))
    return resolve_composition_readings(readings,scale,small.shape[:2])


def resolve_composition_readings(readings,scale,image_shape):
    """Compare anchor readings and retain all parts under a common geometry."""
    best=None
    for layout,threshold,quantile,parts in readings:
        pitch=min(np.linalg.norm(layout.column_vector_px),np.linalg.norm(layout.row_vector_px))
        corners=((0,0),(layout.columns-1,0),(0,layout.rows-1),(layout.columns-1,layout.rows-1))
        peers=[r for r in readings if (r[0].columns,r[0].rows)==(layout.columns,layout.rows)
            and max(np.linalg.norm(np.array(layout.position(c,rr))-r[0].position(c,rr))
                    for c,rr in corners)<pitch*.12]
        threshold_count=len({p[1] for p in peers})
        if threshold_count<2 or (len({p[2] for p in peers})<2 and threshold_count<3):continue
        # Keep all four sides of every component. Optimise shared phase, never
        # independent cut positions and never a crop that discards crossing ink.
        basis=np.column_stack([layout.column_vector_px,layout.row_vector_px])
        inverse=np.linalg.inv(basis)
        boxes=parts[:,:4].astype(float)
        lo=boxes[:,:2];hi=lo+boxes[:,2:]
        points=np.stack([lo,hi,np.column_stack([lo[:,0],hi[:,1]]),np.column_stack([hi[:,0],lo[:,1]])],axis=1)
        coords=(points-np.array(layout.origin_px))@inverse.T
        centres=coords.mean(axis=1);areas=parts[:,4]
        phase_best=None
        # Anchor centres move within their composition as primary marks change
        # width (e.g. one versus two digits). Bound a spacing refinement by ink
        # corridors rather than treating these centres as physical panel centres.
        for sx in (.96,1.,1.04,1.08):
            for sy in (.96,1.,1.04,1.08):
                ratios=np.array([sx,sy]);adjusted=coords/ratios
                for dx in np.linspace(-.45,.45,13):
                    for dy in np.linspace(-.45,.45,13):
                        phase=np.array([dx,dy]);cell=np.floor(centres/ratios-phase+.5).astype(int)
                        inside=(cell[:,0]>=0)&(cell[:,0]<layout.columns)&(cell[:,1]>=0)&(cell[:,1]<layout.rows)
                        # An owner boundary can cross a letter or a peripheral
                        # detail; retain its entire component with bounded context.
                        contained=(np.max(abs(adjusted-phase-cell[:,None,:]),axis=(1,2))<=.60)&inside
                        occupancy=len(set(map(tuple,cell[inside])))/(layout.columns*layout.rows)
                        retained=float(areas[contained].sum()/areas.sum())
                        if occupancy<.90 or retained<.97 or contained.mean()<.90:continue
                        clearance=.5-np.max(abs(adjusted-phase-cell[:,None,:]),axis=(1,2))
                        merit=retained+float(np.mean(np.clip(clearance,0,.15)))*.2-.01*np.linalg.norm(ratios-1)
                        if phase_best is None or merit>phase_best[0]:
                            phase_best=(merit,phase,cell,inside,retained,float(contained.mean()),ratios)
        if phase_best is None:continue
        rank=(len(peers),phase_best[0],layout.confidence)
        if best is None or rank>best[0]:best=(rank,layout,parts,phase_best,peers)
    if best is None:return None
    _,layout,parts,(_,phase,cells,inside,retained,part_retained,ratios),peers=best
    # Incomplete extra rows cannot be silently dropped to certify a dense grid.
    if not np.all(inside):
        outside=parts[~inside]
        # A few pixels of frame at the image edge cannot veto all compositions.
        # Meaningful outside ink still rejects this complete-layout proposal.
        border=(outside[:,0]<=0)|(outside[:,1]<=0)|(outside[:,0]+outside[:,2]>=image_shape[1])|(outside[:,1]+outside[:,3]>=image_shape[0])
        if (outside[:,4].sum()>parts[:,4].sum()*.002 or not np.all(border)
                or np.any(np.min(outside[:,2:4],axis=1)>3)):return None
    col=np.array(layout.column_vector_px)*ratios[0]/scale
    row=np.array(layout.row_vector_px)*ratios[1]/scale
    origin=np.array(layout.origin_px)/scale+phase[0]*col+phase[1]*row
    # Primary marks have unequal widths. Refit one common lattice from the
    # whole groups, then reassign their parts; do not move individual cuts.
    for _ in range(2):
        keys=sorted(set(map(tuple,cells[inside])),key=lambda cell:cell[::-1])
        centres=[]
        for key in keys:
            selected=parts[np.all(cells==key,axis=1)]
            lo=selected[:,:2].min(axis=0)/scale
            hi=(selected[:,:2]+selected[:,2:4]).max(axis=0)/scale
            centres.append((lo+hi)/2)
        coefficients=np.linalg.lstsq(np.column_stack([np.ones(len(keys)),np.asarray(keys)]),np.asarray(centres),rcond=None)[0]
        fitted_origin,fitted_col,fitted_row=coefficients
        if (abs(np.linalg.norm(fitted_col)/np.linalg.norm(col)-1)>.12
                or abs(np.linalg.norm(fitted_row)/np.linalg.norm(row)-1)>.12
                or np.linalg.norm(fitted_origin-origin)>min(np.linalg.norm(col),np.linalg.norm(row))*.35):break
        fitted_basis=np.column_stack([fitted_col,fitted_row])
        positions=(parts[:,:2]+parts[:,2:4]/2)/scale
        logical=(positions-fitted_origin)@np.linalg.inv(fitted_basis).T
        proposed=np.floor(logical+.5).astype(int)
        context=(logical[:,0]>=-.60)&(logical[:,0]<=layout.columns-.40)&(logical[:,1]>=-.60)&(logical[:,1]<=layout.rows-.40)
        # Peripheral ink may extend a little beyond the outer owner boundary.
        # Preserve it in the edge group, including its complete source bounds.
        proposed[context]=np.clip(proposed[context],[0,0],[layout.columns-1,layout.rows-1])
        proposed_inside=(proposed[:,0]>=0)&(proposed[:,0]<layout.columns)&(proposed[:,1]>=0)&(proposed[:,1]<layout.rows)
        if not np.all(proposed_inside[inside]):break
        if len(set(map(tuple,proposed[proposed_inside])))!=len(keys):break
        origin,col,row=fitted_origin,fitted_col,fitted_row
        cells,inside=proposed,proposed_inside
    grid=PanelGrid(tuple(origin[0]+(c-.5)*col[0]+(layout.rows-1)*row[0]/2 for c in range(layout.columns+1)),
        tuple(origin[1]+(r-.5)*row[1]+(layout.columns-1)*col[1]/2 for r in range(layout.rows+1)),
        layout.confidence,'local_contrast',(tuple(origin),tuple(col),tuple(row)))
    groups=[]
    for c,r in sorted(set(map(tuple,cells[inside])),key=lambda cell:cell[::-1]):
        selected=parts[np.all(cells==[c,r],axis=1)]
        left,top=selected[:,:2].min(axis=0)/scale
        right,bottom=(selected[:,:2]+selected[:,2:4]).max(axis=0)/scale
        left,top=int(np.floor(left)),int(np.floor(top))
        right,bottom=int(np.ceil(right)),int(np.ceil(bottom))
        groups.append(((left,top,right-left,bottom-top),int(selected[:,4].sum()/scale**2),
                       tuple(origin+c*col+r*row)))
    return grid,groups,{'agreeing_readings':len(peers),'thresholds':sorted({p[1] for p in peers}),
        'area_quantiles':sorted({p[2] for p in peers}),'columns':grid.columns,'rows':grid.rows,
        'foreground_parts':len(parts),'retained_ink_fraction':retained,'retained_parts_fraction':part_retained,
        'spacing_refinement':ratios.tolist(),'outside_border_parts':int(np.count_nonzero(~inside))}
