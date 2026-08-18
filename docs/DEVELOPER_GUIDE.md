# Guía de desarrollo de Lalikul Cut Prep

Esta guía complementa el `README.md`. El README está escrito primero para usuarios de Windows y funciona como portada de GitHub; este documento concentra la información técnica para evitar mezclar instalación cotidiana con desarrollo.

La separación sigue la recomendación de GitHub de usar el README para explicar qué hace un proyecto, por qué es útil, cómo empezar y dónde obtener ayuda, dejando la documentación extensa en archivos enlazados.

## Stack

- Python 3.10 o posterior.
- PySide6 para la interfaz de escritorio.
- OpenCV para detección clásica de motivos.
- NumPy para representación y conversión de imágenes.
- `unittest` para pruebas funcionales, geométricas y de interfaz.

Las versiones admitidas están definidas en `requirements.txt`.

## Entorno local

Desde PowerShell, en la raíz del proyecto:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

También puede utilizarse `setup.bat`, que crea o repara `.venv` y descarga las dependencias.

## Ejecutar la aplicación

Con consola visible:

```powershell
.\.venv\Scripts\python.exe -m app.main
```

`setup.bat` genera `Lalikul Cut Prep.lnk`, un acceso directo local que apunta a `Lalikul Cut Prep.vbs` y usa `app/assets/lalikul-cut-prep.ico`. El VBS valida el entorno en segundo plano y ejecuta `.venv\Scripts\pythonw.exe -m app.main` sin consola.

La aplicación establece el icono de Qt y un `AppUserModelID` explícito en Windows. Esto evita que la ventana y su botón de la barra de tareas hereden la identidad visual genérica de `pythonw.exe`.

`run_console.bat` debe conservarse como ruta de diagnóstico porque `pythonw.exe` no muestra excepciones en una terminal.

## Ejecutar las pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La suite cubre:

- conversiones píxel ↔ pulgadas, centímetros y milímetros;
- escalas horizontal y vertical;
- colocación proporcional de la imagen;
- tamaños de cama y perfiles de máquina personalizados;
- detector y agrupación de fragmentos;
- centrado del corte por límites completos del dibujo y conservación de esos
  límites al resolver solapes;
- cuadrados y rectángulos configurables;
- límites de cama y colisiones entre cortes;
- zoom, encaje y desplazamiento del canvas;
- exclusión de cortes inválidos en SVG;
- unidades SVG y round-trip verification;
- controles, ayudas y gestos principales de la interfaz.

## Estructura del proyecto

```text
app/
  config/       perfiles de máquina y persistencia
  demo/         imagen de prueba reproducible
  export/       SVG, JSON de diagnóstico y verificación
  geometry/     unidades, cama, escala y geometría de corte
  imaging/      detector OpenCV
  ui/           ventana, canvas, panel y ayuda contextual
  main.py       punto de entrada y hoja de estilos
tests/          pruebas unitarias y smoke tests de interfaz
docs/           manual de usuario y documentación técnica
setup.bat       creación o reparación de .venv
run.bat         delegación rápida al lanzador oculto
run_console.bat ejecución diagnóstica con terminal
Lalikul Cut Prep.vbs  ejecución normal sin terminal
app/assets/           logotipo PNG e icono ICO multirresolución
```

## Modelo geométrico

`CoordinateMapper` concentra la transformación entre:

1. píxeles de la imagen;
2. pulgadas canónicas internas;
3. unidades visibles o de exportación.

Las unidades internas permanecen en pulgadas para evitar deriva por conversiones sucesivas. La interfaz convierte a `in`, `cm` o `mm` al mostrar valores y el exportador convierte una única vez a la unidad SVG seleccionada.

La imagen tiene una colocación física propia dentro de la cama: X, Y, anchura y altura. La carga inicial usa `contain_image`, que conserva la proporción y centra la imagen. El movimiento mantiene tamaño y la escala desde esquinas mantiene la proporción.

El zoom y el desplazamiento pertenecen exclusivamente a la vista del canvas. Modifican el rectángulo dibujado de la cama, pero no `CoordinateMapper`, las coordenadas físicas, las detecciones ni el SVG. El zoom conserva bajo el cursor el mismo punto físico.

