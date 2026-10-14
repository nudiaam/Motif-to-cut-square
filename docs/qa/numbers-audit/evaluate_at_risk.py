"""Before/after comparison restricted to the user-selected at-risk collections."""
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
import json,time
import cv2
from app.imaging.detector import MotifDetector,DetectorSettings

import argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('docs/qa/holdout-20261014/verified'))
ROOT=Path('tests/fixtures');OUT=parser.parse_args().output;OUT.mkdir(exist_ok=True)
FILES=['customer_20261012/numbers_compact_5x4.png','customer_20261012/numbers_objects_5x4.png',
 'customer_20261012/alphabet_detached_6x4.png','generated/customer_20261012/alphabet_6x4.png',
 'customer_20261012/cocktails_groups.png','customer_20261012/quotes_groups.png',
 'customer_20261012/animals_accessories_4x3.png','customer_20261012/animals_accessories_columns_4x3.png',
 'acceptance/animal_accessories_4x3.png','floral_patchwork_recovered.png','generated/folk_floral_6x4.png',
 'transport_camera.png','transport_irregular_shadows.png','transport_dashed_shared.png',
 'vehicles_panels.png','acceptance/mixed_icons_6x4.png']
records=[]
for name in FILES:
    image=cv2.imread(str(ROOT/name));before=MotifDetector()
    with patch.object(before,'_compare_whole_layout',side_effect=lambda image,settings,current:(current,False)):
        old=before.detect_with_layout(image,DetectorSettings())
    after=MotifDetector();start=time.perf_counter();new=after.detect_with_layout(image,DetectorSettings())
    record={'file':name,'before_count':len(old.candidates),'after_count':len(new.candidates),
        'result_equal':asdict(old)==asdict(new),'seconds':time.perf_counter()-start,
        'before':asdict(old),'after':asdict(new),'diagnostics':after.last_diagnostics}
    records.append(record);(OUT/'at-risk-comparison.json').write_text(json.dumps(records,indent=2))
    print(name,record['before_count'],record['after_count'],'equal',record['result_equal'],flush=True)
