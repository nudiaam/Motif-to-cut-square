"""Compare preservation policies on the two shadow regression witnesses."""
import inspect,json
from pathlib import Path
from unittest.mock import patch
from dataclasses import asdict
import cv2,numpy as np
import app.imaging.detector as module
import app.imaging.detection_plan as planner
from tests.diagnose_irregular_shadows import shadow_field
from tests.test_irregular_shadows import TRANSPORT_WITNESSES

source=inspect.getsource(planner.choose_grid)
source=source.replace("(baseline >= .95 and retained < baseline-.03\n                         and grids[row['route']].source not in ('manual','visual','camera','reference')) or\n                        ",'')
namespace=dict(planner.__dict__);exec(source,namespace)
fixtures=Path('tests/fixtures');out=Path('docs/qa/group-extent-audit/fixed/shadow-regression');out.mkdir(exist_ok=True)
images={'scaled':cv2.resize(cv2.imread(str(fixtures/'transport_irregular_shadows.png')),None,fx=1.5,fy=1.5)}
image=cv2.imread(str(fixtures/'transport_dashed_shared.png'))
images['vertical']=(image.astype(np.float32)*shadow_field(image,'vertical')[...,None]).astype(np.uint8)
for name,image in images.items():
    for policy in ('current','old_selector','no_mask','both'):
        with patch.object(module,'choose_grid',namespace['choose_grid'] if policy in ('old_selector','both') else planner.choose_grid),patch.object(module,'foreground_mask',lambda image:None if policy in ('no_mask','both') else __import__('app.imaging.content_preservation',fromlist=['foreground_mask']).foreground_mask(image)):
            detector=module.MotifDetector();result=detector.detect_with_layout(image,module.DetectorSettings())
        missing=[]
        if name=='scaled':
            missing=[(px,py) for _,points in TRANSPORT_WITNESSES for px,py in points if not any(x<=px*1.5<=x+w and y<=py*1.5<=y+h for x,y,w,h in (c.bounding_box_px for c in result.candidates))]
        print(name,policy,len(result.candidates),None if result.panel_grid is None else (result.panel_grid.columns,result.panel_grid.rows,result.panel_grid.source),'missing',missing,flush=True)
        (out/f'{name}-{policy}.json').write_text(json.dumps({'result':asdict(result),'diagnostics':detector.last_diagnostics,'missing':missing},indent=2))
