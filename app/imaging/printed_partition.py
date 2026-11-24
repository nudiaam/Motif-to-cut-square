"""Independent evidence for touching pastel panels and faint printed frames.

Read sustained divisions in a cloth-relative analysis plane. Neither artwork
counts nor physical cut dimensions participate in the proposal. A two-axis,
two-scale agreement is required; plain cloth and one-axis stripes abstain.
"""
import cv2
import numpy as np

from .camera_panel import CameraPanel, _axis_choices, _measured_lines
from .panel_grid import PanelGrid
from .seam_grid import _axis_lines


def _cloth_plane(image):
    h, w = image.shape[:2]
    if min(h, w) < 160:
        return None
    gray = cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (9, 9), 0)
    otsu, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    quads = []
    # Otsu alone can mistake a diagonal shadow for the cloth perimeter.
    # Require agreement of two readings. A bed highlight can contaminate the
    # darkest reading; it must not veto two independently matching outlines.
    for threshold in (max(70., min(90., otsu*.55)), max(90., min(110., otsu*.70)),
                      max(110., min(130., otsu*.85))):
        _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < h*w*.35:
            continue
        hull = cv2.convexHull(contour)
        p = cv2.approxPolyDP(hull, cv2.arcLength(hull, True)*.02, True).reshape(-1, 2)
        if len(p) != 4 or cv2.contourArea(p) < cv2.contourArea(hull)*.94:
            continue
        p = p.astype(np.float32)
        s, d = p.sum(1), np.diff(p, axis=1).ravel()
        q = np.array([p[np.argmin(s)], p[np.argmin(d)], p[np.argmax(s)], p[np.argmax(d)]])
        if len(np.unique(q, axis=0)) != 4:
            continue
        sides = np.roll(q, -1, axis=0)-q
        norms = np.linalg.norm(sides, axis=1)
        if np.any(norms < min(h,w)*.25):
            continue
        cosine = np.sum(sides*np.roll(sides, 1, axis=0), axis=1)/(norms*np.roll(norms, 1))
        if np.max(abs(cosine)) > .35:
            continue
        quads.append(q)
    pairs = [(a,b) for j,b in enumerate(quads) for a in quads[:j]
             if np.max(np.linalg.norm(a-b,axis=1)) <= min(h,w)*.035]
    if not pairs:
        return None
    quad = np.mean(pairs[0], axis=0).astype(np.float32)
    width = max(np.linalg.norm(quad[1]-quad[0]), np.linalg.norm(quad[2]-quad[3]))
    height = max(np.linalg.norm(quad[3]-quad[0]), np.linalg.norm(quad[2]-quad[1]))
    # Keep the profile filters at a comparable analysis scale for half-size
    # camera inputs too. This resamples only an analysis copy; source coordinates
    # still use the inverse transform and no physical calibration changes.
    scale = min(2., 1000/max(width,height))
    width, height = round(width*scale), round(height*scale)
    transform = cv2.getPerspectiveTransform(quad, np.float32(
        [[0,0], [width-1,0], [width-1,height-1], [0,height-1]]))
    return cv2.warpPerspective(image, transform, (width,height)), np.linalg.inv(transform)


def _profiles(image, mode, scale):
    h,w = image.shape[:2]
    if mode == 'frames':
        gray = cv2.GaussianBlur(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32),
                                (0,0), scale)
        signal = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, np.ones((9,9),np.uint8))-gray
    else:
        signal = cv2.GaussianBlur(cv2.cvtColor(image,cv2.COLOR_BGR2LAB).astype(np.float32),
                                  (0,0), scale)[:,:,1:]
    result = []
    for axis in (1,0):
        along = np.swapaxes(signal,0,axis)
        if mode == 'colour':
            difference = np.linalg.norm(along[8:]-along[:-8],axis=2)
            padded = cv2.dilate(difference,np.ones((5,1),np.uint8))
            profile = np.pad(np.percentile(padded,20,axis=1),(4,4))
        else:
            padded = cv2.dilate(along,np.ones((7,1),np.uint8))
            rim = max(3, round(padded.shape[1]*.015))
            profile = np.percentile(padded[:,rim:-rim],20,axis=1)
        profile=cv2.GaussianBlur(profile.reshape(1,-1),(0,0),.6).ravel()
        if mode=='frames':
            # A closing/dilation response at the analysis crop has no pixels
            # on both sides. It can be bed/warp fill, not a printed division.
            # The actual printed frame farther inside remains measurable.
            unsupported=4+3+max(2,round(3*scale))
            profile[:unsupported]=0.;profile[-unsupported:]=0.
        result.append(profile)
    return result


