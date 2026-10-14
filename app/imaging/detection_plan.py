"""Choose geometry and local analysis from explicit, comparable evidence."""
from dataclasses import dataclass

import cv2
import numpy as np

from .scene_profile import POLICY, background_evidence
from .logical_layout import LayoutObservation, fit_logical_layout, layout_from_panel_grid
from .panel_grid import PanelGrid


def stable_artwork_grid(candidate_passes):
    """Fit actual spacing and phase, independent of camera/fabric dimensions.

    Require agreement across foreground thresholds before artwork geometry can
    contradict decorative divisions. Raw fragments alone are not a veto.
    """
    layouts = []
    supports = []
    for candidates in candidate_passes:
        layout = fit_logical_layout([
            LayoutObservation(i, c.center_px, c.bounding_box_px)
            for i, c in enumerate(candidates)
        ])
        support = sum(m.status == 'matched' for m in layout.matches) / max(1, len(candidates))
        if (not layout.reliable or min(layout.columns, layout.rows) < 2
                or layout.occupancy < .85):
            return None
        layouts.append(layout)
        supports.append(support)
    if len(layouts) < 3:
        return None
    # A permissive pass may reveal extra background fragments without changing
    # the fitted artwork geometry. Require a clean anchor and corroborating pass;
    # every pass must still agree on dimensions, spacing and phase below.
    if supports[0] < .85 or sum(value >= .85 for value in supports) < 2:
        return None
    first = layouts[0]
    spacing = min(np.linalg.norm(first.column_vector_px), np.linalg.norm(first.row_vector_px))
    corners = [(0, 0), (first.columns-1, 0), (0, first.rows-1), (first.columns-1, first.rows-1)]
    for other in layouts[1:]:
        if (other.columns, other.rows) != (first.columns, first.rows):
            return None
        if max(np.linalg.norm(np.array(first.position(c,r))-other.position(c,r))
               for c,r in corners) > spacing*.08:
            return None
    origin, column, row = first.origin_px, first.column_vector_px, first.row_vector_px
    return PanelGrid(
        tuple(origin[0]+(c-.5)*column[0]+(first.rows-1)*row[0]/2 for c in range(first.columns+1)),
        tuple(origin[1]+(r-.5)*row[1]+(first.columns-1)*column[1]/2 for r in range(first.rows+1)),
        min(l.confidence for l in layouts), 'observations', (origin,column,row), first.projection)


@dataclass(frozen=True)
class ZonePlan:
    column: int
    row: int
    bounds: tuple[int, int, int, int]
    strategy: str
    preserve_detail: bool
    shadow_gain: float
    measurements: dict


def plan_zones(image, grid):
    h,w = image.shape[:2]
    zones = []
    for col,row,(x,y,cw,ch) in grid.cells():
        left,top,right,bottom=max(0,x),max(0,y),min(w,x+cw),min(h,y+ch)
        if right-left < 8 or bottom-top < 8:
            continue
        crop=image[top:bottom,left:right]
        evidence=background_evidence(crop)
        if evidence is None:
            continue
        stats=evidence['stats']
        zones.append(ZonePlan(col,row,(left,top,right,bottom),
                              'local_palette' if stats['background_reliable'] else 'local_contrast',
                              stats['fine_detail_fraction'] > .12,1.,stats))
    # Cross-cell agreement is a prerequisite for calling a row a shadow.
    # Colour similarity is checked separately from luminance.
    updated=[]
    for zone in zones:
        peers=[z for z in zones if z.row != zone.row and z.column == zone.column
               and np.linalg.norm(np.array(z.measurements['background_chroma'])-
                                  zone.measurements['background_chroma']) < 7
               and z.measurements['background_reliable']]
        reference=max((z.measurements['background_luminance'] for z in peers), default=0.)
        level=zone.measurements['background_luminance']
        gain=min(POLICY.max_shadow_gain, reference/max(1.,level)) if reference > level*1.18 else 1.
        updated.append((zone,gain))
    result=[]
    for zone,gain in updated:
        row_gains=[g for z,g in updated if z.row == zone.row and g > 1.]
        coherent=(len(row_gains) >= max(3, int(np.ceil(grid.columns*.6)))
                  and np.std(row_gains) < .12)
        values=dict(zone.measurements)
        shared=sum(np.linalg.norm(np.array(z.measurements['background_chroma'])-
                                  values['background_chroma']) < 7 for z in zones)
        values['similar_background_cells']=int(shared)
        result.append(ZonePlan(zone.column,zone.row,zone.bounds,zone.strategy,
                               zone.preserve_detail,gain if coherent else 1.,values))
    return result


