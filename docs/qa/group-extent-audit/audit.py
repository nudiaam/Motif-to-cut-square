"""Read-only audit of ownership, source bounds and fixed-size cut placement."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
from dataclasses import asdict,replace
import sys,json
import cv2
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from app.imaging.detector import MotifDetector,DetectorSettings,DetectionResult
from app.imaging.hierarchical_compositions import infer_hierarchical_compositions
from app.ui.main_window import MainWindow
from PySide6.QtWidgets import QApplication

OUT=Path(__file__).parent
SOURCES={
 'cocktails':Path('C:/Users/daman/AppData/Local/Temp/codex-clipboard-72f414d9-dd16-4526-a5d5-d15403d9bb98.png'),
 'quotes':Path('C:/Users/daman/AppData/Local/Temp/codex-clipboard-05adb881-139b-456b-8f9f-6f8248646c52.png')}
POINTS={
 'cocktails':[
 [(181,263),(248,186),(259,303),(269,350),(182,356)],
 [(411,263),(459,194),(482,249),(503,333),(415,358)],
 [(625,283),(674,193),(709,277),(724,351),(625,354)],
 [(865,264),(903,194),(943,249),(952,340),(865,350)],
 [(1087,289),(1127,189),(1161,236),(1180,352),(1091,357)],
 [(1306,280),(1367,189),(1388,252),(1394,343),(1308,356)],
 [(182,542),(207,436),(259,557),(288,544),(268,601)],
 [(408,541),(453,445),(496,507),(503,591),(410,597)],
 [(633,509),(680,449),(714,519),(729,601),(633,604)],
 [(864,536),(897,436),(940,504),(953,587),(865,612)],
 [(1096,524),(1154,494),(1174,545),(1187,603),(1093,610)],
 [(1322,550),(1389,460),(1408,551),(1401,586),(1322,604)],
 [(190,795),(244,689),(272,755),(283,858),(194,863)],
 [(412,807),(450,729),(512,789),(514,850),(417,855)],
 [(643,738),(689,674),(719,778),(725,853),(643,853)],
 [(856,806),(919,697),(943,771),(953,850),(859,857)],
 [(1096,811),(1168,722),(1189,820),(1177,853),(1098,855)],
 [(1320,805),(1394,685),(1392,822),(1394,857),(1320,852)]],
 'quotes':[
 [(407,164),(457,210),(373,264),(475,265)],[(664,164),(657,213),(598,263),(713,263)],
 [(867,165),(891,213),(832,260),(946,261)],[(1118,164),(1194,213),(1050,260),(1198,264)],
 [(407,367),(357,405),(491,405),(347,475),(489,475)],[(635,366),(699,401),(601,457),(708,467)],
 [(889,366),(849,400),(832,462),(951,462)],[(1128,366),(1055,407),(1215,406),(1071,469),(1192,469)],
 [(407,560),(458,608),(342,679),(495,679)],[(615,560),(692,605),(585,674),(727,673)],
 [(889,559),(890,606),(825,667),(953,674)],[(1127,560),(1177,606),(1090,672),(1154,671)],
 [(384,759),(422,809),(345,872),(494,871)],[(638,759),(698,811),(591,865),(706,866)],
 [(878,759),(898,809),(833,865),(974,870)],[(1082,759),(1201,810),(1080,864),(1218,873)]]}

def ownership(boxes,points):
    return [{'group':i+1,'owners':[j for j,(x,y,w,h) in enumerate(boxes)
        if all(x<=px<x+w and y<=py<y+h for px,py in ps)]} for i,ps in enumerate(points)]

class Trace(MotifDetector):
    def __init__(self):super().__init__();self.trace=[]
    def _coordinate_appearance(self,image,settings,current,*args,**kw):
        self.trace.append({'stage':'before_appearance','result':asdict(current)})
        r=super()._coordinate_appearance(image,settings,current,*args,**kw)
        self.trace.append({'stage':'after_appearance','result':asdict(r[0])})
        return r

def run():
    global OUT
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT/'fixed')
    OUT=parser.parse_args().output;OUT.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    for name,path in SOURCES.items():
        image=cv2.imread(str(path));records=[]
        for label,settings in [('auto',DetectorSettings()),('repeat',DetectorSettings()),('free',replace(DetectorSettings(),layout_mode='free'))]:
            d=Trace();result=d.detect_with_layout(image,settings)
            o=ownership([c.bounding_box_px for c in result.candidates],POINTS[name])
            data={'result':asdict(result),'diagnostics':d.last_diagnostics,'trace':d.trace,'ownership':o}
            (OUT/f'{name}-{label}.json').write_text(json.dumps(data,indent=2))
            print(name,label,len(result.candidates),'complete witnesses',sum(len(x['owners'])==1 for x in o),'grid',None if result.panel_grid is None else (result.panel_grid.columns,result.panel_grid.rows,result.panel_grid.source),flush=True)
        hierarchy=infer_hierarchical_compositions(image)
        hdata=None if hierarchy is None else {'grid':asdict(hierarchy[0]),'groups':hierarchy[1],'diagnostics':hierarchy[2],
            'ownership':ownership([g[0] for g in hierarchy[1]],POINTS[name])}
        (OUT/f'{name}-hierarchy.json').write_text(json.dumps(hdata,indent=2))
        print(name,'independent hierarchy',None if hdata is None else (len(hdata['groups']),sum(len(o['owners'])==1 for o in hdata['ownership'])),flush=True)
        w=MainWindow();w._load_image(image,name);w.change_cut_size(4,4);w.detect_motifs();app.processEvents()
        cuts=[]
        for d in w.detections:
            cx,cy=d.center_px
            # Mapper maps inches to source pixels, preserving independent x/y scale.
            left,top=w.mapper.inches_to_pixel(d.center_inches[0]-2,d.center_inches[1]-2)
            right,bottom=w.mapper.inches_to_pixel(d.center_inches[0]+2,d.center_inches[1]+2)
            cuts.append((left,top,right-left,bottom-top))
        data={'detections':[asdict(d) for d in w.detections],'layout':asdict(w.logical_layout),'mapper':asdict(w.mapper),
              'cut_ownership':ownership(cuts,POINTS[name]),'cuts':cuts,'diagnostics':w.detection_diagnostics}
        (OUT/f'{name}-ui.json').write_text(json.dumps(data,indent=2))
        print(name,'ui',len(w.detections),'cuts contain full witnesses',sum(len(o['owners'])==1 for o in data['cut_ownership']),flush=True)
        w.close()

if __name__=='__main__':run()
