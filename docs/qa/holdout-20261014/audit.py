"""Reproduce the five newly supplied originals, without production changes."""
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
import json,time
import cv2
from app.imaging.detector import MotifDetector,DetectorSettings
from app.imaging.hierarchical_compositions import infer_hierarchical_compositions

ROOT=Path('docs/qa/holdout-20261014');ROOT.mkdir(exist_ok=True)
FILES={
 'letters_compact':('codex-clipboard-1c77cfba-b684-4568-a6bc-cf48fee998ce.png',12,(4,3)),
 'numbers_flat':('codex-clipboard-99730b04-f542-45b8-ad67-bcc32b5e4d26.png',20,(5,4)),
 'quotes':('codex-clipboard-d91cadf4-5328-4e9f-b2dd-aa61241c1859.png',16,(4,4)),
 'numbers_felt':('codex-clipboard-a718f8f1-10ec-40b8-a0d3-45cf4470a11a.png',20,(5,4)),
 'animals_panels':('codex-clipboard-f0c795aa-83cf-4add-8ec2-8cfff5be8315.png',12,(4,3)),
}

class Trace(MotifDetector):
    def __init__(self):super().__init__();self.trace=[]
    def _coordinate_appearance(self,image,settings,current,*args,**kw):
        self.trace.append({'stage':'before_appearance','result':asdict(current)})
        result=super()._coordinate_appearance(image,settings,current,*args,**kw)
        self.trace.append({'stage':'after_appearance','result':asdict(result[0])})
        return result

def run():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'current-runs');out=parser.parse_args().output;out.mkdir(exist_ok=True)
    for name,(filename,count,shape) in FILES.items():
        original=Path('C:/Users/daman/AppData/Local/Temp')/filename
        source=ROOT/f'{name}.png'
        if not source.exists():source.write_bytes(original.read_bytes())
        image=cv2.imread(str(source));runs=[]
        for label,active in (('current',True),('without_compound',False)):
            detector=Trace();start=time.perf_counter()
            with __import__('contextlib').nullcontext() if active else patch('app.imaging.compound_grid.infer_compound_grid',return_value=None):
                result=detector.detect_with_layout(image,DetectorSettings())
            runs.append({'mode':label,'seconds':time.perf_counter()-start,'result':asdict(result),'diagnostics':detector.last_diagnostics,'trace':detector.trace})
            print(name,label,len(result.candidates),None if result.panel_grid is None else (result.panel_grid.columns,result.panel_grid.rows,result.panel_grid.source),flush=True)
        hierarchy=infer_hierarchical_compositions(image)
        data={'expected_count':count,'expected_shape':shape,'runs':runs,'hierarchy':None if hierarchy is None else {'grid':asdict(hierarchy[0]),'groups':hierarchy[1],'diagnostics':hierarchy[2]}}
        (out/f'{name}.json').write_text(json.dumps(data,indent=2))

if __name__=='__main__':run()
