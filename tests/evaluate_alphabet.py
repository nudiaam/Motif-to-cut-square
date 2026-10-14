"""Independent letter/illustration witnesses across photographic perturbations."""
from dataclasses import asdict
from pathlib import Path
import argparse
import json
import time
import cv2
import numpy as np
from app.imaging.detector import MotifDetector
from tests.evaluate_accessory_columns import variants

POINTS=[[(168,160),(241,224)],[(376,150),(459,220)],[(577,145),(668,221)],
[(791,135),(875,215)],[(994,126),(1091,190)],[(1219,116),(1323,166)],
[(158,340),(228,421)],[(367,331),(446,410)],[(573,326),(662,414)],
[(792,318),(877,383)],[(1004,312),(1117,351)],[(1234,306),(1328,374)],
[(145,548),(238,618)],[(366,531),(456,612)],[(581,526),(671,595)],
[(798,520),(886,599)],[(1018,518),(1122,602)],[(1254,510),(1349,589)],
[(134,765),(213,846)],[(353,752),(450,810)],[(587,746),(684,828)],
[(813,738),(880,823)],[(1035,731),(1130,827)],[(1284,731),(1374,802)]]

def assess(result,transform):
    groups=cv2.perspectiveTransform(np.array(POINTS,dtype=float).reshape(-1,1,2),transform).reshape(24,2,2)
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
    image=cv2.imread('tests/fixtures/customer_20261012/alphabet_detached_6x4.png');records=[]
    for name,pixels,transform,settings in variants(image):
        detector=MotifDetector();started=time.perf_counter();result=detector.detect_with_layout(pixels,settings)
        record={'variant':name,'count':len(result.candidates),'seconds':time.perf_counter()-started,
                **assess(result,transform),'result':asdict(result),'diagnostics':detector.last_diagnostics}
        records.append(record);Path(args.output).write_text(json.dumps(records,indent=2))
        print(name,record['count'],record['whole_groups'],record['failed_groups'],round(record['seconds'],2),flush=True)
