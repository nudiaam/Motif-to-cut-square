"""Controlled ablation of the 22 September change; source files stay untouched."""
from contextlib import ExitStack
import argparse
from dataclasses import asdict
import hashlib
import inspect
import json
from pathlib import Path
import textwrap
from unittest.mock import patch

import cv2

import app.imaging.detector as dm
import app.imaging.detection_plan as dp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/qa/selection-audit'


def previous_layout():
    source=textwrap.dedent(inspect.getsource(dm.MotifDetector._detect_layout))
    start=source.index('            eligible_routes =')
    end=source.index("            if preferred == 'observations':",start)
    source=source[:start]+source[end:]
    source=source.replace("    if settings.adaptive_planning and layout_mode == 'auto' and preferred is None:\n        return DetectionResult(tuple(primary))\n",'')
    namespace=dict(vars(dm));exec(source,namespace)
    return namespace['_detect_layout']


def previous_selector():
    source=inspect.getsource(dp.choose_grid)
    start=source.index("        if (measures['unique_assignment_fraction']")
    end=source.index('    independent =',start)
    source=source[:start]+source[end:]
    namespace=dict(vars(dp));exec(source,namespace)
    return namespace['choose_grid']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--image', help='Run one preserved fixture by filename')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT/'app').rglob('*.py')}
    rows=[]
    for path in sorted((ROOT/'tests/fixtures/acceptance').glob('*.png')):
        if args.image and path.name != args.image:
            continue
        image=cv2.imread(str(path))
        for variant in ('current','without_new_contrast','before_shadow_change'):
            with ExitStack() as context:
                if variant!='current':
                    context.enter_context(patch.object(dm,'infer_contrast_geometry',return_value=None))
                if variant=='before_shadow_change':
                    context.enter_context(patch.object(dm.MotifDetector,'_detect_layout',previous_layout()))
                    context.enter_context(patch.object(dm,'choose_grid',previous_selector()))
                detector=dm.MotifDetector()
                result=detector.detect_with_layout(image,dm.DetectorSettings())
            row={'image':path.name,'variant':variant,'count':len(result.candidates),
                 'grid':asdict(result.panel_grid) if result.panel_grid else None,
                 'candidates':[asdict(c) for c in result.candidates],
                 'diagnostics':detector.last_diagnostics}
            rows.append(row)
            canvas=image.copy()
            for c in result.candidates:
                x,y,w,h=c.bounding_box_px;cv2.rectangle(canvas,(x,y),(x+w,y+h),(0,0,255),2)
            cv2.imwrite(str(OUT/(path.stem+'-'+variant+'.png')),canvas)
            print(path.name,variant,len(result.candidates),
                  (result.panel_grid.columns,result.panel_grid.rows,result.panel_grid.source) if result.panel_grid else None,
                  flush=True)
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    output=(Path(args.image).stem+'-ab-comparison.json') if args.image else 'ab-comparison.json'
    (OUT/output).write_text(json.dumps({'source_sha256':hashes,'cases':rows},indent=2)+'\n')


if __name__=='__main__':main()