def _response_center(profile,indices,floor,high,minimum):
    """Locate the centre of a sustained response, not its first flat maximum.

    Differencing and dilation spread a true division over several pixels. A
    pitch prior or the first argmax biases that plateau towards one side.
    The proposal limits which peak is eligible; its measured centre is read
    independently from the connected response, including beyond that window.
    """
    if not len(indices):return None
    signal=(profile-floor)/max(.5,high-floor)
    peak=int(indices[np.argmax(signal[indices])])
    strength=float(signal[peak])
    if strength<minimum:return None
    threshold=max(minimum*.6,strength*.8)
    left,right=peak,peak+1
    while left>0 and signal[left-1]>=threshold:left-=1
    while right<len(signal) and signal[right]>=threshold:right+=1
    coordinates=np.arange(left,right)
    return float(np.average(coordinates,weights=np.maximum(signal[left:right],.001))),strength


def _read_axis(profile, *, details=False):
    choices = sorted(_axis_choices(profile,max(35,round(len(profile)*.045))),
                     key=lambda v:-v[1])
    if not choices or choices[0][0] < 3 or choices[0][1] < .26:
        return None
    count, score = choices[0]
    if len(choices)>1 and choices[1][1] > score*.72:
        return None
    lines = _measured_lines(profile,count)
    if lines is None:
        return None
    pitch = float(np.median(np.diff(lines)))
    floor, high = np.percentile(profile,[50,96])
    measured = []
    observed = []
    for index,expected in enumerate(lines):
        radius = pitch*.16
        xs = np.arange(max(0,int(expected-radius)),min(len(profile),int(expected+radius)+1))
        # All internal boundaries need visible support. Outer ones may be
        # extrapolated only within this same cloth plane, with review metadata.
        peak=_response_center(profile,xs,floor,high,.18 if index in (0,len(lines)-1) else .5)
        measured.append(peak[0] if peak is not None else float(expected))
        observed.append(peak is not None)
    # A motif's repeated upper edge can be stronger than the cloth rim at one
    # smoothing scale. Locate outer divisions from the adjacent *measured*
    # seams, rather than accepting a short first/last row from the pitch prior.
    # This is independent of artwork boxes, desired sizes and source filenames.
    for index,expected in ((0,2*measured[1]-measured[2]),
                           (len(measured)-1,2*measured[-2]-measured[-3])):
        radius=pitch*.10
        xs=np.arange(max(0,int(expected-radius)),min(len(profile),int(expected+radius)+1))
        peak=_response_center(profile,xs,floor,high,.18)
        if peak is not None and abs(peak[0]-expected)<=radius:
            measured[index]=peak[0]
            observed[index]=True
    if np.min(np.diff(measured)) < pitch*.70 or np.max(np.diff(measured)) > pitch*1.30:
        return None
    result=(tuple(measured),float(score))
    return (*result,{'observed':tuple(observed)}) if details else result


def _combine_axis_votes(first, second, *, allow_outer_estimate=False):
    """Combine observations without turning a spacing prior into a border.

    Every observed division, including the outside edges, must agree across
    scales. A real observation wins over an extrapolated prior. Missing support
    remains explicit review evidence instead of cropping to the inward guess.
    """
    if len(first[0]) != len(second[0]):
        return None
    pitch=float(np.median(np.diff(first[0])))
    lines=[];estimated=[];single=[];disputed=[];spread=0.
    for i,(a,b) in enumerate(zip(first[0],second[0])):
        support=(first[2]['observed'][i],second[2]['observed'][i])
        if all(support):
            if abs(a-b)>pitch*.08:
                if not allow_outer_estimate or i not in (0,len(first[0])-1):
                    return None
                # Retain the well-supported interior/ownership structure, but
                # reject both conflicting edge readings. An explicit estimate
                # cannot be presented as an independently observed boundary.
                lines.append(None);estimated.append(i);disputed.append(i)
                continue
            lines.append((a+b)/2)
            spread=max(spread,abs(a-b)/2)
        elif any(support):
            lines.append(a if support[0] else b)
            single.append(i)
            spread=max(spread,abs(a-b)/2)
        else:
            lines.append((a+b)/2)
            estimated.append(i)
            spread=max(spread,abs(a-b)/2)
    for i in disputed:
        lines[i]=(2*lines[1]-lines[2] if i==0 else 2*lines[-2]-lines[-3])
        spread=max(spread,abs(lines[i]-first[0][i]),abs(lines[i]-second[0][i]))
    if min(np.diff(lines))<pitch*.70 or max(np.diff(lines))>pitch*1.30:
        return None
    return tuple(lines),{'estimated':estimated,'single_scale':single,'disputed':disputed,'spread_px':spread}


