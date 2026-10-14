"""Read-only causal audit of the new number/object composition source."""
import json,time
from pathlib import Path
from dataclasses import asdict,replace
import cv2
import numpy as np
from app.imaging.detector import MotifDetector,DetectorSettings
from app.imaging.hierarchical_compositions import infer_hierarchical_compositions

OUT=Path('docs/qa/numbers-audit/alternating-columns');OUT.mkdir(exist_ok=True)
SOURCE=OUT/'source.png'
POINTS=[[(193,217),(277,209),(277,257)],[(445,213),(531,185),(531,250)],[(685,218),(768,179),(819,226)],[(939,213),(1011,186),(1076,248)],[(1204,219),(1279,193),(1375,193),(1342,248)],
[(170,416),(247,380),(330,433)],[(434,418),(502,376),(580,376),(534,455)],[(676,415),(744,373),(830,457)],[(928,415),(1007,370),(1086,451)],[(1201,412),(1285,360),(1386,445)],
[(171,610),(246,557),(332,557),(305,620)],[(432,611),(516,556),(596,556),(568,646)],[(681,611),(759,556),(845,557),(820,643)],[(932,611),(1009,556),(1111,556),(1082,624)],[(1209,611),(1301,560),(1399,560),(1399,659)],
[(164,810),(234,759),(318,759),(318,853)],[(427,810),(498,761),(582,761),(554,854)],[(681,810),(751,755),(841,755),(841,852)],[(932,810),(1009,757),(1120,756),(1120,850)],[(1202,810),(1314,745),(1410,745),(1410,866)]]

def ownership(candidates,points):
    boxes=[c.bounding_box_px if hasattr(c,'bounding_box_px') else c[0] for c in candidates]
    return [{'group':i+1,'owners':[j for j,(x,y,w,h) in enumerate(boxes)
        if all(x<=px<x+w and y<=py<y+h for px,py in group)]} for i,group in enumerate(points)]

class Trace(MotifDetector):
    def __init__(self):super().__init__();self.before=None
    def _coordinate_appearance(self,image,settings,current,*args,**kwargs):
        self.before=asdict(current)
        return super()._coordinate_appearance(image,settings,current,*args,**kwargs)

def run():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT/'fixed')
    output=parser.parse_args().output;output.mkdir(parents=True,exist_ok=True)
    image=cv2.imread(str(SOURCE));records=[]
    for scale in (.5,1.,1.5):
        pixels=cv2.resize(image,None,fx=scale,fy=scale)
        points=[[(x*scale,y*scale) for x,y in group] for group in POINTS]
        detector=Trace();started=time.perf_counter();result=detector.detect_with_layout(pixels,DetectorSettings())
        hierarchy=infer_hierarchical_compositions(pixels)
        owners=ownership(result.candidates,points)
        data={'scale':scale,'seconds':time.perf_counter()-started,'result':asdict(result),'before_appearance':detector.before,
              'ownership':owners,'diagnostics':detector.last_diagnostics,
              'hierarchy':None if hierarchy is None else {'grid':asdict(hierarchy[0]),'groups':hierarchy[1],
                  'support':hierarchy[2],'ownership':ownership(hierarchy[1],points)}}
        records.append(data);(output/'results.json').write_text(json.dumps(records,indent=2))
        print(scale,len(result.candidates),None if result.panel_grid is None else (result.panel_grid.columns,result.panel_grid.rows,result.panel_grid.source),
              'whole',sum(len(g['owners'])==1 for g in owners),'hierarchy',None if hierarchy is None else (len(hierarchy[1]),sum(len(g['owners'])==1 for g in data['hierarchy']['ownership'])),flush=True)

if __name__=='__main__':run()
