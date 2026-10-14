"""Compare repeated primary marks and accessory clusters on an accepted grid.

This bounded proposal is limited to unprinted automatic fields. It does not
recognise digits or prescribe a number of groups. Tall anchors define spacing;
low-contrast parts independently define complete composition bounds.
"""
import cv2
import numpy as np
from .contrast_grid import _shared_background
from .pattern_grid import _cloth_mask
from .logical_layout import LayoutObservation,fit_logical_layout,layout_from_panel_grid
from .hierarchical_compositions import resolve_composition_readings
from .detection_plan import grid_evidence


def infer_compound_grid(image,current):
    result=_infer_compound_grid(image,current)
    if result is not None:return result
    grid=current.panel_grid
    if (grid is None or grid.source in ('manual','visual','camera','reference')
            or min(grid.columns,grid.rows)<3 or any(c.source_incomplete for c in current.candidates)):
        return None
    from .bed_reference import locate_bright_fabric
    from .scene_profile import illumination_view
    from .detection_plan import grid_distance
    mask=locate_bright_fabric(image).mask
    if mask is None or illumination_view(image,mask) is None:return None
    _,_,w,h=cv2.boundingRect(mask);gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32)
    readings=[]
    for fraction in (.15,.20):
        size=round(min(w,h)*fraction)|1
        field=cv2.morphologyEx(gray,cv2.MORPH_CLOSE,np.ones((size,size),np.uint8))
        field=cv2.GaussianBlur(field,(0,0),min(w,h)*.025)
        target=np.percentile(field[mask>0],85)
        view=np.clip(image.astype(np.float32)*np.clip(target/np.maximum(field,30),.75,1.8)[:,:,None],0,255).astype(np.uint8)
        proposal=_infer_compound_grid(view,current)
        if proposal is None:return None
        readings.append(proposal)
    if grid_distance(readings[0][0],readings[1][0])>=.10:return None
    grid,groups,diagnostics=readings[0]
    return grid,groups,{**diagnostics,'illumination_compensated':True,'illumination_readings':2}


