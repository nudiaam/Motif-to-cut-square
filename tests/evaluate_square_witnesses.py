"""Run 45 photo variations with independently selected body/accessory points.

Run from the repository root with the private QA originals installed. This
checks composition ownership/retained bounds, not physical machine alignment
or a complete semantic silhouette. Failure exits nonzero for reproducible QA.
"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from app.imaging.detector import MotifDetector
from tests.evaluate_accessory_columns import variants
ROOT=Path('docs/qa/square-contract-20261115')
cv2.setNumThreads(2)
# Deliberately selected on the photographs, independent of detected grids and
# returned bounds. Every selected set must have exactly one composition owner.
POINTS={
 'faint':[[(436,108),(420,270)],[(432,765),(420,927)],[(625,555),(700,705)]],
 'accessories':[[(160,260),(330,205),(330,330)],[(550,250),(690,190),(690,320)],
                [(910,810),(1060,765),(1050,890)]],
}
def sheet_points(quad,cols,rows,accessories=False):
 q=np.asarray(quad,float)
 def at(u,v):return ((1-v)*((1-u)*q[0]+u*q[1])+v*((1-u)*q[3]+u*q[2])).tolist()
 return [[at((c+.35)/cols,(r+.55)/rows),at((c+.80)/cols,(r+.30)/rows),at((c+.80)/cols,(r+.80)/rows)]
         if accessories else [at((c+.5)/cols,(r+.55)/rows)]
         for r in range(rows) for c in range(cols)]
POINTS['holdout_accessories_4x3']=sheet_points(((112,117),(1418,113),(1502,941),(37,947)),4,3,True)
POINTS['holdout_pale_5x4']=sheet_points(((166,48),(1425,103),(1416,957),(81,922)),5,4)
import ast
tree=ast.parse(Path('tests/test_printed_partition.py').read_text(encoding='utf-8'))
regression=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)
    and n.name=='test_perspective_keeps_birds_with_their_flowers_despite_a_bed_highlight')
coordinates={n.targets[0].id:ast.literal_eval(n.value) for n in regression.body
             if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
             and n.targets[0].id in ('heads','flowers')}
POINTS['holdout_birds_7x3']=[list(pair) for pair in zip(coordinates['heads'],coordinates['flowers'])]
reports=[]
for name,groups in POINTS.items():
 image=cv2.imread(str(ROOT/'originals'/(name+'.png')))
 for variant,pixels,transform,settings in variants(image):
  r=MotifDetector().detect_with_layout(pixels,settings)
  owners=[];failed=[]
  for i,points in enumerate(groups):
   mapped=cv2.perspectiveTransform(np.asarray(points,float).reshape(-1,1,2),transform).reshape(-1,2)
   hits=[j for j,c in enumerate(r.candidates) if all(x<=px<x+w and y<=py<y+h
         for px,py in mapped for x,y,w,h in [c.bounding_box_px])]
   if len(hits)!=1:failed.append(i+1)
   else:owners.append(hits[0])
  reports.append({'case':name,'variant':variant,'witness_groups':len(groups),
                  'distinct_owners':len(set(owners)),'failed_groups':failed})
  (ROOT/'witnesses.json').write_text(json.dumps({'source_points':POINTS,'checks':reports},indent=2))
  print(name,variant,'owners',len(set(owners)),'of',len(groups),'failed',failed,flush=True)

assert len(reports)==45
assert not any(r['failed_groups'] for r in reports), 'A body or accessory witness lost its unique owner'
assert all(r['distinct_owners']==r['witness_groups'] for r in reports), 'Neighbouring compositions were merged'
