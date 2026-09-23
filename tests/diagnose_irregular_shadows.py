"""Read-only causal probes of irregular shadows. No production parameter edits.

Run: python -m tests.diagnose_irregular_shadows
Known cell bounds are diagnostic oracles only, not inputs to automatic detection.
"""
from dataclasses import asdict
import argparse
import hashlib
import inspect
import json
from pathlib import Path
import textwrap
from unittest.mock import patch

import cv2
import numpy as np

import app.imaging.detector as detector_module
from app.imaging.detector import DetectorSettings, MotifDetector
from app.imaging.bed_reference import FabricEvidence, locate_bright_fabric
from app.imaging.scene_profile import illumination_view
from app.imaging.panel_grid import PanelGrid
from app.imaging.logical_layout import LayoutObservation, fit_logical_layout


ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/qa/irregular-shadows'
FIXTURES=ROOT/'tests/fixtures'
SETTINGS=DetectorSettings()


def run(image,name,draw=False):
    detector=MotifDetector()
    result=detector.detect_with_layout(image,SETTINGS)
    row={'name':name,'count':len(result.candidates),
         'grid':[result.panel_grid.columns,result.panel_grid.rows] if result.panel_grid else None,
         'diagnostics':detector.last_diagnostics,
         'candidates':[asdict(c) for c in result.candidates]}
    if draw:overlay(image,result.candidates,name)
    print(name,row['count'],row['grid'],detector.last_diagnostics['fabric_status'],flush=True)
    return row


def overlay(image,candidates,name):
    display=image.copy()
    for i,candidate in enumerate(candidates,1):
        x,y,w,h=candidate.bounding_box_px
        cv2.rectangle(display,(x,y),(x+w,y+h),(30,50,245),2)
        cv2.putText(display,str(i),(x,y+16),cv2.FONT_HERSHEY_SIMPLEX,.55,(30,50,245),2)
    cv2.imwrite(str(OUT/(name+'-bounds.png')),display)


def shadow_field(image,kind):
    h,w=image.shape[:2]
    y,x=np.mgrid[0:h,0:w].astype(np.float32)
    x/=w;y/=h
    if kind=='horizontal':distance=(y-.78)/.13
    elif kind=='vertical':distance=(x-.45)/.13
    elif kind=='diagonal':distance=(x-.68*y-.12)/.10
    else:
        patches=sum(np.exp(-((x-cx)**2+(y-cy)**2)/(2*.085**2))
                    for cx,cy in ((.18,.20),(.43,.53),(.71,.33),(.84,.80),(.39,.90)))
        return 1.-.60*np.clip(patches,0,1)
    return 1.-.60*np.exp(-distance**2/2)


def experimental_compensation(image, mask=None):
    """Fixed diagnostic settings, shared by all collections; not production."""
    if mask is None:
        h,w=image.shape[:2]
        mask=np.zeros((h,w),np.uint8)
        mask[round(h*.05):round(h*.95),round(w*.05):round(w*.95)]=255
    lab=cv2.cvtColor(image,cv2.COLOR_BGR2LAB)
    field=cv2.morphologyEx(lab[...,0],cv2.MORPH_CLOSE,np.ones((151,151),np.uint8)).astype(np.float32)
    field=cv2.GaussianBlur(field,(0,0),15)
    target=np.percentile(field[mask>0],80)
    lab[...,0]=np.clip(lab[...,0].astype(np.float32)*np.clip(target/np.maximum(field,1),1,1.6),0,255).astype(np.uint8)
    return cv2.cvtColor(lab,cv2.COLOR_LAB2BGR)


def trace_foreground(image):
    captures=[]
    original=MotifDetector._remove_camera_surround
    def observe(mask):
        cleaned=original(mask)
        count,labels,stats,_=cv2.connectedComponentsWithStats(mask)
        components=[]
        for label in range(1,count):
            x,y,w,h,area=map(int,stats[label])
            if area>=500:
                components.append({'box':[x,y,w,h],'area':area,
                    'removed_by_camera_cleanup':bool(np.any((labels==label)&(cleaned==0)))})
        captures.append({'foreground_pixels_before':int(np.count_nonzero(mask)),
                         'foreground_pixels_after':int(np.count_nonzero(cleaned)),
                         'components':components})
        cv2.imwrite(str(OUT/'foreground-before-camera-cleanup.png'),mask)
        cv2.imwrite(str(OUT/'foreground-after-camera-cleanup.png'),cleaned)
        return cleaned
    with patch.object(MotifDetector,'_remove_camera_surround',side_effect=observe):
        candidates=MotifDetector()._detect_once(image,SETTINGS)
    return captures,candidates


