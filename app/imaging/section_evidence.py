"""Local source-pixel evidence for the extent and corners of printed sections."""
from dataclasses import replace
import cv2
import numpy as np


def _ridge_position(values, offsets, width):
    """Centre a narrow sustained ridge; comparable separate ridges abstain."""
    floor=float(np.median(values));mad=float(np.median(abs(values-floor)))
    peak=int(np.argmax(values));high=float(values[peak])
    if high < max(3.,floor+5*mad):
        return None
    threshold=floor+(high-floor)*.75
    left=right=peak
    while left and values[left-1]>=threshold:left-=1
    while right+1<len(values) and values[right+1]>=threshold:right+=1
    if left==0 or right==len(values)-1 or offsets[right]-offsets[left]>width*.09:
        return None
    rival=(abs(offsets-offsets[peak])>max(3.,width*.035)) & (values>=floor+(high-floor)*.7)
    rival[left:right+1]=False
    if rival.any():return None
    return float(np.average(offsets[left:right+1],weights=values[left:right+1]-floor))


def _sample_division(image, start, end, pitch, outer):
    """Read a dark frame or white gutter in three source-image strips."""
    tangent=end-start;length=float(np.linalg.norm(tangent))
    if length<20:return None
    normal=np.array([-tangent[1],tangent[0]])/length
    radius=max(5.,min(18.,pitch*.075))
    offsets=np.arange(-radius,radius+.25,.5,dtype=np.float32)
    ts=np.linspace(.12,.88,21,dtype=np.float32)
    points=start+ts[:,None,None]*tangent+offsets[None,:,None]*normal
    if (points[:,:,0].min()<1 or points[:,:,1].min()<1 or
            points[:,:,0].max()>image.shape[1]-2 or points[:,:,1].max()>image.shape[0]-2):
        return None
    pixels=cv2.remap(image,points[:,:,0].astype(np.float32),points[:,:,1].astype(np.float32),cv2.INTER_LINEAR)
    lab=cv2.cvtColor(pixels,cv2.COLOR_BGR2LAB).astype(np.float32)
    channels=[lab[:,:,0],np.linalg.norm(lab[:,:,1:]-128.,axis=2)]
    candidates=[]
    for mode,channel in enumerate(channels):
        readings=[]
        for part in np.array_split(channel,3,axis=0):
            scales=[]
            for sigma in (.5,.8):
                smooth=cv2.GaussianBlur(part,(0,0),sigmaX=sigma/.5,sigmaY=.01)
                kernel=np.ones((1,max(5,round(pitch*.06/.5)|1)),np.uint8)
                if outer and mode==1:
                    # Outside a coloured panel there may be a broad unprinted
                    # hem, not a narrow gutter. Observe its chroma transition;
                    # a neutral bed/cloth brightness edge cannot supply it.
                    response=np.pad(abs(smooth[:,4:]-smooth[:,:-4])/2.,((0,0),(2,2)))
                else:
                    response=cv2.morphologyEx(smooth,cv2.MORPH_CLOSE,kernel)-smooth
                profile=np.percentile(response,20,axis=0)
                p=_ridge_position(profile,offsets,pitch)
                if p is None:break
                scales.append(p)
            if len(scales)!=2 or abs(scales[0]-scales[1])>1.:
                break
            readings.append(float(np.mean(scales)))
        if len(readings)==3:
            t=np.array([ts[:7].mean(),ts[7:14].mean(),ts[14:].mean()])
            fit=np.polyfit(t,readings,1)
            if max(abs(np.polyval(fit,t)-readings))<=1.:
                candidates.append(fit)
    if not candidates:return None
    if len(candidates)==2 and max(abs(np.polyval(candidates[0],[0,1])-np.polyval(candidates[1],[0,1])))>2.:
        return None
    fit=np.mean(candidates,axis=0)
    return (start+normal*np.polyval(fit,0),end+normal*np.polyval(fit,1))


