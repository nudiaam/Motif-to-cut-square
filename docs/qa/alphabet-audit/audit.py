"""Read-only application audit; writes evidence, never changes detector behavior."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import sys,json
from dataclasses import asdict,replace
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import cv2
from PySide6.QtWidgets import QApplication
from app.ui.main_window import MainWindow
from app.imaging.detector import MotifDetector,DetectorSettings
from app.imaging.panel_grid import PanelGrid

OUT=Path(__file__).parent
SOURCE=Path('C:/Users/daman/AppData/Local/Temp/codex-clipboard-12d6d19e-0d2e-4ece-89ac-c03fa1b40cd2.png')
# Independent hand-labelled witnesses: letter and main illustration, A through X.
POINTS=[[(168,160),(241,224)],[(376,150),(459,220)],[(577,145),(668,221)],
[(791,135),(875,215)],[(994,126),(1091,190)],[(1219,116),(1323,166)],
[(158,340),(228,421)],[(367,331),(446,410)],[(573,326),(662,414)],
[(792,318),(877,383)],[(1004,312),(1117,351)],[(1234,306),(1328,374)],
[(145,548),(238,618)],[(366,531),(456,612)],[(581,526),(671,595)],
[(798,520),(886,599)],[(1018,518),(1122,602)],[(1254,510),(1349,589)],
[(134,765),(213,846)],[(353,752),(450,810)],[(587,746),(684,828)],
[(813,738),(880,823)],[(1035,731),(1130,827)],[(1284,731),(1374,802)]]

def assess(candidates):
    ownership=[]
    for letter,points in zip('ABCDEFGHIJKLMNOPQRSTUVWX',POINTS):
        ids=[i+1 for i,c in enumerate(candidates) if all(c.bounding_box_px[0]<=x<c.bounding_box_px[0]+c.bounding_box_px[2] and c.bounding_box_px[1]<=y<c.bounding_box_px[1]+c.bounding_box_px[3] for x,y in points)]
        ownership.append({'letter':letter,'owners':ids})
    return ownership

class TracedDetector(MotifDetector):
    def __init__(self):super().__init__();self.trace=[]
    def _detect_once(self,image,settings,*args,**kwargs):
        r=super()._detect_once(image,settings,*args,**kwargs)
        if min(image.shape[:2])>500:self.trace.append({'stage':'raw','shape':list(image.shape),'settings':asdict(settings),'candidates':[asdict(c) for c in r]})
        return r
    def _coordinate_appearance(self,image,settings,current,*args,**kwargs):
        self.trace.append({'stage':'before_appearance','result':asdict(current)})
        r=super()._coordinate_appearance(image,settings,current,*args,**kwargs)
        self.trace.append({'stage':'after_appearance','result':asdict(r[0])})
        return r

def run():
    im=cv2.imread(str(SOURCE)); assert im is not None
    records=[]
    for name,settings in [('auto',DetectorSettings()),('repeat',DetectorSettings()),('no_adaptive',replace(DetectorSettings(),adaptive_planning=False))]:
        d=TracedDetector();r=d.detect_with_layout(im,settings)
        data={'name':name,'result':asdict(r),'diagnostics':d.last_diagnostics,'trace':d.trace,'ownership':assess(r.candidates)}
        (OUT/(name+'.json')).write_text(json.dumps(data,indent=2))
        print(name,len(r.candidates),r.panel_grid.columns if r.panel_grid else None,r.panel_grid.rows if r.panel_grid else None,'whole_pairs',sum(len(x['owners'])==1 for x in data['ownership']),flush=True)
    # Diagnostic oracle: manually supplied approximate 6x4 cells, not automatic success.
    grid=PanelGrid.regular(im.shape[1],im.shape[0],6,4,bounds_px=(95,78,1478,949),confidence=1,source='manual')
    d=MotifDetector();r=d.detect_with_guides(im,DetectorSettings(),grid)
    (OUT/'manual_oracle.json').write_text(json.dumps({'result':asdict(r),'diagnostics':d.last_diagnostics,'ownership':assess(r.candidates)},indent=2))
    print('manual_oracle',len(r.candidates),'whole_pairs',sum(len(x['owners'])==1 for x in assess(r.candidates)),flush=True)
    app=QApplication([]);w=MainWindow();w._load_image(im,'Alphabet audit');w.detect_motifs()
    data={'detections':[asdict(d) for d in w.detections],'layout':asdict(w.logical_layout),'diagnostics':w.detection_diagnostics,'mapper':asdict(w.mapper)}
    (OUT/'ui.json').write_text(json.dumps(data,indent=2))
    print('ui',len(w.detections),'inferred',sum(d.inferred for d in w.detections),'on_grid',sum(d.grid_positioned for d in w.detections),flush=True)
    w.close()

if __name__=='__main__':run()
