"""Read-only diagnosis of the supplied numbers photograph; no production edits."""
from pathlib import Path
import sys,json
from dataclasses import asdict
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from app.imaging.detector import MotifDetector,DetectorSettings
from app.imaging.contrast_grid import infer_contrast_geometry,_shared_background
from app.imaging.panel_grid import PanelGrid
from app.imaging.composition_evidence import shared_compositions

SOURCE=Path('C:/Users/daman/AppData/Local/Temp/codex-clipboard-8af8aaff-3e22-4103-9193-f88917134267.png')
OUT=Path(__file__).parent
# Independent number and outer-object witnesses, inspected on supplied original.
POINTS=[[(145,195),(255,180)],[(408,195),(489,201),(550,221)],
[(679,195),(780,161),(825,208)],[(947,191),(1037,165),(1098,218)],
[(1204,190),(1295,150),(1384,200),(1354,237)],
[(134,378),(222,345),(303,347),(302,411)],[(402,378),(511,338),(542,440)],
[(671,380),(744,333),(810,453)],[(937,380),(1000,343),(1097,444)],
[(1217,380),(1292,335),(1413,439)],[(122,592),(232,532),(291,627)],
[(392,590),(487,531),(587,628)],[(676,591),(756,522),(843,641)],
[(945,582),(1026,520),(1136,639)],[(1229,584),(1308,516),(1423,650)],
[(105,799),(196,736),(299,895)],[(390,798),(474,725),(614,896)],
[(678,805),(747,735),(872,863)],[(952,807),(1023,727),(1163,876)],
[(1255,805),(1335,724),(1461,861)]]

def assess(candidates):
    records=[]
    for number,points in enumerate(POINTS,1):
        owners=[i for i,c in enumerate(candidates) if all(
            c.bounding_box_px[0]<=x<c.bounding_box_px[0]+c.bounding_box_px[2] and
            c.bounding_box_px[1]<=y<c.bounding_box_px[1]+c.bounding_box_px[3] for x,y in points)]
        records.append({'number':number,'owners':owners})
    return records

class Trace(MotifDetector):
    def __init__(self):super().__init__();self.trace=[]
    def _coordinate_appearance(self,image,settings,current,*args,**kwargs):
        self.trace.append({'stage':'before_appearance','result':asdict(current)})
        result=super()._coordinate_appearance(image,settings,current,*args,**kwargs)
        self.trace.append({'stage':'after_appearance','result':asdict(result[0])})
        return result

def main():
    image=cv2.imread(str(SOURCE));assert image is not None
    for run in ('auto','repeat'):
        d=Trace();r=d.detect_with_layout(image,DetectorSettings())
        data={'result':asdict(r),'diagnostics':d.last_diagnostics,'trace':d.trace,'ownership':assess(r.candidates)}
        (OUT/(run+'.json')).write_text(json.dumps(data,indent=2))
        print(run,len(r.candidates),'grid',None if r.panel_grid is None else (r.panel_grid.columns,r.panel_grid.rows,r.panel_grid.source),'whole',sum(len(x['owners'])==1 for x in data['ownership']),flush=True)
    proposals={}
    for channel in ('dark','light','chroma','shared_background'):
        g=infer_contrast_geometry(image,channel=channel)
        proposals[channel]=asdict(g) if g else None
        print('proposal',channel,None if g is None else (g.grid.columns,g.grid.rows,len(g.regions),g.diagnostics),flush=True)
    (OUT/'proposals.json').write_text(json.dumps(proposals,indent=2))
    # A supplied 5x4 layout is an oracle experiment, never automatic success.
    grid=PanelGrid.regular(image.shape[1],image.shape[0],5,4,bounds_px=(60,90,1500,945),confidence=1,source='manual')
    lab=cv2.GaussianBlur(cv2.cvtColor(image,cv2.COLOR_BGR2LAB).astype(np.float32),(0,0),1.)
    model=_shared_background(lab)
    records={}
    for name,background in [('local',None),('global',model)]:
        d=MotifDetector();r=d.detect_in_grid(image,DetectorSettings(),grid,background_model=background)
        records[name]={'candidates':[asdict(c) for c in r],'ownership':assess(r),'plans':d._plans}
        print('oracle',name,len(r),'whole',sum(len(x['owners'])==1 for x in assess(r)),flush=True)
    (OUT/'oracle.json').write_text(json.dumps(records,indent=2))

if __name__=='__main__':main()