## Validez y colisiones

Cada `Detection` diferencia tres condiciones:

- `enabled`: inclusión manual solicitada;
- `valid_cut`: el rectángulo está dentro de la cama;
- `overlaps_cut`: el rectángulo toca o intersecta otro corte activo.

La propiedad `exportable` exige `enabled and valid_cut and not overlaps_cut`.

`recalculate_cut_overlaps` considera conflicto tanto una intersección con área como el contacto exacto de bordes. Las detecciones desactivadas no participan. La interfaz recalcula después de mover, redimensionar, activar, desactivar, detectar o cambiar la colocación de la imagen. El exportador y el verificador vuelven a calcular como defensa adicional.

`center_cuts_on_visual_anchors` centra primero cada corte usando los límites
completos del dibujo. Después, `resolve_cut_overlaps` separa los conflictos dentro
del intervalo que todavía contiene esos límites. Este orden evita el ciclo
centrar → recrear solape → volver a separar.

El flujo vive en una barra horizontal `WORKFLOW` sobre el canvas: preparar la
imagen, detectar y validar, revisar, comprobar salida y exportar. `SidePanel`
es contextual y muestra únicamente los controles de la fase activa. Las acciones
condicionales de borrar, resolver solapes y centrar pertenecen a revisión, no al
indicador principal. No se duplica `Detect` en el toolbar global.

La primera detección fuerza `layout_mode="free"` y permanece en la fase `detect`.
Tener resultados y haberlos aceptado son estados diferentes:
`_detection_review_complete` solo cambia mediante la confirmación explícita del
usuario. Hasta entonces, revisión y preflight permanecen bloqueados.

`PANEL GRID` es una mejora opcional posterior a esa primera detección. Mostrar y
editar son estados separados. Filas y columnas actualizan las guías de inmediato,
pero conservan el resultado visible para poder compararlo. Cada cambio invalida
`_grid_review_complete`; al confirmar, se ejecuta una nueva detección con las
divisiones elegidas y se invalida de nuevo `_detection_review_complete`. La
sustitución queda en el historial de deshacer. Las acciones de espaciado uniforme
solo se muestran mientras las guías están editables.

`MainWindow.selected_ids` mantiene la selección múltiple compartida por canvas y
lista. `Shift+click` alterna miembros; el id primario se conserva únicamente para
el inspector de detalle. Un clic en espacio vacío del canvas conserva la selección.
`BedCanvas` pinta el propio rectángulo de corte con borde, centro y relleno cian
cuando está seleccionado, sin añadir geometría visual por fuera. Centrado y
resolución de solapes limpian la selección antes de modificar geometría.

El historial guarda hasta 50 snapshots de detecciones, mapper, tamaño de corte,
selección y estado del flujo. `Ctrl+Z` restaura operaciones de geometría y revisión.
Los arrastres emiten `edit_started` una sola vez, evitando un snapshot por cada
evento de movimiento.

`Preview Cuts` es exclusivamente visual. `BedCanvas` construye una máscara con
huecos para las detecciones `exportable` y oscurece el resto de la cama; no cambia
coordenadas, estados ni contenido SVG.

## Detector

El detector sigue siendo clásico y reproducible:

- propone primero una cuadrícula a partir de costuras y cambios amplios de tela;
  los centros candidatos solo validan la propuesta y nunca la crean por sí solos;
- descarta la ruta de paneles en fondos uniformes aunque los dibujos estén
  colocados regularmente;
- en una cuadrícula confirmada analiza cada celda con un fondo local independiente,
  excluye un margen de costura y devuelve como máximo un candidato por panel;
- estima un fondo local que sigue los cambios de iluminación;
- segmenta diferencias de color con una máscara permisiva;
- aplica limpieza morfológica;
- filtra por área;
- agrupa componentes cercanos usando `Merge distance`;
- separa primero componentes sustanciales y asigna después los fragmentos al
  núcleo más cercano, sin permitir que motas del estampado conecten dos dibujos;
