"""Compare previous controls and the user's new ten-image batch before/after."""
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys

import cv2

from app.imaging.detector import MotifDetector, DetectorSettings

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/qa/accessory-groups'


def main():
    name='app.imaging._before_accessory_ownership'
    spec=importlib.util.spec_from_file_location(name,OUT/'detector.py')
    old=importlib.util.module_from_spec(spec);sys.modules[name]=old;spec.loader.exec_module(old)
    previous=json.loads((ROOT/'docs/qa/joint-coordinator/comparison.json').read_text())
    files=[ROOT/c['file'] for c in previous['cases']]
    files += [ROOT/'tests/fixtures/acceptance'/n for n in ('mixed_icons_6x4.png','dark_leaves_5x3.png')]
    files += sorted((ROOT/'tests/fixtures/acceptance/batch_20260923').glob('case_*.png'))
    files += [ROOT/'tests/fixtures/acceptance/animal_accessories_4x3.png']
    records=[]
    for path in files:
        image=cv2.imread(str(path))
        before=old.MotifDetector().detect_with_layout(image,old.DetectorSettings())
        detector=MotifDetector();after=detector.detect_with_layout(image,DetectorSettings())
        geometry=lambda r:sorted((c.bounding_box_px,c.center_px) for c in r.candidates)
        states=lambda r:sorted((c.bounding_box_px,c.review_reasons) for c in r.candidates)
        record=dict(file=str(path),previous_count=len(before.candidates),count=len(after.candidates),
                    same_boxes_and_centres=geometry(before)==geometry(after),
                    same_review_reasons=states(before)==states(after),
                    rechecks=[s for s in detector.last_diagnostics['detection_plans']
                              if s['stage']=='appearance_ownership_recheck'])
        records.append(record);print(record,flush=True)
        (OUT/'comparison.json').write_text(json.dumps(records,indent=2))
    failure=ROOT/'tests/fixtures/acceptance/animal_accessories_4x3.png'
    controls=[r for r in records if Path(r['file'])!=failure]
    assert len(controls)==29
    assert all(r['same_boxes_and_centres'] and r['same_review_reasons'] for r in controls)
    changed=next(r for r in records if Path(r['file'])==failure)
    assert changed['previous_count']==20 and changed['count']==12


if __name__=='__main__':main()
