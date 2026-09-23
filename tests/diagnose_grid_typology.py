"""Controlled texture/grid probes, independent of vehicle appearance.

Run: python -m tests.diagnose_grid_typology
These procedural images isolate mechanisms; they are not customer photographs.
"""
from dataclasses import asdict
import json
from pathlib import Path

import cv2
import numpy as np

from app.imaging.detector import DetectorSettings, MotifCandidate, MotifDetector
from app.imaging.detection_plan import choose_grid
from app.imaging.panel_grid import PanelGrid


OUTPUT = Path(__file__).resolve().parents[1]/'docs/qa/grid-typology'


def panel(columns=6, rows=4, *, stars=False, frames=False, varied_sizes=False):
    step=120
    image=np.full((rows*step+80,columns*step+80,3),25,np.uint8)
    image[20:-20,20:-20]=(207,189,168)
    for row in range(rows):
        for col in range(columns):
            x,y=40+col*step,40+row*step
            if stars:
                for dx,dy in ((15,15),(72,18),(22,96),(96,87)):
                    cv2.drawMarker(image,(x+dx,y+dy),(233,230,221),cv2.MARKER_STAR,9,1)
            if frames:
                for offset in range(4,112,12):
                    for sy in (y+4,y+115):cv2.line(image,(x+offset,sy),(x+offset+7,sy),(233,230,221),2)
                    for sx in (x+4,x+115):cv2.line(image,(sx,y+offset),(sx,y+offset+7),(233,230,221),2)
            ax,ay=((42,18) if (row+col)%2 else (16,40)) if varied_sizes else (27,30)
            color=((40,180,235),(210,120,40),(55,130,55))[(row+col)%3]
            cv2.ellipse(image,(x+60,y+60),(ax,ay),0,0,360,(22,22,22),-1)
            cv2.ellipse(image,(x+60,y+60),(ax-3,ay-3),0,0,360,color,-1)
    return image


def competing_periods():
    """Strong decorative lines must not be assumed to be composition divisions."""
    image=panel()
    correct=PanelGrid.regular(800,560,6,4,bounds_px=(40,40,760,520),confidence=.95,source='pattern')
    decorative=PanelGrid.regular(800,560,4,3,bounds_px=(40,40,760,520),confidence=.95,source='visual')
    for x in decorative.x_lines_px[1:-1]:cv2.line(image,(round(x),40),(round(x),520),(250,250,250),3)
    for y in decorative.y_lines_px[1:-1]:cv2.line(image,(40,round(y)),(760,round(y)),(250,250,250),3)
    # Exact, independently known centres isolate ranking from segmentation.
    candidates=[MotifCandidate((100+c*120,100+r*120),(73+c*120,70+r*120,55,61),.9,1800)
                for r in range(4) for c in range(6)]
    chosen,measurements=choose_grid(image,[('decorative',decorative),('compositions',correct)],candidates,
                                    stable_routes=('compositions',))
    return image,{'chosen':chosen,'measurements':measurements,
                  'known_composition_grid':[6,4],'decorative_grid':[4,3],
                  'scope':'grid ranking only, exact centres supplied as a diagnostic oracle'}


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    cases=[]
    for columns,rows in ((6,4),(5,3)):
        for name,options in (
                ('plain',{}),('stars',{'stars':True}),('dashed',{'frames':True}),
                ('stars_dashed',{'stars':True,'frames':True}),
                ('mixed_extents',{'stars':True,'frames':True,'varied_sizes':True})):
            image=panel(columns,rows,**options)
            detector=MotifDetector()
            result=detector.detect_with_layout(image,DetectorSettings(minimum_area_px=150))
            key=f'{columns}x{rows}_{name}'
            cv2.imwrite(str(OUTPUT/(key+'.png')),image)
            cases.append({'name':key,'expected':columns*rows,'detected':len(result.candidates),
                          'grid':asdict(result.panel_grid) if result.panel_grid else None,
                          'diagnostics':detector.last_diagnostics})
            print(key,len(result.candidates),(result.panel_grid.columns,result.panel_grid.rows)
                  if result.panel_grid else None,flush=True)
    image,ranking=competing_periods()
    cv2.imwrite(str(OUTPUT/'competing-periods.png'),image)
    print('isolated_ranking',ranking,flush=True)
    (OUTPUT/'diagnosis.json').write_text(json.dumps({'cases':cases,'isolated_ranking':ranking},indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