def seam_profiles(image):
    """Compute image-only evidence once per comparison, never cache across images."""
    h,w=image.shape[:2]
    scale=min(1.,POLICY.max_scene_side/max(h,w))
    small=cv2.resize(image,(max(1,round(w*scale)),max(1,round(h*scale))))
    lab=cv2.cvtColor(small,cv2.COLOR_BGR2LAB).astype(np.float32)
    profiles = []
    for axis in (1, 0):
        signal = np.linalg.norm(np.diff(lab, axis=axis), axis=2)
        profile = np.percentile(signal, 65, axis=1-axis)
        baseline, high = np.percentile(profile, [50, 95])
        profiles.append((profile, baseline, high))
    return scale, profiles


def grid_evidence(image, grid, candidates, *, profiles=None):
    """Score the same pixel and occupancy evidence for every grid producer."""
    scale, profiles = seam_profiles(image) if profiles is None else profiles
    seams=[]
    for lines,(profile,baseline,high) in zip((grid.x_lines_px,grid.y_lines_px),profiles):
        radius=max(1,round(np.median(np.diff(lines))*scale*.025))
        for line in lines[1:-1]:
            p=round(line*scale)
            part=profile[max(0,p-radius):min(len(profile),p+radius+1)]
            if len(part):seams.append(float(np.clip((part.max()-baseline)/max(1.,high-baseline),0,1)))
    left,top,right,bottom=grid.bounds_px
    occupied=set();outside=0;residuals=[]
    for candidate in candidates:
        x,y=candidate.center_px
        if not (left <= x < right and top <= y < bottom):
            outside+=1;continue
        col=int(np.searchsorted(grid.x_lines_px,x,side='right')-1);row=int(np.searchsorted(grid.y_lines_px,y,side='right')-1)
        occupied.add((col,row))
        cx=(grid.x_lines_px[col]+grid.x_lines_px[col+1])/2
        cy=(grid.y_lines_px[row]+grid.y_lines_px[row+1])/2
        residuals.append(max(abs(x-cx)/(grid.x_lines_px[col+1]-grid.x_lines_px[col]),
                             abs(y-cy)/(grid.y_lines_px[row+1]-grid.y_lines_px[row])))
    coverage=len(occupied)/(grid.columns*grid.rows)
    alignment=float(np.mean(np.array(residuals)<.25)) if residuals else 0.
    seam=float(np.mean(seams)) if seams else 0.
    unexplained=outside/max(1,len(candidates))
    score=.40*seam+.35*coverage+.25*alignment-.3*unexplained
    return {'seam_support':seam,'occupied_fraction':coverage,'aligned_fraction':alignment,
            'outside_fraction':unexplained,'score':score,
            'unique_assignment_fraction':len(occupied)/max(1,len(candidates)-outside)}


def _contained_fraction(grid, candidates):
    """Box support for comparison only; this never clips or regroups artwork."""
    retained=[]
    for c in candidates:
        x,y,w,h=c.bounding_box_px
        area=max(1,w*h)
        retained.append(max((max(0,min(x+w,cx+cw)-max(x,cx))*
                             max(0,min(y+h,cy+ch)-max(y,cy))/area
                             for _,_,(cx,cy,cw,ch) in grid.cells()),default=0.))
    return float(np.mean(np.array(retained)>=.85)) if retained else 0.