def _read_truncated_axis(profile,cut_start,cut_end):
    """Read actual seams when the photograph ends partway through a row.

    A full-sheet period fit would distribute three complete rows over the
    partial fourth row and move every centre. The cut edge and sustained seam
    sequence, rather than artwork centres, authorize this limited extrapolation.
    """
    if cut_start == cut_end:
        return None
    length=len(profile);floor,high=np.percentile(profile,[50,96])
    if high-floor<1.:
        return None
    normal=(profile-floor)/(high-floor)
    peaks=np.flatnonzero((normal>np.roll(normal,1))&(normal>=np.roll(normal,-1))&(normal>.65))
    peaks=peaks[(peaks>length*.06)&(peaks<length*.94)]
    chosen=[]
    for p in sorted(peaks,key=lambda p:-normal[p]):
        if all(abs(p-q)>length*.12 for q in chosen):chosen.append(int(p))
    chosen=sorted(chosen)
    if len(chosen)<3:
        return None
    spacing=float(np.median(np.diff(chosen)))
    if np.max(abs(np.diff(chosen)-spacing))>spacing*.22:
        return None
    radius=max(3,round(spacing*.10))
    chosen=[_response_center(profile,np.arange(max(0,p-radius),min(length,p+radius+1)),
                             floor,high,.65)[0] for p in chosen]
    spacing=float(np.median(np.diff(chosen)))
    if cut_end:
        if not spacing*.12<length-1-chosen[-1]<spacing*.85:
            return None
        window=max(3,round(spacing*.18))
        peak=_response_center(profile,np.arange(window),floor,high,.20)
        if peak is None:return None
        outer=peak[0]
        if not .65*spacing<chosen[0]-outer<1.35*spacing:
            return None
        lines=[outer,*chosen,chosen[-1]+spacing]
    else:
        if not spacing*.12<chosen[0]<spacing*.85:
            return None
        window=max(3,round(spacing*.18))
        peak=_response_center(profile,np.arange(length-window,length),floor,high,.20)
        if peak is None:return None
        outer=peak[0]
        if not .65*spacing<outer-chosen[-1]<1.35*spacing:
            return None
        lines=[chosen[0]-spacing,*chosen,outer]
    return tuple(float(v) for v in lines),float(np.mean(np.interp(chosen,np.arange(length),normal)))


def _observed_frame_sequence(profile,perpendicular_pitch):
    """Read a finite sequence of actual rules when a wide hem defeats a fit.

    No cloth-length/count extrapolation participates. At least four sustained
    rules, near-square spacing and a majority of the axis span are required.
    """
    floor=float(np.median(profile));mad=float(np.median(abs(profile-floor)))
    high=float(np.max(profile));threshold=max(floor+6*mad,floor+(high-floor)*.25,4.)
    peaks=np.flatnonzero((profile>=np.roll(profile,1))&(profile>np.roll(profile,-1))&(profile>threshold))
    accepted=[]
    for p in sorted(peaks,key=lambda p:-profile[p]):
        if all(abs(p-q)>perpendicular_pitch*.18 for q in accepted):accepted.append(int(p))
    accepted.sort()
    if len(accepted)<4 or len(accepted)>16:return None
    measured=[]
    for p in accepted:
        radius=max(3,round(perpendicular_pitch*.08))
        peak=_response_center(profile,np.arange(max(0,p-radius),min(len(profile),p+radius+1)),floor,high,.2)
        if peak is None:return None
        measured.append(peak[0])
    intervals=np.diff(measured);pitch=float(np.median(intervals))
    if (not .55< pitch/perpendicular_pitch <1.75 or
            min(intervals)<pitch*.75 or max(intervals)>pitch*1.25 or
            measured[-1]-measured[0]<len(profile)*.5):return None
    return tuple(measured),.8,{'observed':(True,)*len(measured),'finite_frame_sequence':True}


