"""Deterministic photographic perturbations with independent artwork witnesses."""
from dataclasses import replace, asdict
from pathlib import Path
import argparse,json,time
import cv2
import numpy as np
from app.imaging.detector import MotifDetector,DetectorSettings

POINTS = [[(225,230),(365,160),(365,280)],[(560,235),(715,155),(699,281)],
 [(895,235),(1037,150),(1042,280)],[(1220,235),(1360,195),(1385,300)],
 [(220,500),(350,419),(352,553)],[(540,500),(698,442),(694,547)],
 [(884,500),(1043,440),(1044,540)],[(1250,540),(1387,447),(1387,560)],
 [(200,790),(330,729),(327,850)],[(540,795),(710,742),(699,855)],
 [(880,797),(1040,711),(1044,842)],[(1270,805),(1420,751),(1410,860)]]

def variants(image):
    h,w=image.shape[:2]; identity=np.eye(3)
    yield 'original',image,identity,DetectorSettings()
    for scale in (.75,.5):
        yield f'resize_{scale}',cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA),np.diag([scale,scale,1]),DetectorSettings(minimum_area_px=round(500*scale*scale),merge_distance_px_x=14*scale,merge_distance_px_y=14*scale)
    yield 'dim',np.clip(image.astype(float)*.72,0,255).astype(np.uint8),identity,DetectorSettings()
    yy,xx=np.mgrid[:h,:w];gain=1-.32*np.exp(-((yy/h-.45-.2*xx/w)/.19)**2)
    yield 'diagonal_shadow',np.clip(image*gain[:,:,None],0,255).astype(np.uint8),identity,DetectorSettings()
    yield 'warm',np.clip(image.astype(float)*[.88,.98,1.04],0,255).astype(np.uint8),identity,DetectorSettings()
    rotation=np.vstack([cv2.getRotationMatrix2D((w/2,h/2),2.5,.92),[0,0,1]])
    yield 'rotation',cv2.warpPerspective(image,rotation,(w,h),borderValue=(24,24,24)),rotation,DetectorSettings()
    perspective=cv2.getPerspectiveTransform(np.float32([[0,0],[w,0],[w,h],[0,h]]),np.float32([[40,30],[w-50,10],[w-10,h-20],[20,h-45]]))
    yield 'perspective',cv2.warpPerspective(image,perspective,(w,h),borderValue=(24,24,24)),perspective,DetectorSettings()
    yield 'margin',cv2.copyMakeBorder(image,60,30,40,70,cv2.BORDER_CONSTANT,value=(24,24,24)),np.array([[1,0,40],[0,1,60],[0,0,1]]),DetectorSettings()

def assess(result,transform):
    groups=cv2.perspectiveTransform(np.array(POINTS,dtype=float).reshape(-1,1,2),transform).reshape(12,3,2)
    owners=[];misses=[]
    for idx,points in enumerate(groups):
        owning=[i for i,c in enumerate(result.candidates) if all(c.bounding_box_px[0]<=x<c.bounding_box_px[0]+c.bounding_box_px[2] and c.bounding_box_px[1]<=y<c.bounding_box_px[1]+c.bounding_box_px[3] for x,y in points)]
        if len(owning)!=1:misses.append(idx+1)
        else:owners.extend(owning)
    return {'whole_groups':len(set(owners)),'failed_groups':misses}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    image=cv2.imread('tests/fixtures/customer_20261012/animals_accessories_columns_4x3.png');records=[]
    for name,im,transform,settings in variants(image):
        detector=MotifDetector();started=time.perf_counter();result=detector.detect_with_layout(im,settings)
        record={'variant':name,'count':len(result.candidates),'seconds':time.perf_counter()-started,**assess(result,transform),'result':asdict(result),'diagnostics':detector.last_diagnostics}
        records.append(record);Path(args.output).write_text(json.dumps(records,indent=2))
        print(name,record['count'],record['whole_groups'],round(record['seconds'],2),flush=True)
