"""Audit ten photographs through the real Qt workflow and serialized SVG.

Run with the private originals installed in docs/qa/square-contract-20261115.
Manual truth and witnesses remain separate from detection inputs. A correct
count, an export round trip and a semantic artwork verdict are distinct checks.
"""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,json,hashlib,html,copy,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
from app.ui.main_window import MainWindow
from app.main import APP_STYLESHEET
from app.export.svg_exporter import SVG_NAMESPACE
from app.geometry.units import LengthUnit
from tests.square_contract_truth import CASES

ROOT=Path(__file__).resolve().parents[1]/'docs/qa/square-contract-20261115'

def truth_centres(case):
 cols,rows=case['shape']
 if 'xs' in case:
  return {(c,r):((case['xs'][c]+case['xs'][c+1])/2,(case['ys'][r]+case['ys'][r+1])/2)
          for r in range(rows) for c in range(cols)}
 T=cv2.getPerspectiveTransform(np.float32([[0,0],[cols,0],[cols,rows],[0,rows]]),np.float32(case['quad']))
 return {(c,r):tuple(cv2.perspectiveTransform(np.float64([[[c+.5,r+.5]]]),T).reshape(2))
         for r in range(rows) for c in range(cols)}

def truth_polygon(case,c,r):
 if 'xs' in case:
  x0,x1=case['xs'][c:c+2];y0,y1=case['ys'][r:r+2]
  return np.float32([(x0,y0),(x1,y0),(x1,y1),(x0,y1)])
 cols,rows=case['shape']
 T=cv2.getPerspectiveTransform(np.float32([[0,0],[cols,0],[cols,rows],[0,rows]]),np.float32(case['quad']))
 return cv2.perspectiveTransform(np.float64([[[c,r]],[[c+1,r]],[[c+1,r+1]],[[c,r+1]]]),T).reshape(-1,2).astype(np.float32)

def largest_square(window,include_uncertainty=True):
 # Independent corner testing; this does not use the production placement solver.
 widths=[]
 for d in window.detections:
  poly=np.asarray(d.cut_region_px,np.float32);cx,cy=d.center_px;lo,hi=0.,max(window.image_bgr.shape[:2])
  # The main test keeps away from the border's measured error band. A second,
  # tighter run exercises that band explicitly without calling it a crossing.
  margin=2.+(d.cut_region_uncertainty_px if include_uncertainty else 0.)
  for _ in range(35):
   half=(lo+hi)/2
   distances=[cv2.pointPolygonTest(poly,(cx+sx*half,cy+sy*half),True) for sx,sy in ((-1,-1),(1,-1),(1,1),(-1,1))]
   if min(distances)>=margin:lo=half
   else:hi=half
  widths.append(2*lo/window.mapper.px_per_inch_x)
 return np.floor(min(widths)*100)/100

def serialize(window):
 return ET.tostring(window.svg_exporter.build_tree(window.mapper,window.detections,LengthUnit.INCHES).getroot())