def choose_grid(image, proposals, candidates, *, stable_routes=(), route_evidence=None):
    """Prefer clear independent support; producer confidence is only eligibility."""
    rows=[]
    route_evidence=route_evidence or {}
    grids=dict(proposals)
    profiles = seam_profiles(image)
    reference=candidates
    reference_name='primary'
    for route in stable_routes:
        own=route_evidence.get(route)
        grid=grids.get(route)
        if own and grid is not None:
            support=grid_evidence(image,grid,own,profiles=profiles)
            if (support['occupied_fraction'] >= .85 and support['aligned_fraction'] >= .8
                    and support['unique_assignment_fraction'] >= .85):
                reference=own
                reference_name=route
                break
    for name,grid in proposals:
        if grid is None:continue
        evidence=route_evidence.get(name,reference)
        measures=grid_evidence(image,grid,evidence,profiles=profiles)
        rows.append({'route':name,'columns':grid.columns,'rows':grid.rows,
                     'eligible':grid.confidence >= .78,'evidence_count':len(evidence),
                     'evidence_source':name if name in route_evidence else reference_name,**measures})
        if (measures['unique_assignment_fraction'] < .70
                and measures['aligned_fraction'] < .25 and len(evidence) >= 6):
            rows[-1]['eligible'] = False
            rows[-1]['rejection_reason'] = 'Groups poorly aligned independent centres; no reliable ownership evidence'
    independent = [r for r in rows if r['eligible'] and r['route'] in stable_routes
                   and r['unique_assignment_fraction'] >= .85 and r['aligned_fraction'] >= .8]
    for row in rows:
        for alternative in independent:
            own=route_evidence.get(alternative['route'])
            if own is not None and row is not alternative:
                support=grid_evidence(image,grids[row['route']],own,profiles=profiles)
                baseline=_contained_fraction(grids[alternative['route']],own)
                retained=_contained_fraction(grids[row['route']],own)
                row.setdefault('cross_checks',[]).append({
                    'against':alternative['route'],'contained_fraction':retained,
                    'reference_contained_fraction':baseline,**support})
                if (support['unique_assignment_fraction'] < .70 or
                        support['outside_fraction'] > alternative['outside_fraction']+.12 or
                        support['aligned_fraction'] < alternative['aligned_fraction']-.25 or
                        (baseline >= .95 and retained < baseline-.03
                         and grids[row['route']].source not in ('manual','visual','camera','reference')) or
                        (baseline >= .8 and retained < baseline-.25)):
                    row['eligible']=False
                    row['rejection_reason']='Contradicts independently supported compositions from '+alternative['route']
                    break
            if (row is not alternative
                    and row['unique_assignment_fraction'] < alternative['unique_assignment_fraction']-.20
                    and row['aligned_fraction'] < alternative['aligned_fraction']-.25):
                row['eligible'] = False
                row['rejection_reason'] = 'Groups distinct stable artwork centres; contradicted by '+alternative['route']
                break
    eligible=[r for r in rows if r['eligible']]
    if not eligible:return None,rows
    winner=max(eligible,key=lambda r:r['score'])
    # Preserve established routing for equivalent geometry. Do not present a
    # materially different near-tie as independently confirmed geometry.
    for row in eligible:
        if row['score'] >= winner['score']-.06:
            alternatives = [r['route'] for r in eligible if r is not row
                and r['score'] >= winner['score']-.06
                and grid_distance(grids[row['route']], grids[r['route']]) > .15]
            row['competing_routes'] = alternatives
            row['selection_margin'] = row['score'] - max(
                (r['score'] for r in eligible if r is not row), default=row['score'])
            return row['route'],rows
    return winner['route'],rows


def grid_distance(first, second):
    """Largest centre displacement, in cells, including affine/projective phase."""
    if (first.columns, first.rows) != (second.columns, second.rows):
        return float('inf')
    from .logical_layout import layout_from_panel_grid
    a, b = layout_from_panel_grid([], first), layout_from_panel_grid([], second)
    spacing = min(np.median(np.diff(first.x_lines_px)), np.median(np.diff(first.y_lines_px)))
    return max(np.linalg.norm(np.array(a.position(c,r))-b.position(c,r))
               for c,r in ((0,0),(first.columns-1,0),(0,first.rows-1),
                           (first.columns-1,first.rows-1))) / max(1., spacing)
