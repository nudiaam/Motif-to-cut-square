"""Reconstruct the pre-preservation policy in memory, without editing the app."""
import inspect,types,sys,runpy,json
from pathlib import Path
from dataclasses import asdict
import cv2
import app.imaging.detector as current
import app.imaging.detection_plan as planner

choose_source=inspect.getsource(planner.choose_grid).replace(
    "(baseline >= .95 and retained < baseline-.03\n                         and grids[row['route']].source not in ('manual','visual','camera','reference')) or\n                        ",'')
choose_namespace=dict(planner.__dict__)
exec(compile(choose_source,'<baseline-grid-choice>','exec'),choose_namespace)
module=types.ModuleType('app.imaging._qa_baseline');module.__package__='app.imaging'
sys.modules[module.__name__]=module
source=Path(current.__file__).read_text().replace(
    '2026-10-14-composition-content-preservation','2026-10-13-whole-composition-evidence')
exec(compile(source,'<baseline-detector>','exec'),module.__dict__)
module.foreground_mask=lambda image:None
module.choose_grid=choose_namespace['choose_grid']
helpers=runpy.run_path('docs/qa/group-extent-audit/audit.py',run_name='audit_helpers')
out=Path('docs/qa/group-extent-audit/baseline');out.mkdir(exist_ok=True)
for name,path in helpers['SOURCES'].items():
    detector=module.MotifDetector();result=detector.detect_with_layout(cv2.imread(str(path)),module.DetectorSettings())
    ownership=helpers['ownership']([c.bounding_box_px for c in result.candidates],helpers['POINTS'][name])
    data={'reconstructed_policy':True,'result':asdict(result),'diagnostics':detector.last_diagnostics,'ownership':ownership}
    (out/f'{name}.json').write_text(json.dumps(data,indent=2))
    print(name,len(result.candidates),sum(len(o['owners'])==1 for o in ownership),flush=True)