def main():
 cv2.setNumThreads(2)
 app=QApplication([])
 for font in ('segoeui.ttf','segoeuib.ttf'):QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+font)
 app.setFont(QFont('Segoe UI',9));app.setStyle('Fusion');app.setStyleSheet(APP_STYLESHEET)
 reports=[]
 baseline_path=ROOT/'before-confidence/evaluation.json'
 baseline={r['case']:r for r in json.loads(baseline_path.read_text())} if baseline_path.exists() else {}
 for name,case in CASES.items():
  source=ROOT/'originals'/(name+'.png');image=cv2.imread(str(source))
  if image is None:raise FileNotFoundError(source)
  w=MainWindow();w.resize(1600,950);w.show();app.processEvents();w._load_image(image,name);w.detect_motifs();app.processEvents()
  initial_positions={d.id:d.center_px for d in w.detections}
  expected=int(np.prod(case['shape']));assert len(w.detections)==expected,(name,len(w.detections),expected)
  w.grab().save(str(ROOT/(name+'-default.png')))
  w.svg_exporter.export(ROOT/(name+'-default.svg'),w.mapper,w.detections)
  defaults={'cut_inches':5.,'count':len(w.detections),'red':sum(bool(d.cut_warning_reason(w.mapper)) for d in w.detections)}
  comparison=None
  if name in baseline:
   previous=baseline[name];w.panel.cut_width_spin.setValue(previous['adapted_square_inches']);app.processEvents()
   assert previous['sha256']==hashlib.sha256(source.read_bytes()).hexdigest(),(name,'comparison source changed')
   comparison_path=ROOT/(name+'-comparison.svg')
   w.svg_exporter.export(comparison_path,w.mapper,w.detections)
   unchanged=comparison_path.read_bytes()==(ROOT/'before-confidence'/(name+'-adapted.svg')).read_bytes()
   old_rects=ET.parse(ROOT/'before-confidence'/(name+'-adapted.svg')).getroot().findall(f'{{{SVG_NAMESPACE}}}rect')
   new_rects=ET.parse(comparison_path).getroot().findall(f'{{{SVG_NAMESPACE}}}rect')
   assert len(old_rects)==len(new_rects)==expected
   # Candidate identifiers/order can change when a measured extent changes.
   # Compare physical owners, not unrelated rectangles with the same list index.
   old_by_cell={tuple(check['cell']):rect for check,rect in zip(previous['checks'],old_rects)}
   shifts=[]
   for d,new in zip(w.detections,new_rects):
    old=old_by_cell[tuple(d.layout_cell)]
    assert old.attrib['width']==new.attrib['width'] and old.attrib['height']==new.attrib['height']
    dx=(float(new.attrib['x'])-float(old.attrib['x']))*w.mapper.px_per_inch_x
    dy=(float(new.attrib['y'])-float(old.attrib['y']))*w.mapper.px_per_inch_y
    shifts.append(float(np.hypot(dx,dy)))
   # Strip diagnostic evidence on copies: classification itself cannot move,
   # resize or omit a checked rectangle. Measured seam-centre corrections can.
   diagnostic_before=serialize(w);legacy=copy.deepcopy(w.detections)
   for d in legacy:
    d.artwork_extent_uncertain=False;d.artwork_support_boxes_px=();d.review_reasons=()
    d.recalculate_for_mapper(w.mapper)
   diagnostic_after=ET.tostring(w.svg_exporter.build_tree(w.mapper,legacy,LengthUnit.INCHES).getroot())
   assert diagnostic_before==diagnostic_after,(name,'diagnostic evidence changed SVG geometry')
   comparison={'size_inches':previous['adapted_square_inches'],'before_red':previous['red'],
    'after_red':sum(bool(d.cut_warning_reason(w.mapper)) for d in w.detections),
    'review_only':sum(not d.cut_warning_reason(w.mapper) and bool(d.review_reasons_for(w.mapper)) for d in w.detections),
    'svg_bytes_unchanged':unchanged,'maximum_seam_centre_correction_px':max(shifts),
    'diagnostic_classification_svg_unchanged':True}
  stress_size=largest_square(w,include_uncertainty=False)
  w.panel.cut_width_spin.setValue(stress_size);app.processEvents()
  stress={'cut_inches':float(stress_size),
   'red':sum(bool(d.cut_warning_reason(w.mapper)) for d in w.detections),
   'review_only':sum(not d.cut_warning_reason(w.mapper) and bool(d.review_reasons_for(w.mapper)) for d in w.detections),
   'section_crossings':sum(bool(d.panel_boundary_reason(w.mapper)) for d in w.detections)}
  assert stress['section_crossings']==0
  assert {d.id:d.center_px for d in w.detections}==initial_positions
  w.grab().save(str(ROOT/(name+'-edge-stress.png')))
  w.svg_exporter.export(ROOT/(name+'-edge-stress.svg'),w.mapper,w.detections)
  size=largest_square(w);w.panel.cut_width_spin.setValue(size);app.processEvents()
  assert abs(w.cut_width_inches-size)<.0001
  assert {d.id:d.center_px for d in w.detections}==initial_positions,(name,'resizing moved centres')
  w.grab().save(str(ROOT/(name+'-adapted.png')))
  result=w.svg_exporter.export(ROOT/(name+'-adapted.svg'),w.mapper,w.detections)
  tree=ET.parse(ROOT/(name+'-adapted.svg')).getroot();rects=tree.findall(f'{{{SVG_NAMESPACE}}}rect')
  assert tree.attrib['width']=='36in' and tree.attrib['height']=='24in'
  assert result.rectangle_count==len(rects)==expected
  truth=truth_centres(case);checks=[];max_error=0.
  cut_geometry=[]
  for d,rect in zip(w.detections,rects):
   values=tuple(float(rect.attrib[k]) for k in ('x','y','width','height'))
   px=w.mapper.inches_rect_to_pixel(values);cut_geometry.append(px)
   expected_px=w.mapper.inches_rect_to_pixel(d.square_inches.as_tuple())
   error=max(abs(a-b) for a,b in zip(px,expected_px));max_error=max(max_error,error)
   assert error<.001,(name,'serialized SVG moved',error)
   x,y,ww,hh=px;poly=np.asarray(d.cut_region_px,np.float32)
   distances=[float(cv2.pointPolygonTest(poly,point,True)) for point in ((x,y),(x+ww,y),(x+ww,y+hh),(x,y+hh))]
   assert min(distances)>=-.001,(name,d.id,'adapted cut crosses its cell',distances)
   assert d.square_inches.is_valid(w.mapper.bed_width_in,w.mapper.bed_height_in)
   automatic=w.logical_layout.position(*d.layout_cell)
   assert max(abs(a-b) for a,b in zip(automatic,d.center_px))<1e-7
   manual=truth.get(tuple(d.layout_cell));measurement=None if manual is None else float(np.linalg.norm(np.asarray(d.center_px)-manual))
   measured_poly=truth_polygon(case,*d.layout_cell)
   measured_distances=[float(cv2.pointPolygonTest(measured_poly,point,True)) for point in ((x,y),(x+ww,y),(x+ww,y+hh),(x,y+hh))]
   # An approximate reference disagreement is not proof of a calibrated edge,
   # but it must never receive an unqualified READY verdict.
   if min(measured_distances)<-6.:
    assert d.cut_warning_reason(w.mapper) or d.review_reasons_for(w.mapper),(name,d.id,'unqualified reference crossing')
   checks.append({'id':d.id,'cell':d.layout_cell,'center_px':d.center_px,'manual_center_px':manual,
    'manual_center_error_px':measurement,'polygon':d.cut_region_px,'bbox':d.bounding_box_px,
    'cut_px':px,'corner_margins_px':distances,'manual_corner_margins_px':measured_distances,'warning':d.cut_warning_reason(w.mapper),
    'reviews':d.review_reasons_for(w.mapper),'contains_detected_artwork':d.contains_artwork(w.mapper),
    'artwork_extent_uncertain':d.artwork_extent_uncertain,
    'artwork_support_boxes_px':d.artwork_support_boxes_px,
    'contains_supported_artwork':d.contains_supported_artwork(w.mapper)})
  # Display operations must not change any serialized coordinate.
  before=serialize(w);w.canvas.set_view_scale(2.);w.canvas.center_view_on_bed_inches(18.,12.);app.processEvents()
  assert serialize(w)==before
  w.panel.working_unit_combo.setCurrentIndex(w.panel.working_unit_combo.findData('mm'));app.processEvents()
  assert serialize(w)==before
  w.change_cut_size(size*.8,size*.8);w.undo();app.processEvents()
  assert serialize(w)==before,(name,'undo changed export')
  d=w.detections[0];d.enabled=False
  assert len(ET.fromstring(serialize(w)).findall(f'{{{SVG_NAMESPACE}}}rect'))==expected-1
  d.enabled=True
  # Sampled details checked against both detected extents and actual SVG cuts.
  witnesses=[]
  for group in case.get('witnesses',[]):
   owners=[d.id for d in w.detections if all(x<=px<x+bw and y<=py<y+bh
     for px,py in group for x,y,bw,bh in [d.bounding_box_px])]
   cut_owners=[i for i,(x,y,bw,bh) in enumerate(cut_geometry) if all(x<=px<x+bw and y<=py<y+bh for px,py in group)]
   witnesses.append({'points':group,'detected_owners':owners,'svg_cut_owners':cut_owners})
  cv2.imwrite(str(ROOT/(name+'-thumb.jpg')),cv2.resize(image,(768,512)))
  report={'case':name,'expected':expected,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
   'default':defaults,'edge_stress':stress,'same_size_comparison':comparison,'adapted_square_inches':float(size),'count':len(w.detections),
   'red':sum(bool(d.cut_warning_reason(w.mapper)) for d in w.detections),
   'ready':sum(not d.cut_warning_reason(w.mapper) and not d.review_reasons_for(w.mapper) and not d.overlaps_cut for d in w.detections),
   'review_only':sum(not d.cut_warning_reason(w.mapper) and bool(d.review_reasons_for(w.mapper)) for d in w.detections),
   'svg_error_px':max_error,'manual_max_error_px':max(c['manual_center_error_px'] for c in checks if c['manual_center_error_px'] is not None),
   'manual_measurement_uncertainty_px':6.,
   'reference_crossings_over_tolerance':sum(min(c['manual_corner_margins_px']) < -6. for c in checks),
   'reference_crossings_presented_as_ready':0,'checks':checks,'witnesses':witnesses,
   'geometry_export_checks_passed':True}
  reports.append(report);(ROOT/'evaluation.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
  (ROOT/(name+'-diagnostics.json')).write_text(json.dumps(w.detection_diagnostics,indent=2,default=str),encoding='utf-8')
  print(name,'count',report['count'],'size',size,'red',report['red'],'ready',report['ready'],'manual_error',round(report['manual_max_error_px'],2),flush=True)
  w.close()
 export_controls()
 build_report(reports)

def build_report(reports):
 sections=[];rows=[];comparisons=[]
 labels={'beige':'Animales beige inclinados','shadow':'Animales bajo sombra diagonal',
 'faint':'Animales de contraste muy bajo','accessories':'Animales y accesorios separados',
 'holdout_accessories_4x3':'Otra tela con accesorios','holdout_pale_5x4':'Animales claros con sombra',
 'holdout_birds_7x3':'Pájaros, ramas y flores','partial':'Fotografía con fila inferior recortada',
 'square_animals_6x4':'Nueva: animales en fondos distintos',
 'square_offcentre_5x3':'Nueva: animales descentrados y accesorios'}
 evidence=ROOT/'test-evidence/summary.json'
 suite=json.loads(evidence.read_text()) if evidence.exists() else None
 suite_text=('Suite completa: '+str(suite['tests'])+' pruebas; '+str(len(suite['failures']))+' fallos; '+str(len(suite['errors']))+' errores; '+str(len(suite['skipped']))+' omitidas.') if suite else 'Suite completa: verificación final en curso.'
 for r in reports:
  name=r['case'];rows.append(f'<tr><td><a href="#{name}">{labels[name]}</a></td><td>{r["count"]}/{r["expected"]}</td><td>{r["adapted_square_inches"]:.2f}″</td><td>{r["ready"]}</td><td>{r["review_only"]}</td><td>{r["red"]}</td><td>{r["manual_max_error_px"]:.1f} px</td></tr>')
  comparison=r.get('same_size_comparison')
  if comparison:
   comparisons.append(f'<tr><td>{labels[name]}</td><td>{comparison["size_inches"]:.2f}″</td><td>{comparison["before_red"]}</td><td>{comparison["after_red"]}</td><td>{comparison["review_only"]}</td><td>{comparison["maximum_seam_centre_correction_px"]:.2f} px</td><td><a href="before-confidence/{name}-adapted.svg">Antes</a> · <a href="{name}-comparison.svg">Actual</a></td></tr>')
  stress=r.get('edge_stress',{})
  stress_text=(f'<p>Prueba junto al borde: {stress["cut_inches"]:.2f}″; {stress["section_crossings"]} cruces de sección; {stress["red"]} rojos y {stress["review_only"]} revisiones. <a href="{name}-edge-stress.png">Captura</a> · <a href="{name}-edge-stress.svg">SVG</a></p>') if stress else ''
  sections.append(f'<section id="{name}"><h2>{name}</h2><p>{r["count"]} casillas; {r["ready"]} sin avisos; {r["review_only"]} en revisión; {r["red"]} rojos. Cuadrado de prueba: {r["adapted_square_inches"]:.2f}″.</p><div class="pair"><a href="originals/{name}.png"><img src="{name}-thumb.jpg" alt="Fotografía original"></a><a href="{name}-adapted.png"><img src="{name}-adapted.png" alt="Captura real de la aplicación"></a></div><p><a href="{name}-default.png">App a 5″</a> · <a href="{name}-default.svg">SVG a 5″</a> · <a href="{name}-adapted.svg">SVG con tamaño adaptado</a> · <a href="{name}-diagnostics.json">Diagnóstico</a></p>{stress_text}</section>')
 page='''<!doctype html><html lang="es"><meta charset="utf-8"><title>Casillas, dibujos y exportación — diez fotografías</title><style>body{font:16px system-ui;background:#14191f;color:#e1e8ef;max-width:1400px;margin:40px auto;padding:0 20px}a{color:#65ddd0}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:10px;border-bottom:1px solid #39434c}.pair{display:grid;grid-template-columns:1fr 1.5fr;gap:12px}img{width:100%}section{margin:50px 0}.notice{border-left:4px solid #ffb75c;padding:12px;background:#28252a}p{line-height:1.55}</style><h1>Diez fotografías: casillas, dibujos y SVG</h1>
<p>Ocho fotografías reutilizadas y dos nuevas generadas con aspecto fotográfico. Las medidas descritas en un prompt no se consideran calibración física. La prueba conserva cuadrados y adapta su tamaño global al espacio de las casillas, sin mover sus centros.</p>
<p class="notice">Rojo significa un conflicto confirmado: cruce más allá del error de medida de la guía, fuente incompleta o recorte de un contorno resuelto. Morado significa revisión, incluido posible recorte de contorno incierto o proximidad a una guía dudosa. Coincidir en algunos píxeles no confirma por sí solo toda la silueta. El recuento y la fidelidad del SVG tampoco certifican el reconocimiento completo del dibujo.</p>
<p>El tamaño adaptado se aproxima al mayor cuadrado que cabe en todas las secciones medidas, dejando su banda de incertidumbre y 2 píxeles adicionales. Una segunda prueba junto al borde deja solo 2 píxeles: comprueba que la banda de incertidumbre se muestre como revisión y no como cruce demostrado. Algunas composiciones ocupan secciones más anchas que altas en la fotografía: el mayor cuadrado que cabe aún puede recortar sus detalles. No se altera la calibración para volverlas verdes.</p>
<p>Las referencias manuales son aproximaciones de los bordes, a veces interpoladas entre cuatro esquinas, con una incertidumbre nominal de ±6 píxeles. Hay discrepancias superiores a esa cifra, publicadas en la tabla. Por ello no equivalen a una validación precisa de todos los centros físicos. Las pruebas independientes con divisiones conocidas y con límites anotados impiden certificar como listo un cruce sin advertencia.</p>
<p>Comprobado por separado: centro automático invariable al cambiar tamaño; cuatro esquinas del corte adaptado dentro de su casilla; coordenadas reales del SVG; página de 36 × 24″; ausencia de rectángulos fuera de cama; zoom, unidades y deshacer sin desplazamientos; exclusión manual omitida. La prueba automatizada adicional de casilla de 4″ y corte de 5″ verifica el aviso exportable.</p>
<table><thead><tr><th>Imagen</th><th>Casillas</th><th>Corte adaptado</th><th>Sin avisos</th><th>Revisión</th><th>Rojos</th><th>Desvío máximo frente a referencia aproximada</th></tr></thead><tbody>'''+''.join(rows)+'</tbody></table>'
 if comparisons:
  page+='<h2>Antes y después al mismo tamaño</h2><p>Comparación con la revisión anterior del proyecto. La nueva medición corrige ligeramente algunos centros de transición y puede cambiar el orden de identificadores. Se comparan las mismas casillas físicas. Por separado, quitar solo la clasificación diagnóstica de copias de los cortes deja el SVG idéntico en las diez fotografías: el color del aviso no mueve ni elimina rectángulos.</p><table><thead><tr><th>Imagen</th><th>Tamaño fijo</th><th>Rojos antes</th><th>Rojos ahora</th><th>Revisión ahora</th><th>Corrección máxima de centro</th><th>SVG</th></tr></thead><tbody>'+''.join(comparisons)+'</tbody></table>'
 rules=Path(__file__).resolve().parents[1]/'docs/CUTTING_RULES.md'
 rules_link=os.path.relpath(rules,ROOT).replace('\\','/')
 page+=''.join(sections)+'<p><a href="evaluation.json">Resultados completos y puntos de control</a> · <a href="'+rules_link+'">Reglas acordadas</a></p></html>'
 for name,label in labels.items():page=page.replace('<h2>'+name+'</h2>','<h2>'+label+'</h2>')
 page=page.replace('<table><thead>', '<p>'+suite_text+' <a href="test-evidence/summary.json">Resultado de la suite</a> · <a href="witnesses.json">Variaciones y puntos de dibujo</a> · <a href="oversize-checked.svg">Ejemplo de aviso exportado</a> · <a href="export-controls.json">Comprobación del ejemplo</a> · <a href="navigator-check.png">Navegador ampliado</a></p><table><thead>',1)
 (ROOT/'index.html').write_text(page,encoding='utf-8')

def export_controls():
 from app.models import Detection
 from app.geometry.coordinate_mapper import CoordinateMapper
 from app.export.svg_exporter import SVGExporter
 mapper=CoordinateMapper(1800,1200)
 d=Detection.from_pixel_center(1,(450,350),mapper,(430,330,40,40))
 d.cut_region_px=((350.,250.),(550.,250.),(550.,450.),(350.,450.))
 d.recalculate_for_mapper(mapper)
 assert d.cut_warning_reason(mapper) and d.enabled
 exporter=SVGExporter();path=ROOT/'oversize-checked.svg'
 exporter.export(path,mapper,[d]);rect=ET.parse(path).getroot().find(f'{{{SVG_NAMESPACE}}}rect')
 values=tuple(float(rect.attrib[k]) for k in ('x','y','width','height'))
 assert values==(6.5,4.5,5.,5.)
 d.enabled=False
 result=exporter.export(ROOT/'oversize-unchecked.svg',mapper,[d]);assert result.rectangle_count==0
 outside=Detection.from_pixel_center(2,(30,30),mapper)
 result=exporter.export(ROOT/'outside-bed.svg',mapper,[outside]);assert result.rectangle_count==0
 (ROOT/'export-controls.json').write_text(json.dumps({'cell_inches':[7,5,4,4],
  'checked_warning_svg_rect_inches':values,'checked_rectangles':1,'unchecked_rectangles':0,
  'outside_bed_rectangles':0,'page_inches':[36,24]},indent=2))

if __name__=='__main__':main()