- reincorpora un único detalle pequeño algo más distante cuando existe un solo
  padre claramente mayor, por ejemplo una cereza o una antena;
- cuando no hay evidencia visual suficiente de paneles conserva la consolidación
  compatible anterior o la ruta libre;
- calcula un centro robusto con los píxeles de mayor confianza y recorta el 10 %
  de los extremos para que motas o fragmentos débiles no desplacen el marcador;
- devuelve un único centro robusto por grupo.

El centro robusto del detector y el centro del corte tienen responsabilidades
distintas. `Detection.artwork_center_px()` usa el punto medio del bounding box
completo para el paso de centrado, incluyendo detalles finos. El resolvedor de
solapes limita después cada eje al intervalo en el que tanto el corte como ese
bounding box siguen contenidos. Si el dibujo supera el tamaño de corte, el
intervalo se colapsa a su punto medio para que el recorte inevitable sea simétrico
y explícito.

`Detection.artwork_fits_cut()` separa la factibilidad física del estado actual de
alineación. El resolvedor no descarta un corte solo porque todavía no contiene su
dibujo. El flujo primero establece una disposición sin solapes y después centra.
El centrado prueba la solución conjunta contra los vecinos; si la relajación por
pares entra en ciclo en una cuadrícula densa, restaura la última disposición válida
y avanza monótonamente hacia cada centro sin permitir una nueva colisión.

La revisión de interfaz sigue un flujo finito: `1` elimina la detección
seleccionada, `2` resuelve solapes y `3` centra. El estado de centrado impide volver
a ejecutar el paso 3 después del paso final, salvo que cambie la geometría.

Los valores predeterminados se encuentran en `SidePanel` y `DetectorSettings`.
`PanelGrid` conserva las líneas en píxeles de imagen. El canvas permite arrastrar
límites e interiores; `distribute("x")` y `distribute("y")` reparten las líneas
internas entre los límites exteriores. Cualquier cambio manual vuelve a ejecutar
la detección por celdas y forma parte del historial de deshacer.
`test_patterned_quilt_acceptance.py` fija el contrato de una detección por panel
frente a fondos estampados, piezas separadas, oscuridad, gradiente de luz,
desenfoque, ruido y compresión JPEG.

## Exportación

`SVGExporter` crea un SVG con el tamaño físico completo de la cama y un `viewBox` en la misma unidad. Solo escribe elementos `<rect>` exportables.

`verify_export_geometry` convierte la geometría a la unidad SVG, la reconstruye a pulgadas y finalmente a píxeles. Este recorrido permite detectar errores de escala, offset o conversión.

`export_debug_json` registra máquina, unidades, colocación de imagen, escalas y estado de cada detección.

## Configuración persistente

Los perfiles personalizados se guardan en:

```text
%APPDATA%\Lalikul\CutPrep\machines.json
```

No se guardan imágenes ni resultados de detección automáticamente.

## Criterios antes de publicar una release

1. Ejecutar toda la suite en Windows con `QT_QPA_PLATFORM=offscreen` para las pruebas automatizadas.
2. Probar manualmente Paste Image, Open Image, bloqueo, movimiento, escala, zoom y exportación.
3. Verificar un SVG en el software receptor con una geometría física conocida.
4. Confirmar origen, escala y cama en una Epilog Fusion Maker 36 real.
5. Empaquetar la app para que el usuario final no necesite instalar Python.
6. Firmar el instalador y el ejecutable.
7. Añadir `LICENSE`, versión, changelog y artefactos de release antes de publicar el repositorio como producto distribuible.

## Referencias de documentación

- [GitHub Docs: About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
- [Microsoft PowerToys](https://github.com/microsoft/PowerToys), como ejemplo de README que presenta primero utilidad e instalación y enlaza después documentación más extensa.
- [Adobe Illustrator: atajos de visualización](https://helpx.adobe.com/illustrator/using/default-keyboard-shortcuts.html)
- [Epilog: Copy Background Image](https://support.epiloglaser.com/laser-machine/fusion-galvo/usage-and-operation/how-and-when-to-use-the-copy-background-image-feature/)