def refine_projected_sections(image,grid):
    """Refine automatic printed polygons; manual/projective user guides stay put.

    Shared vertices keep neighbouring sections consistent. The original global
    projection remains available for assignment; actual polygons/centres are
    explicit, so no regular lattice replaces the observed individual sections.
    """
    if grid.source!='printed' or not grid.cell_regions_px:return grid
    cols,rows=grid.columns,grid.rows
    polygons=np.asarray(grid.cell_regions_px,float).reshape(rows,cols,4,2)
    vertices=np.zeros((rows+1,cols+1,2));weights=np.zeros((rows+1,cols+1))
    for r in range(rows):
        for c in range(cols):
            for point,(dr,dc) in zip(polygons[r,c],((0,0),(0,1),(1,1),(1,0))):
                vertices[r+dr,c+dc]+=point;weights[r+dr,c+dc]+=1
    vertices/=weights[:,:,None]
    constraints={};count=0
    for vertical in (False,True):
        outer_limit=cols if vertical else rows
        for r in range(rows if vertical else rows+1):
            for c in range(cols+1 if vertical else cols):
                a=(r,c);b=(r+1,c) if vertical else (r,c+1)
                pitch=float(np.median(np.linalg.norm(np.diff(vertices,axis=1 if vertical else 0),axis=2)))
                edge=_sample_division(image,vertices[a],vertices[b],pitch,
                                      (c if vertical else r) in (0,outer_limit))
                if edge is None:continue
                count+=1;u,v=edge;direction=v-u
                normal=np.array([-direction[1],direction[0]])/np.linalg.norm(direction)
                for index in (a,b):
                    constraints.setdefault(index,[]).append((normal,float(normal@u)))
    if not count:return grid
    adjusted=vertices.copy()
    for index,lines in constraints.items():
        point=vertices[index];normals=np.array([n for n,_ in lines]);residual=np.array([d-n@point for n,d in lines])
        delta=np.linalg.lstsq(normals,residual,rcond=None)[0]
        if np.linalg.norm(delta)<=18 and max(abs(normals@delta-residual))<=2.:
            adjusted[index]=point+delta
    regions=[];centres=[]
    for r in range(rows):
        for c in range(cols):
            poly=np.array([adjusted[r,c],adjusted[r,c+1],adjusted[r+1,c+1],adjusted[r+1,c]])
            if not cv2.isContourConvex(poly.astype(np.float32)) or cv2.contourArea(poly.astype(np.float32))<cv2.contourArea(polygons[r,c].astype(np.float32))*.8:
                return grid
            # The diagonal intersection is the projective centre of a square.
            a,b=poly[2]-poly[0],poly[3]-poly[1]
            try:t=np.linalg.solve(np.column_stack([a,-b]),poly[1]-poly[0])[0]
            except np.linalg.LinAlgError:return grid
            centre=poly[0]+t*a
            regions.append(tuple(map(tuple,poly)));centres.append(tuple(centre))
    if np.max(abs(adjusted-vertices))<.05:return grid
    return replace(grid,cell_regions_px=tuple(regions),cell_centers_px=tuple(centres))


def trim_unprinted_extensions(image,axes,observations):
    """An observed closing frame with terminated stems ends the printed sheet.

    Only unobserved exterior extensions are eligible. Faint artwork inside the
    closing frame is never tested against a new contrast threshold or deleted.
    """
    from .printed_partition import _profiles
    axes=[list(lines) for lines in axes];removed=[]
    for axis in (0,1):
        estimates=set(observations[axis]['estimated'])
        for at_end in (False,True):
            lines=axes[axis];other=axes[1-axis]
            edge=len(lines)-1 if at_end else 0
            if edge not in estimates or len(lines)<5:continue
            border=lines[-2] if at_end else lines[1]
            pitch=abs(border-(lines[-3] if at_end else lines[2]))
            pad=max(8,round(pitch*.08))
            before=(border-pitch+pad,border-pad) if at_end else (border+pad,border+pitch-pad)
            after=(border+pad,lines[-1]-pad) if at_end else (lines[0]+pad,border-pad)
            def strip(bounds):
                a,b=max(0,round(bounds[0])),min(image.shape[1-axis],round(bounds[1]))
                return image[:,a:b] if axis==0 else image[a:b]
            inside,outside=strip(before),strip(after)
            if min(*inside.shape[:2],*outside.shape[:2])<20:continue
            before_profile=_profiles(inside,'frames',.5)[1-axis]
            after_profile=_profiles(outside,'frames',.5)[1-axis]
            votes=[]
            for p in other[1:-1]:
                i=round(p);a,b=max(0,i-3),min(len(before_profile),i+4)
                strong=float(before_profile[a:b].max());weak=float(after_profile[a:b].max())
                if strong>=15.:votes.append(weak<max(3.,strong*.25))
            # Observe the full closing rule as well as several terminated stems.
            span=image[:,max(0,round(other[0])):min(image.shape[1],round(other[-1]))] if axis==1 else image[max(0,round(other[0])):min(image.shape[0],round(other[-1]))]
            closing=_profiles(span,'frames',.5)[axis]
            k=round(border);strength=float(closing[max(0,k-3):min(len(closing),k+4)].max())
            if len(votes)>=3 and np.mean(votes)>=.8 and strength>=15.:
                axes[axis]=lines[:-1] if at_end else lines[1:]
                estimates=({i for i in estimates if i!=edge} if at_end else
                           {i-1 for i in estimates if i!=edge})
                removed.append({'axis':axis,'side':'end' if at_end else 'start',
                                'closing_border':float(border),'terminated_stems':sum(votes)})
    return tuple(tuple(lines) for lines in axes),removed