def cloth_threshold(image,name):
    h,w=image.shape[:2];s=min(1.,1000/max(h,w))
    gray=cv2.cvtColor(cv2.resize(image,(round(w*s),round(h*s))),cv2.COLOR_BGR2GRAY)
    threshold,binary=cv2.threshold(cv2.GaussianBlur(gray,(9,9),0),0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    contours,_=cv2.findContours(binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    fractions=sorted([cv2.contourArea(c)/binary.size for c in contours],reverse=True)
    cv2.imwrite(str(OUT/(name+'-cloth-threshold.png')),binary)
    return {'otsu_threshold':threshold,'largest_component_fractions':fractions[:8],
            'evidence_status':locate_bright_fabric(image).reason}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source_files=sorted((ROOT/'app').rglob('*.py'))
    before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}
    images={name:cv2.imread(str(FIXTURES/path)) for name,path in {
        'transport_clean':'transport_dashed_shared.png',
        'transport_irregular':'transport_irregular_shadows.png',
        'dogs':'generated/straight/dogs_6x4.png',
        'hearts':'generated/straight/hearts_6x4.png'}.items()}
    baselines=[run(im,name,draw=True) for name,im in images.items()]
    threshold_profiles={name:cloth_threshold(image,name) for name,image in images.items()}
    sweep=[]
    for name in ('transport_clean','transport_irregular'):
        for sensitivity in (35,45,55,65,75,85):
            candidates=MotifDetector()._detect_once(images[name],DetectorSettings(sensitivity=sensitivity))
            layout=fit_logical_layout([LayoutObservation(i,c.center_px,c.bounding_box_px)
                                       for i,c in enumerate(candidates)])
            sweep.append({'image':name,'sensitivity':sensitivity,'raw_count':len(candidates),
                          'layout':[layout.columns,layout.rows],'confidence':layout.confidence,
                          'occupancy':layout.occupancy})
    trace,_=trace_foreground(images['transport_irregular'])
    probes=[]
    for name in ('transport_clean','dogs','hearts'):
        for kind in ('horizontal','vertical','diagonal','patches'):
            shadowed=(images[name].astype(np.float32)*shadow_field(images[name],kind)[...,None]).astype(np.uint8)
            probes.append(run(shadowed,name+'_'+kind,draw=kind=='patches'))
    image=images['transport_irregular']
    ablations=[]
    # Crop only for a diagnostic: removes much of the unrelated dark surround.
    ablations.append(run(image[40:990,80:1470],'crop_surround',draw=True))
    original=MotifDetector._detect_once
    def without_camera_cleanup(self,pixels,settings,*,local_context=False):
        return original(self,pixels,settings,local_context=True)
    with patch.object(MotifDetector,'_detect_once',without_camera_cleanup):
        ablations.append(run(image,'no_camera_cleanup',draw=True))
    # Same detector, same pixels, only luminance contribution removed in memory.
    source=textwrap.dedent(inspect.getsource(original)).replace('0.35 *','0.0 *')
    namespace=dict(vars(detector_module));exec(source,namespace)
    with patch.object(MotifDetector,'_detect_once',namespace['_detect_once']):
        ablations.append(run(image,'chroma_only',draw=True))
    manual_mask=np.zeros(image.shape[:2],np.uint8);manual_mask[40:990,80:1470]=255
    forced=FabricEvidence(manual_mask,'Diagnostic manually supplied cloth bounds')
    with patch('app.imaging.bed_reference.locate_bright_fabric',return_value=forced):
        ablations.append(run(image,'oracle_cloth_mask',draw=True))
    # Supplying correct cell geometry separates grid discovery from segmentation.
    grid=PanelGrid.regular(image.shape[1],image.shape[0],6,4,
                           bounds_px=(110,100,1435,915),confidence=1.,source='manual')
    local=MotifDetector().detect_in_grid(image,SETTINGS,grid)
    overlay(image,local,'oracle_grid')
    oracle={'count':len(local),'grid':asdict(grid),'candidates':[asdict(c) for c in local],
            'note':'Approximate manually supplied cell bounds; not automatic detection or full-mask ground truth'}
    # Simple generic 2D compensation is an experiment, not an accepted solution.
    alternative=experimental_compensation(image,manual_mask)
    ablations.append(run(alternative,'experimental_2d_compensation',draw=True))
    print('oracle_grid',len(local),flush=True)
    unchanged=all(hashlib.sha256(p.read_bytes()).hexdigest()==before[str(p.relative_to(ROOT))] for p in source_files)
    assert unchanged,'Diagnostic must not modify production files'
    report={'application_files_unchanged':unchanged,'application_sha256':before,
            'baselines':baselines,'threshold_profiles':threshold_profiles,'sensitivity_sweep':sweep,
            'foreground_trace':trace,'controlled_shadows':probes,'ablations':ablations,'oracle_grid':oracle,
            'oracle_mask_enables_row_compensation':illumination_view(image,manual_mask) is not None}
    (OUT/'diagnosis.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


def cross_check():
    """Repeat the same compensation on every collection, including controls."""
    OUT.mkdir(parents=True,exist_ok=True)
    fingerprints={p:hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (ROOT/'app').rglob('*.py')}
    results=[]
    for name,path in (
        ('transport_clean','transport_dashed_shared.png'),
        ('transport_irregular','transport_irregular_shadows.png'),
        ('dogs','generated/straight/dogs_6x4.png'),
        ('hearts','generated/straight/hearts_6x4.png'),
    ):
        image=cv2.imread(str(FIXTURES/path))
        kinds=('none',) if name=='transport_irregular' else ('none','horizontal','vertical','diagonal','patches')
        for kind in kinds:
            source=image if kind=='none' else (image.astype(np.float32)*shadow_field(image,kind)[...,None]).astype(np.uint8)
            results.append(run(experimental_compensation(source),name+'_'+kind+'_2d',
                               draw=name=='transport_irregular' or kind=='patches'))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in fingerprints.items())
    (OUT/'compensation-cross-check.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cross-check',action='store_true',help='Run the separate compensation comparison')
    args=parser.parse_args()
    cross_check() if args.cross_check else main()
