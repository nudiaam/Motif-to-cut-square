"""Source-pixel witnesses, framing probes and the preceding mixed-panel fix."""
import importlib.util
import json
from pathlib import Path
import sys
import time

import cv2
import numpy as np

from app.imaging.detector import MotifDetector, DetectorSettings
from tests.test_shared_background import WITNESSES, FIXTURE

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/qa/dark-leaves'


def main():
    image=cv2.imread(str(FIXTURE));records=[]
    variants=[('original',image,1.,0),
              ('half',cv2.resize(image,None,fx=.5,fy=.5),.5,0),
              ('larger',cv2.resize(image,None,fx=1.5,fy=1.5),1.5,0),
              ('surround',cv2.copyMakeBorder(image,60,60,60,60,cv2.BORDER_CONSTANT,
                                            value=(45,45,45)),1.,60)]
    for name,source,scale,offset in variants:
        before=source.copy();start=time.perf_counter();detector=MotifDetector()
        result=detector.detect_with_layout(source,DetectorSettings())
        owners=[[i for i,c in enumerate(result.candidates)
                 if all(c.bounding_box_px[0]<=x*scale+offset<=c.bounding_box_px[0]+c.bounding_box_px[2]
                        and c.bounding_box_px[1]<=y*scale+offset<=c.bounding_box_px[1]+c.bounding_box_px[3]
                        for x,y in points)] for points in WITNESSES]
        records.append(dict(variant=name,count=len(result.candidates),
                            grid=[result.panel_grid.columns,result.panel_grid.rows],
                            witness_owners=owners,seconds=time.perf_counter()-start))
        assert len(result.candidates)==15 and records[-1]['grid']==[5,3]
        assert all(len(hits)==1 for hits in owners) and len({hits[0] for hits in owners})==15
        np.testing.assert_array_equal(source,before)
        if name=='original':
            (OUT/'after.json').write_text(json.dumps(detector.last_diagnostics,indent=2))
        print(records[-1],flush=True)
    (OUT/'witness-variants.json').write_text(json.dumps(records,indent=2))

    # This saved detector predates the shared-background route. Its existing
    # segmentation calls omit the new optional background model.
    name='app.imaging._before_shared_background'
    spec=importlib.util.spec_from_file_location(name,OUT/'detector.py')
    old=importlib.util.module_from_spec(spec);sys.modules[name]=old;spec.loader.exec_module(old)
    mixed=cv2.imread(str(FIXTURE.parent/'mixed_icons_6x4.png'))
    old_result=old.MotifDetector().detect_with_layout(mixed,old.DetectorSettings())
    new_result=MotifDetector().detect_with_layout(mixed,DetectorSettings())
    geometry=lambda result:sorted((c.bounding_box_px,c.center_px) for c in result.candidates)
    record={'previous_count':len(old_result.candidates),'count':len(new_result.candidates),
            'same_boxes_and_centres':geometry(old_result)==geometry(new_result)}
    (OUT/'mixed-icons-control.json').write_text(json.dumps(record,indent=2))
    assert record['same_boxes_and_centres'] and record['count']==24
    print(record,flush=True)


if __name__=='__main__':main()