def _infer_compound_grid(image,current):
    grid=current.panel_grid
    if (grid is None or grid.source in ('manual','visual','camera','reference')
            or min(grid.columns,grid.rows)<3 or grid.projection is not None
            or any(c.source_incomplete for c in current.candidates)):
        return None
    support=grid_evidence(image,grid,current.candidates)
    # Printed boundaries are independent evidence, not accessory spacing.
    if support['seam_support']>.20 or support['occupied_fraction']<.85:return None
    ih,iw=image.shape[:2]
    if min(ih,iw)<120:return None
    scale=960/max(ih,iw)
    small=cv2.resize(image,(round(iw*scale),round(ih*scale)),interpolation=cv2.INTER_AREA)
    cloth=_cloth_mask(small)
    if not np.any(cloth):return None
    x,y,w,h=cv2.boundingRect(cloth)
    lab=cv2.GaussianBlur(cv2.cvtColor(small,cv2.COLOR_BGR2LAB).astype(np.float32),(0,0),1.)
    model=_shared_background(lab[y:y+h,x:x+w])
    if model is None:return None
    colour,noise=model;signal=10*np.linalg.norm((lab-colour)/noise,axis=2)
    def parts_at(threshold):
        _,_,stats,_=cv2.connectedComponentsWithStats(((signal>threshold)&(cloth>0)).astype(np.uint8))
        return np.asarray([s for s in stats[1:] if
            small.shape[0]*small.shape[1]*.00008<=s[4]<w*h*.12
            and s[2]<w*.4 and s[3]<h*.4])
    complete=parts_at(55)
    if not 30<=len(complete)<=600:return None
    pitch=np.median(np.diff(grid.y_lines_px))*scale
    fine=layout_from_panel_grid([],grid)
    def owners(parts):
        return np.asarray([np.floor(np.asarray(fine.coordinates(
            (p[0]+p[2]/2)/scale,(p[1]+p[3]/2)/scale))+.5).astype(int) for p in parts])
    # Repeated roles are required independently of any proposed coarsening.
    # A large drawing beside one small drawing is insufficient evidence.
    role_readings=[];part_readings={}
    for threshold in (75,95,115,135):
        parts=parts_at(threshold);part_readings[threshold]=parts
        if not len(parts):continue
        cells=owners(parts);primary=np.zeros((grid.rows,grid.columns),bool);clusters=primary.copy()
        for row in range(grid.rows):
            for column in range(grid.columns):
                selected=parts[np.all(cells==[column,row],axis=1)]
                tall=np.count_nonzero(selected[:,3]>pitch*.45) if len(selected) else 0
                short=np.count_nonzero(selected[:,3]<pitch*.30) if len(selected) else 0
                primary[row,column]=tall>=1 and short<=2
                clusters[row,column]=short>=3
        anchor_columns=np.flatnonzero((primary.mean(axis=0)>=.75)&(clusters.mean(axis=0)<=.25))
        if len(anchor_columns)<3:continue
        intervals=np.diff(anchor_columns)
        if not np.all(intervals==intervals[0]) or not 2<=intervals[0]<=4:continue
        period=int(intervals[0])
        if anchor_columns[0]!=0 or len(anchor_columns)*period!=grid.columns:continue
        accessory_columns=np.setdiff1d(np.arange(grid.columns),anchor_columns)
        if (np.mean(clusters[:,accessory_columns])<.65
                or np.any(clusters[:,accessory_columns].mean(axis=0)<.25)
                or np.mean(primary[:,accessory_columns])>.35):continue
        role_readings.append((threshold,period,len(anchor_columns)))
    if len(role_readings)<2:return None
    dimensions={(period,count) for _,period,count in role_readings}
    if len(dimensions)!=1:return None
    period,columns=next(iter(dimensions))
    cells=owners(complete);bounds={}
    for row in range(grid.rows):
        for column in range(grid.columns):
            selected=complete[np.all(cells==[column,row],axis=1)]
            if len(selected):bounds[column,row]=(selected[:,:2].min(axis=0),
                (selected[:,:2]+selected[:,2:4]).max(axis=0))
    inner=[];outer=[]
    for row in range(grid.rows):
        for column in range(0,grid.columns-period,period):
            a=bounds.get((column,row));b=bounds.get((column+period-1,row));c=bounds.get((column+period,row))
            if a is not None and b is not None and c is not None:
                inner.append(max(0,b[0][0]-a[1][0]));outer.append(max(0,c[0][0]-b[1][0]))
    if (len(inner)<grid.rows*2 or np.median(inner)>=np.median(outer)*.80
            or np.mean(np.asarray(inner)<np.asarray(outer))<.65):return None
    readings=[]
    for threshold in (75,95,115,135):
        parts=part_readings[threshold]
        if not len(parts):continue
        for fraction in (.45,.50,.55):
            anchors=parts[parts[:,3]>pitch*fraction]
            if len(anchors)<6:continue
            layout=fit_logical_layout([LayoutObservation(i,(x+bw/2,y+bh/2),(x,y,bw,bh))
                for i,(x,y,bw,bh,_) in enumerate(anchors)])
            matched=sum(m.status=='matched' for m in layout.matches)/len(anchors)
            if (layout.confidence<.85 or layout.occupancy<.90 or matched<.80
                    or layout.rows!=grid.rows or layout.columns!=columns
                    or len(complete)<layout.columns*layout.rows*2):continue
            readings.append((layout,threshold,fraction,complete))
    if not readings:return None
    proposal=resolve_composition_readings(readings,scale,small.shape[:2])
    if proposal is None:return None
    proposed,groups,diagnostics=proposal
    fractions=diagnostics.pop('area_quantiles')
    return proposed,groups,{**diagnostics,'anchor_metric':'height_relative_to_row_pitch',
        'height_fractions':fractions,'previous_columns':grid.columns,
        'previous_rows':grid.rows,'previous_seam_support':support['seam_support'],
        'role_readings':len(role_readings),'role_period':period,
        'within_group_gap_px':float(np.median(inner)/scale),
        'between_group_gap_px':float(np.median(outer)/scale)}