def _blank_colour_row(image, xs, ys, at_end):
    """Confirm an extrapolated end row is bare cloth beyond a closing rule."""
    # Read towards the bottom in both orientations. Examine the full printed
    # width so that even a single faint motif can protect the whole row.
    if not at_end:
        image = image[::-1]
        ys = [image.shape[0] - 1 - y for y in reversed(ys)]
    pitch = ys[-1] - ys[-2]
    radius = round(.12 * pitch)
    start = max(0, round(ys[-2]) - radius - 2)
    stop = min(image.shape[0], round(ys[-2]) + radius + 3)
    left, right = max(0, round(xs[0])), min(image.shape[1], round(xs[-1]))
    if stop - start < 5 or right - left < 20:
        return None
    strip = cv2.GaussianBlur(image[start:, left:right], (0, 0), 1.2)
    window = strip[:stop - start].astype(np.int16)
    steps = np.max(np.abs(window[4:] - window[:-4]), axis=2)
    # A closing rule has a colour or luminance step across most of the sheet.
    profile = np.percentile(steps, 20, axis=1)
    peak = int(np.argmax(profile))
    if profile[peak] < 15:
        return None
    border = start + peak + 2
    # Exclude the rule itself and the interpolation rim of the cloth warp.
    # A near-uniform *entire* strip is positive evidence of a blank hem.
    hem = strip[peak + 7:-3]
    if len(hem) < .70 * pitch:
        return None
    if np.ptp(hem, axis=(0, 1)).max() > 6:
        # Woven cloth and a folded edge can vary in brightness. Require the
        # vertical rules to end here, then inspect the whole width for print.
        from .section_evidence import trim_unprinted_extensions
        estimated = [{'estimated': []}, {'estimated': [len(ys) - 1]}]
        _, closures = trim_unprinted_extensions(image, (xs, ys), estimated)
        if not closures:
            return None
        pad = max(3, round(.08 * pitch))
        interior = image[border + pad:-pad, left:right]
        if len(interior) < .65 * pitch:
            return None
        smooth = cv2.GaussianBlur(interior, (0, 0), 2.5).astype(np.float32)
        chroma = smooth - smooth.mean(axis=2, keepdims=True)
        if np.ptp(chroma, axis=(0, 1)).max() > 8:
            return None
        spread = np.ptp(smooth, axis=(0, 1))
        low, high = np.percentile(smooth, (10, 90), axis=(0, 1))
        # Compare extremes with the normal variation of this same fabric.
        # Sparse marks in a smooth margin must not be averaged away.
        if np.any(spread > np.minimum(36, 6 + 3.5 * (high - low))):
            return None
    return border if at_end else image.shape[0] - 1 - border


