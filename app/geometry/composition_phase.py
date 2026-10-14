"""Find a shared translation that contains complete artwork at the chosen size."""
from dataclasses import replace
import numpy as np


def contain_automatic_compositions(layout,detections,mapper,width_inches,height_inches):
    # Printed/manual guides, holes, spanning artwork and explicit edits retain
    # their positions. A common phase is only inferred for complete auto groups.
    if (not layout.reliable or layout.source in ('manual','camera','reference','visual')
            or layout.missing or any(m.status!='matched' or m.review_reason for m in layout.matches)
            or any(d.manual or d.inferred or d.source_incomplete for d in detections)):
        return layout
    active=[d for d in detections if d.enabled and d.bounding_box_px is not None]
    if len(active)!=layout.columns*layout.rows:return layout
    matches={m.detection_id:m for m in layout.matches}
    half=np.array([width_inches*mapper.px_per_inch_x,height_inches*mapper.px_per_inch_y])/2
    bed_lo=np.array(mapper.inches_to_pixel(0,0));bed_hi=np.array(mapper.inches_to_pixel(mapper.bed_width_in,mapper.bed_height_in))
    lower=np.array([-np.inf,-np.inf]);upper=np.array([np.inf,np.inf])
    for detection in active:
        match=matches.get(detection.id)
        if match is None or match.column is None or match.row is None:return layout
        position=np.asarray(layout.position(match.column,match.row))
        x,y,w,h=detection.bounding_box_px
        if np.any(np.array([w,h])>half*2+1e-6):return layout
        lower=np.maximum(lower,np.maximum(np.array([x+w,y+h])-half,bed_lo+half)-position)
        upper=np.minimum(upper,np.minimum(np.array([x,y])+half,bed_hi-half)-position)
    if np.any(lower>upper+1e-6):return layout
    delta=np.clip(np.zeros(2),lower,upper)
    if np.linalg.norm(delta)<1e-6:return layout
    pitch=min(np.linalg.norm(layout.column_vector_px),np.linalg.norm(layout.row_vector_px))
    if np.linalg.norm(delta)>pitch*.20:return layout
    projection=layout.projection
    if projection is not None:
        matrix=np.array([[1.,0.,delta[0]],[0.,1.,delta[1]],[0.,0.,1.]])@np.asarray(projection)
        projection=tuple(tuple(float(v) for v in line) for line in matrix)
    shifted=tuple(replace(m,proposed_px=tuple(np.asarray(m.proposed_px)+delta)) for m in layout.matches)
    return replace(layout,origin_px=tuple(np.asarray(layout.origin_px)+delta),projection=projection,matches=shifted,
                   reason='Common cut phase contains the complete compositions at the selected size.')
