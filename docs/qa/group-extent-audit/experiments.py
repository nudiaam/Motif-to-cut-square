"""Counterfactual comparisons without changing application source."""
from pathlib import Path
import runpy,json
from dataclasses import asdict
from unittest.mock import patch
import cv2
import numpy as np
from app.imaging.detector import MotifDetector,DetectorSettings
import app.imaging.detector as detector_module
from app.imaging.bed_reference import locate_bright_fabric
from app.imaging.contrast_grid import infer_contrast_geometry
from app.imaging.analysis_frame import translate_grid
from dataclasses import replace

m=runpy.run_path('docs/qa/group-extent-audit/audit.py',run_name='helpers')
OUT=Path('docs/qa/group-extent-audit');records=[]
for name,path in m['SOURCES'].items():
    image=cv2.imread(str(path))
    for experiment in ('without_appearance_replacement','grayscale','shared_only'):
        d=MotifDetector();input_image=image
        if experiment=='grayscale':input_image=cv2.cvtColor(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),cv2.COLOR_GRAY2BGR)
        original=detector_module.infer_contrast_geometry
        context=(patch.object(d,'_coordinate_appearance',side_effect=lambda image,settings,current,*a,**kw:(current,False))
            if experiment=='without_appearance_replacement' else
            patch.object(detector_module,'infer_contrast_geometry',side_effect=lambda image,channel='dark':
                        original(image,channel=channel) if channel=='shared_background' else None)
            if experiment=='shared_only' else __import__('contextlib').nullcontext())
        with context:result=d.detect_with_layout(input_image,DetectorSettings())
        ownership=m['ownership']([c.bounding_box_px for c in result.candidates],m['POINTS'][name])
        data={'source':name,'experiment':experiment,'result':asdict(result),'ownership':ownership,'diagnostics':d.last_diagnostics}
        records.append(data);(OUT/'experiments.json').write_text(json.dumps(records,indent=2))
        print(name,experiment,len(result.candidates),'whole',sum(len(g['owners'])==1 for g in ownership),
              'grid',None if result.panel_grid is None else (result.panel_grid.columns,result.panel_grid.rows,result.panel_grid.source),flush=True)
    if name=='cocktails':
        # Prefer independently detected whole pattern regions instead of extracting
        # another set of local boxes from a competing automatic partition.
        choose=detector_module.choose_grid
        def pattern_first(image,proposals,candidates,**kw):
            preferred,rows=choose(image,proposals,candidates,**kw)
            if any(r['route']=='pattern' and r['eligible'] for r in rows):preferred='pattern'
            return preferred,rows
        d=MotifDetector()
        with patch.object(detector_module,'choose_grid',side_effect=pattern_first):
            result=d.detect_with_layout(image,DetectorSettings())
        o=m['ownership']([c.bounding_box_px for c in result.candidates],m['POINTS'][name])
        data={'source':name,'experiment':'whole_pattern_priority','result':asdict(result),'ownership':o,'diagnostics':d.last_diagnostics}
        records.append(data);(OUT/'experiments.json').write_text(json.dumps(records,indent=2))
        print(name,'whole_pattern_priority',len(result.candidates),'whole',sum(len(g['owners'])==1 for g in o),flush=True)
