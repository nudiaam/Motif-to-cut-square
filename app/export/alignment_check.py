"""Export bed-relative landmarks through the normal physical SVG exporter."""
from dataclasses import dataclass
from pathlib import Path
import csv
import math

from app.export.svg_exporter import SVGExporter
from app.geometry.coordinate_mapper import CoordinateMapper
from app.geometry.units import LengthUnit, from_inches
from app.models import Detection


@dataclass(frozen=True)
class AlignmentCheckResult:
    svg_path: Path
    measurements_path: Path
    instructions_path: Path


def export_alignment_check(path, bed_width_in, bed_height_in, unit=LengthUnit.INCHES):
    """Five known centres, independent of image fitting, motifs and cut size.

    The CSV records machine-bed coordinates in mm, with blank measured fields.
    Importing or measuring this pattern never changes a calibration implicitly.
    """
    if (not all(math.isfinite(v) and v > 0 for v in (bed_width_in, bed_height_in))):
        raise ValueError('Bed dimensions must be finite and positive')
    path=Path(path)
    csv_path=path.with_suffix('.measurements.csv')
    if csv_path.exists():
        raise ValueError('A measurement sheet already exists for this filename. '
                         'Choose a new filename to preserve recorded measurements.')
    side=min(2.,bed_width_in/8,bed_height_in/8)
    inset=min(1.,bed_width_in/12,bed_height_in/12)
    left=top=inset+side/2
    right=bed_width_in-inset-side/2;bottom=bed_height_in-inset-side/2
    targets=(('top_left',left,top),('top_right',right,top),
             ('bottom_left',left,bottom),('bottom_right',right,bottom),
             ('centre',bed_width_in/2,bed_height_in/2))
    mapper=CoordinateMapper(1000,1000,bed_width_in,bed_height_in)
    detections=[Detection.from_pixel_center(i,mapper.inches_to_pixel(x,y),mapper,
                cut_width_inches=side,cut_height_inches=side)
                for i,(_,x,y) in enumerate(targets,1)]
    SVGExporter().export(path,mapper,detections,unit)
    with csv_path.open('x',encoding='utf-8',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(('target','expected_centre_x_mm','expected_centre_y_mm',
                         'expected_side_mm','measured_centre_x_mm','measured_centre_y_mm',
                         'measured_width_mm','measured_height_mm'))
        for name,x,y in targets:
            writer.writerow((name,f'{x*25.4:.6f}',f'{y*25.4:.6f}',f'{side*25.4:.6f}',
                             '','','',''))
    instructions=path.with_suffix('.instructions.txt')
    width=from_inches(bed_width_in,unit);height=from_inches(bed_height_in,unit)
    instructions.write_text(
        'Lalikul - comprobacion de alineacion / alignment check\n\n'
        f'Pagina / Page: {width:g} x {height:g} {unit.value}\n'
        f'Cinco cuadrados / Five squares: {side*25.4:g} x {side*25.4:g} mm\n'
        'Origen / Origin: esquina superior izquierda / top left; X derecha / right, Y abajo / down.\n\n'
        '1. Importar el SVG mediante el mismo recorrido que un trabajo normal.\n'
        '   Import the SVG through the same path as a normal job.\n'
        '2. Comprobar pagina, escala 100%, sin ajustar a pagina ni centrar el dibujo.\n'
        '   Check page size, 100% actual size, no fit-to-page or artwork centring.\n'
        '3. Comprobar los cinco centros respecto al origen de la cama y el lado de cada cuadrado.\n'
        '   Check all five centres from the bed origin and each square side.\n'
        '4. Anotar las medidas reales en el CSV; sus coordenadas estan siempre en mm.\n'
        '   Record actual measurements in the CSV; its coordinates are always mm.\n'
        '5. Para comprobar la camara, usar marcas fisicas en las posiciones conocidas y comparar\n'
        '   su fotografia con el patron, sin mover ni escalar manualmente la foto para hacerlo encajar.\n'
        '   For the camera check, photograph physical marks at the known positions and compare\n'
        '   with the pattern without manually fitting the photograph.\n\n'
        'Desplazamiento constante: revisar origen/posicion. Error creciente: revisar escala.\n'
        'Error distinto por zona: revisar giro/distorsion y calibracion.\n'
        'Constant offset: inspect origin/placement. Increasing error: inspect scale.\n'
        'Different errors by location: inspect rotation/distortion and calibration.\n\n'
        'Este patron no certifica ni modifica la calibracion. La app no envia trabajos a la maquina.\n'
        'This pattern does not certify or change calibration. The app does not send machine jobs.\n',
        encoding='utf-8')
    return AlignmentCheckResult(path,csv_path,instructions)