def infer_printed_partition(image):
    plane = _cloth_plane(image)
    if plane is None:
        return None
    rectified, inverse = plane
    height,width=image.shape[:2]
    corners=cv2.perspectiveTransform(np.float64([[[0,0]],[[rectified.shape[1]-1,0]],
        [[rectified.shape[1]-1,rectified.shape[0]-1]],[[0,rectified.shape[0]-1]]]),inverse).reshape(-1,2)
    truncated=((bool(np.all(abs(corners[[0,3],0])<=3.)),bool(np.all(abs(corners[[1,2],0]-(width-1))<=3.))),
               (bool(np.all(abs(corners[[0,1],1])<=3.)),bool(np.all(abs(corners[[2,3],1]-(height-1))<=3.))))
    for mode, scales in (('colour',(2.5,3.5)), ('frames',(.5,.8))):
        votes = []
        used_truncation=False
        for scale in scales:
            profiles=_profiles(rectified,mode,scale)
            axes = [_read_axis(p,details=True) for p in profiles]
            if mode=='frames':
                for missing in (0,1):
                    current=axes[missing];other=axes[1-missing]
                    unsupported=(current is None or not current[2]['observed'][0]
                                 or not current[2]['observed'][-1])
                    if not unsupported or other is None or other[1]<=.6:continue
                    proposal=_observed_frame_sequence(profiles[missing],float(np.median(np.diff(other[0]))))
                    if proposal is not None:
                        # A finite subset ending well inside the cloth could
                        # omit a faint real row. Require a closing rule with
                        # terminated perpendicular stems before accepting it.
                        from .section_evidence import trim_unprinted_extensions
                        sequence=proposal[0];pitch=float(np.median(np.diff(sequence)))
                        for at_end in (False,True):
                            wide_margin=(sequence[-1]<len(profiles[missing])*.85 if at_end
                                         else sequence[0]>len(profiles[missing])*.15)
                            if not wide_margin:continue
                            extension=((*sequence,sequence[-1]+pitch) if at_end else
                                       (sequence[0]-pitch,*sequence))
                            proposed=[other[0],other[0]];proposed[missing]=extension
                            observations=[{'estimated':[]},{'estimated':[]}]
                            observations[missing]['estimated']=[len(extension)-1 if at_end else 0]
                            _,closed=trim_unprinted_extensions(rectified,proposed,observations)
                            if not any(item['axis']==missing for item in closed):
                                proposal=None;break
                        if proposal is not None:axes[missing]=proposal
            if mode=='colour' and sum(a is not None for a in axes)==1:
                missing=next(a for a in (0,1) if axes[a] is None)
                other=axes[1-missing]
                if other[1]>.6:
                    measured=_read_truncated_axis(profiles[missing],*truncated[missing])
                    # The extrapolated edge belongs to a deliberately partial
                    # row outside the source, never a complete cut proposal.
                    axes[missing]=((*measured,{'observed':(True,)*len(measured[0])})
                                   if measured is not None else None)
                    used_truncation|=axes[missing] is not None
            if any(a is None for a in axes) or np.sqrt(axes[0][1]*axes[1][1]) < .40:
                break
            votes.append(axes)
        if len(votes) != 2 or any(len(votes[0][a][0]) != len(votes[1][a][0]) for a in(0,1)):
            continue
        combined=[_combine_axis_votes(votes[0][a],votes[1][a],allow_outer_estimate=True) for a in (0,1)]
        if any(axis is None for axis in combined):
            continue
        xs,ys = [axis[0] for axis in combined]
        if mode=='frames' and not used_truncation:
            from .section_evidence import trim_unprinted_extensions
            trimmed,removed=trim_unprinted_extensions(rectified,(xs,ys),[axis[1] for axis in combined])
            if removed:
                updated=[]
                for original,lines in zip(combined,trimmed):
                    observations=dict(original[1])
                    for key in ('estimated','single_scale','disputed'):
                        observations[key]=[i for i,value in enumerate(lines)
                                           if original[0].index(value) in observations[key]]
                    updated.append((lines,observations))
                combined=updated;xs,ys=trimmed
        else:
            removed=[]
        # This route verifies near-square textile sections. It does not invent
        # cells on a woven or striped surface lacking perpendicular divisions.
        aspect = np.median(np.diff(xs))/np.median(np.diff(ys))
        if not .60 <= aspect <= 1.75:
            continue
        evidence = {'method':'sustained_printed_'+mode,'agreeing_scales':2,
                    'scores':[[a[1] for a in vote] for vote in votes],
                    'source_edge_truncation':used_truncation,
                    'closed_frame_extensions_removed':removed,
                    'axis_observations':[axis[1] for axis in combined]}
        if mode == 'colour' and not used_truncation and len(ys) >= 5:
            blank_rows = []
            for at_end, edge, row in ((False, 0, 0), (True, len(ys)-1, len(ys)-2)):
                if edge in combined[1][1]['estimated'] and not truncated[1][int(at_end)]:
                    closing = _blank_colour_row(rectified, xs, ys, at_end)
                    if closing is not None:
                        blank_rows.append({'row': row, 'closing_border': closing})
            if blank_rows:
                evidence['blank_margin_rows'] = blank_rows
        spread = max(axis[1]['spread_px'] for axis in combined)
        uncertainty = max(3.5,spread)
        evidence['boundary_uncertainty_px'] = float(uncertainty)
        issues=(() if all(not(axis[1]['estimated'] or axis[1]['single_scale']) for axis in combined)
                else ('Some printed divisions need confirmation; check the section guides',))
        return CameraPanel(rectified,PanelGrid(xs,ys,.94,'printed',
                           review_reasons=issues,
                           boundary_uncertainty_px=float(uncertainty)),inverse,evidence)
    return None