def supported_missing_compositions(image,candidates,grid,layout=None):
    """Re-read a layout gap only when two image readings support actual ink.

    A missing position supplies a search region, never permission to invent a
    drawing. Failed/fallback silhouette readings and off-image cells abstain.
    """
    if not candidates:return []
    if grid is None:
        if layout is None or not layout.reliable:return []
    elif grid.confidence<.78:return []
    from .logical_layout import LayoutObservation,layout_from_panel_grid
    from .printed_composition import segment_printed_composition
    from .camera_panel import project_points
    if grid is not None:
        observations=[LayoutObservation(i,c.center_px,c.bounding_box_px,c.layout_center_px)
                      for i,c in enumerate(candidates)]
        layout=layout_from_panel_grid(observations,grid)
    recovered=[]
    for gap in layout.missing:
        if gap.covered_by_artwork or not layout.cell_inside_image(gap.column,gap.row,image.shape[1],image.shape[0]):
            continue
        polygon=np.asarray(layout.cell_polygon(gap.column,gap.row),np.float32)
        width=max(np.linalg.norm(polygon[1]-polygon[0]),np.linalg.norm(polygon[2]-polygon[3]))
        height=max(np.linalg.norm(polygon[3]-polygon[0]),np.linalg.norm(polygon[2]-polygon[1]))
        scale=min(1.,300/max(width,height));width,height=max(12,round(width*scale)),max(12,round(height*scale))
        pad=max(3,round(min(width,height)*.04))
        target=np.float32([(pad,pad),(pad+width,pad),(pad+width,pad+height),(pad,pad+height)])
        transform=cv2.getPerspectiveTransform(polygon,target)
        crop=cv2.warpPerspective(image,transform,(width+2*pad,height+2*pad))
        read=segment_printed_composition(crop,(pad,pad,pad+width,pad+height))
        if read is None or not read['support_contours']:continue
        contours=[np.asarray(p,np.float32) for p in read['support_contours']]
        coherent=[p for p in contours if min(cv2.boundingRect(p)[2:])>=min(width,height)*.10]
        if not coherent or sum(cv2.contourArea(p) for p in coherent)<width*height*.003:continue
        x,y,w,h=read['box'];inverse=np.linalg.inv(transform)
        bounds=project_points([(x,y),(x+w,y),(x+w,y+h),(x,y+h)],inverse)
        a,b=np.floor(bounds.min(axis=0)).astype(int),np.ceil(bounds.max(axis=0)).astype(int)
        box=(int(a[0]),int(a[1]),int(b[0]-a[0]),int(b[1]-a[1]))
        # An accessory/body already owned by a neighbour is not another motif.
        duplicate=False
        for c in candidates:
            bx,by,bw,bh=c.bounding_box_px
            overlap=max(0,min(box[0]+box[2],bx+bw)-max(box[0],bx))*max(0,min(box[1]+box[3],by+bh)-max(box[1],by))
            if overlap/max(1,min(box[2]*box[3],bw*bh))>.35:duplicate=True;break
        if duplicate:continue
        recovered.append({'cell':(gap.column,gap.row),'box':box,'anchor':layout.position(gap.column,gap.row),
                          'score':read['score'],'area':round(read['area']/scale**2),
                          'issues':read['issues'],'uncertain':read['extent_uncertain'],
                          'support_contours':read['support_contours'],'inverse':inverse})
    return recovered
