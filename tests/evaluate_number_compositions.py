"""Independent number/objects witnesses across photographic perturbations."""
from dataclasses import asdict
from pathlib import Path
import argparse
import json
import time
import cv2
import numpy as np
from app.imaging.detector import MotifDetector
from tests.evaluate_accessory_columns import variants

POINTS=[[(145, 195), (255, 180)], [(408, 195), (489, 201), (550, 221)], [(679, 195), (780, 161), (825, 208)], [(947, 191), (1037, 165), (1098, 218)], [(1204, 190), (1295, 150), (1384, 200), (1354, 237)], [(134, 378), (222, 345), (303, 347), (302, 411)], [(402, 378), (511, 338), (542, 440)], [(671, 380), (744, 333), (810, 453)], [(937, 380), (1000, 343), (1097, 444)], [(1217, 380), (1292, 335), (1413, 439)], [(122, 592), (232, 532), (291, 627)], [(392, 590), (487, 531), (587, 628)], [(676, 591), (756, 522), (843, 641)], [(945, 582), (1026, 520), (1136, 639)], [(1229, 584), (1308, 516), (1423, 650)], [(105, 799), (196, 736), (299, 895)], [(390, 798), (474, 725), (614, 896)], [(678, 805), (747, 735), (872, 863)], [(952, 807), (1023, 727), (1163, 876)], [(1255, 805), (1335, 724), (1461, 861)]]

def assess(result,transform):
    groups=[cv2.perspectiveTransform(np.asarray(points,dtype=float).reshape(-1,1,2),transform).reshape(-1,2) for points in POINTS]
    owners=[];misses=[]
    for idx,points in enumerate(groups):
        owning=[i for i,c in enumerate(result.candidates) if all(
            c.bounding_box_px[0]<=x<c.bounding_box_px[0]+c.bounding_box_px[2] and
            c.bounding_box_px[1]<=y<c.bounding_box_px[1]+c.bounding_box_px[3] for x,y in points)]
        if len(owning)!=1:misses.append(idx+1)
        else:owners.extend(owning)
    return {'whole_groups':len(set(owners)),'failed_groups':misses}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    image=cv2.imread('tests/fixtures/customer_20261012/numbers_objects_5x4.png');records=[]
    for name,pixels,transform,settings in variants(image):
        detector=MotifDetector();started=time.perf_counter();result=detector.detect_with_layout(pixels,settings)
        record={'variant':name,'count':len(result.candidates),'seconds':time.perf_counter()-started,
                **assess(result,transform),'result':asdict(result),'diagnostics':detector.last_diagnostics}
        records.append(record);Path(args.output).write_text(json.dumps(records,indent=2))
        print(name,record['count'],record['whole_groups'],record['failed_groups'],round(record['seconds'],2),flush=True)