def _finite_rules(profile):
    """Read the actual positions of sustained rules, including uneven rows."""
    indices = np.flatnonzero(profile > max(12., .48 * np.percentile(profile, 98.5)))
    if not len(indices):
        return None
    bands = np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1)
    # At the cloth rim the projection filter has a truncated support window.
    lines = np.array([(band[0] + band[-1]) / 2 for band in bands
                      if len(band) >= 3 or (len(band) == 2 and
                      min(band[0], len(profile)-1-band[-1]) < .025 * len(profile))])
    if len(lines) < 4:
        return None
    # Decorative hems often contain several close parallel rules. Use the
    # innermost of these, but never remove an internal division.
    gaps = np.diff(lines)
    pitch = np.median(gaps[gaps >= .55 * np.percentile(gaps, 80)])
    while len(lines) >= 4 and lines[1] - lines[0] < .45 * pitch:
        lines = lines[1:]
    while len(lines) >= 4 and lines[-1] - lines[-2] < .45 * pitch:
        lines = lines[:-1]
    gaps = np.diff(lines)
    if (len(lines) < 4 or gaps.min() < .60 * pitch or gaps.max() > 1.48 * pitch
            or lines[-1] - lines[0] < .70 * len(profile)):
        return None
    return lines


def infer_ruled_partition(image):
    plane = _cloth_plane(image)
    if plane is None:
        return None
    view, inverse = plane
    votes = []
    for sigma in (.6, .85):
        axes = [_finite_rules(p) for p in _profiles(view, 'frames', sigma)]
        if any(axis is None for axis in axes):
            return None
        votes.append(axes)
    lines = []
    for a, b in zip(*votes):
        if len(a) != len(b) or np.max(np.abs(a - b)) > 3:
            return None
        lines.append(tuple((a + b) / 2))
    xs, ys = lines
    aspect = np.median(np.diff(xs)) / np.median(np.diff(ys))
    if not .60 <= aspect <= 1.75 or (len(xs)-1)*(len(ys)-1) > 150:
        return None
    return CameraPanel(view, PanelGrid(xs, ys, .93, 'printed', boundary_uncertainty_px=3.5),
                       inverse, {'method': 'observed_frame_intersections', 'agreeing_scales': 2})


def _measure_touching_divisions(lab):
    votes = []
    for sigma in (1.2, 2.2):
        smooth = cv2.GaussianBlur(lab, (0, 0), sigma)
        measurements = []
        for axis in (1, 0):
            along = np.swapaxes(smooth, 0, axis)
            rim = max(1, round(along.shape[1] * .06))
            strips = np.array_split(along[:, rim:-rim], 16, axis=1)
            colours = np.stack([strip.mean(axis=1) for strip in strips], axis=1)
            colours = cv2.GaussianBlur(colours, (1, 0), sigmaY=2, sigmaX=0)
            # Normalise each strip against its local texture before combining
            # them. A strong hem or one dark motif cannot set the whole vote.
            change = np.linalg.norm(colours[12:] - colours[:-12], axis=2)
            baseline = cv2.GaussianBlur(change, (1, 0), sigmaY=14, sigmaX=0)
            peaks = np.maximum(0., change - .9 * baseline) / np.maximum(1.5, baseline)
            profile = np.pad(np.sort(peaks, axis=1)[:, 3:-3].mean(axis=1), (6, 6))
            suggested = _axis_lines(profile)
            if suggested is None:
                return None
            radius = round(np.median(np.diff(suggested)) * .11)
            measured = [_response_center(profile, np.arange(max(0, round(p) - radius),
                         min(len(profile), round(p) + radius + 1)), 0., 1., .32)
                        for p in suggested]
            if any(reading is None for reading in measured):
                return None
            measurements.append(np.array([reading[0] for reading in measured]))
        votes.append(measurements)

    limits = []
    for first, second in zip(*votes):
        pitch = np.median(np.diff(first))
        if len(first) != len(second) or max(abs(first - second)) > pitch * .04:
            return None
        measured = (first + second) / 2
        if min(np.diff(measured)) < pitch * .82 or max(np.diff(measured)) > pitch * 1.18:
            return None
        limits.append(tuple(measured))
    xs, ys = limits
    aspect = np.median(np.diff(xs)) / np.median(np.diff(ys))
    if not .70 <= aspect <= 1.45 or (len(xs) - 1) * (len(ys) - 1) > 150:
        return None
    return xs, ys


