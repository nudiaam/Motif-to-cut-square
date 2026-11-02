"""Contain physical rectangles in convex source-image regions.

The region remains attached to a cut after manual movement. Export must check
current geometry, rather than trusting the last UI validation.
"""
from math import hypot, isfinite

CUT_REGION_CLEARANCE_IN = 0.01


def _planes(polygon):
    if len(polygon) < 3 or not all(isfinite(v) for p in polygon for v in p):
        return None
    area = sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(polygon, (*polygon[1:],polygon[0])))
    if abs(area) < 1e-9:
        return None
    sign = 1. if area > 0 else -1.
    result = []
    for a,b in zip(polygon, (*polygon[1:],polygon[0])):
        nx,ny = sign*(a[1]-b[1]),sign*(b[0]-a[0])
        length = hypot(nx,ny)
        if length < 1e-9:
            return None
        nx,ny = nx/length,ny/length
        k = nx*a[0]+ny*a[1]
        if any(nx*x+ny*y < k-1e-7 for x,y in polygon):
            return None  # A non-convex/invalid boundary cannot certify a cut.
        result.append((nx,ny,k))
    return result


def rectangle_inside_region(center, size, polygon, clearance=0.):
    planes = _planes(polygon)
    if planes is None:
        return False
    x,y = center
    hw,hh = size[0]/2,size[1]/2
    return all(nx*x+ny*y-abs(nx)*hw-abs(ny)*hh >= k+clearance-1e-8
               for nx,ny,k in planes)


def fit_center_in_region(target, size, polygon, clearance=0., center_bounds=None):
    """Nearest feasible centre; None means the requested size cannot fit.

    Erode each polygon half-plane by the axis-aligned rectangle's support.
    Optional centre bounds enforce artwork containment and physical bed limits.
    """
    planes = _planes(polygon)
    if planes is None:
        return None
    xs,ys = zip(*polygon)
    left,top,right,bottom = min(xs),min(ys),max(xs),max(ys)
    if center_bounds is not None:
        a,b,c,d = center_bounds
        left,top,right,bottom = max(left,a),max(top,b),min(right,c),min(bottom,d)
    if right < left or bottom < top:
        return None
    feasible = [(left,top),(right,top),(right,bottom),(left,bottom)]
    hw,hh = size[0]/2,size[1]/2
    for nx,ny,k in planes:
        k += clearance+abs(nx)*hw+abs(ny)*hh
        clipped = []
        for a,b in zip(feasible, (*feasible[1:],feasible[0])):
            da,db = nx*a[0]+ny*a[1]-k,nx*b[0]+ny*b[1]-k
            if da >= -1e-9:
                clipped.append(a)
            if (da < 0) != (db < 0):
                t = da/(da-db)
                clipped.append((a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])))
        feasible = clipped
        if not feasible:
            return None
    if rectangle_inside_region(target,size,polygon,clearance) and (
            center_bounds is None or left <= target[0] <= right and top <= target[1] <= bottom):
        return target
    candidates = list(feasible)
    for a,b in zip(feasible, (*feasible[1:],feasible[0])):
        dx,dy = b[0]-a[0],b[1]-a[1]
        length2 = dx*dx+dy*dy
        if length2 > 1e-18:
            t = max(0.,min(1.,((target[0]-a[0])*dx+(target[1]-a[1])*dy)/length2))
            candidates.append((a[0]+t*dx,a[1]+t*dy))
    return min(candidates,key=lambda p:(p[0]-target[0])**2+(p[1]-target[1])**2)