def infer_straight_printed_partition(image):
    """Find touching, nearly straight panels when the fabric outline is ambiguous."""
    height, width = image.shape[:2]
    if min(height, width) < 200:
        return None
    scale = min(2., 1000 / max(height, width))
    size = (round(width * scale), round(height * scale))
    small = cv2.resize(image, size, interpolation=cv2.INTER_AREA if scale < 1. else cv2.INTER_LINEAR)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    # Keep the source coordinates even when the analysis image is straightened.
    to_source = np.diag([width / size[0], height / size[1], 1.])
    evidence = {'method': 'sustained_printed_transitions', 'agreeing_scales': 2}
    lines = _measure_touching_divisions(lab)
    if lines is not None:
        return CameraPanel(small, PanelGrid(*lines, .90, 'printed', boundary_uncertainty_px=5.),
                           to_source, evidence)

    # Try a small tilt in either direction. A rotated proposal still needs all
    # the seam tests. Two competing proposals are ambiguous.
    supported = []
    for angle in (-1., 1.):
        rotation = cv2.getRotationMatrix2D((size[0] / 2, size[1] / 2), angle, 1.)
        view = cv2.warpAffine(lab, rotation, size, borderMode=cv2.BORDER_REFLECT_101)
        lines = _measure_touching_divisions(view)
        if lines is not None:
            supported.append((angle, rotation, lines))
    if len(supported) != 1:
        return None
    angle, rotation, lines = supported[0]
    rectified = cv2.warpAffine(small, rotation, size, borderMode=cv2.BORDER_REFLECT_101)
    inverse = np.vstack((cv2.invertAffineTransform(rotation), (0., 0., 1.)))
    grid = PanelGrid(*lines, .90, 'printed', boundary_uncertainty_px=5.)
    return CameraPanel(rectified, grid, to_source @ inverse, {**evidence, 'analysis_rotation_degrees': angle})


def include_faint_ink(image, box, core_bounds=None):
    """Conservative extent check independent of the colour segmentation.

    Large closing estimates local illumination; smoothing suppresses weave.
    Keep substantial weak components as well as the strong foreground, so a
    pale ear or detached detail cannot disappear into a background colour mode.
    """
    gray = cv2.GaussianBlur(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY).astype(np.float32),
                            (0,0),1.3)
    size = max(9,round(min(gray.shape)*.70)|1)
    signal = cv2.morphologyEx(gray,cv2.MORPH_CLOSE,np.ones((size,size),np.uint8))-gray
    rim = np.concatenate([signal[:5].ravel(),signal[-5:].ravel(),
                          signal[:,:5].ravel(),signal[:,-5:].ravel()])
    median = np.median(rim)
    threshold = max(2.5,median+3*np.median(abs(rim-median)))
    _,labels,stats,_ = cv2.connectedComponentsWithStats((signal>threshold).astype(np.uint8))
    inside = np.ones(gray.shape,bool)
    if core_bounds is not None:
        left,top,right,bottom=core_bounds
        inside.fill(False);inside[top:bottom,left:right]=True
    support = np.bincount(labels[inside],minlength=len(stats))
    keep = (stats[:,cv2.CC_STAT_AREA] >= max(4,inside.sum()*.001)) & (
        support >= stats[:,cv2.CC_STAT_AREA]*.55)
    keep[0] = False
    ys,xs = np.nonzero(keep[labels])
    if not len(xs):
        return box
    x,y,w,h = box
    left,top = min(x,int(xs.min())),min(y,int(ys.min()))
    return left,top,max(x+w,int(xs.max()+1))-left,max(y+h,int(ys.max()+1))-top
