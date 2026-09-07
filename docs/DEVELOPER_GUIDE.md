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

La primera detección usa el modo configurado (`auto` por defecto) y permanece en
la fase `detect`. Un grid fiable se aplica automáticamente al colocar los cortes.
Tener resultados y haberlos aceptado son estados diferentes:
`_detection_review_complete` solo cambia mediante la confirmación explícita del
usuario. Hasta entonces, revisión y preflight permanecen bloqueados.

`PANEL GRID` permite revisar o corregir manualmente el resultado automático. Mostrar y
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

## Disposición lógica después de detectar

`app/imaging/logical_layout.py` analiza los bounding boxes del detector y también
asigna ilustraciones a una geometría visual independiente cuando está disponible.
El detector individual se conserva: la búsqueda global se complementa con la
misma detección local dentro de cada celda de un panel fiable.
El flujo sigue siendo preparar → detectar y confirmar → revisar → comprobar →
exportar. Dentro de **Detect + check**, la secuencia es detectar → ajustar grid
→ asignar celdas → colocar cortes → mostrar el resultado. No hay un botón ni
un paso adicional para aplicar el grid. La confirmación existente acepta el
resultado ya colocado; detectar y volver a detectar admiten Ctrl+Z.

`app/imaging/visual_grid.py` busca bandas de estampado repetidas mediante perfiles
de color y luminosidad en Lab, descontando iluminación, márgenes y fondo de cama.
Las dimensiones salen de las bandas observadas; no se prueban plantillas 6×4 o
5×3 ni se reciben cantidades esperadas. La región de tela solo limita el análisis:
todos los resultados vuelven a píxeles de la imagen original, sin cambiar escala.
El ajuste exige bandas anchas y regulares, cobertura suficiente y evidencia en
ambos ejes. Si no la encuentra, se mantiene el análisis de límites de panel
existente y, en su ausencia, el ajuste a ilustraciones sin límites visibles.

Para fondos continuos, `pattern_grid.py` complementa el detector con regiones de
primer plano completas: máscara de tela sin el borde de cámara, fondo de iluminación
por cierre morfológico y contraste Lab. Así, el interior de un dibujo grande no se
convierte en su propio fondo y no quedan únicamente fragmentos de sus contornos.
Se comparan cinco umbrales alrededor de la sensibilidad configurada. Al menos
cuatro deben coincidir en dimensiones, espaciado y fase; la confianza queda limitada
por ocupación, proporción de regiones explicadas y estabilidad. El tamaño físico
del corte no participa. Si no hay suficiente acuerdo se conserva la ruta anterior.

Una estructura respaldada por esas regiones usa `PanelGrid.source="pattern"` y
guarda el modelo afín en `PanelGrid.lattice`. Los centros finales proceden de ese
modelo, incluida su orientación. Las divisiones del editor son guías aproximadas;
editarlas manualmente elimina el modelo anterior hasta confirmar la redetección.
Restaurar el grid automático vuelve a ejecutar también esta búsqueda en fondos
continuos. Se conservan las regiones completas al redetectar sobre ese grid para
no fragmentar un dibujo que atraviese varias celdas.

Los bounding boxes se conservan en `LayoutObservation` para señalar dibujos que
abarcan varios centros de celda (`LayoutMatch.review_reason`). El dibujo recibe un
solo corte en una posición del grid, con advertencia visible en canvas, lista,
inspector y preflight. Las otras celdas cubiertas quedan pendientes aunque la
confianza sea alta: no constituyen una ilustración ausente ni generan otro corte.

`layout_from_panel_grid` toma la geometría del grid fiable y asigna dibujos por
celda. Regulariza los centros de las divisiones, sin volver a ajustarlos a los
centros de los dibujos. `detection_panel_grid` conserva la geometría usada por la
última detección, separada de las guías `panel_grid` que el usuario pueda editar.
La confirmación y redetección comprometen esas ediciones; deshacer restaura ambas.

Sin evidencia visual suficiente, el ajuste de ilustraciones utiliza NumPy:

1. Estima las direcciones de vecinos próximos de filas y columnas mediante
   medianas, permitiendo pequeña rotación y cizallamiento.
2. Proyecta los centros completos de los bounding boxes a esos ejes, agrupa
   coordenadas 1D y ajusta espaciados regulares con posibles huecos.
3. Ajusta `p = origen + columna * vector_columna + fila * vector_fila` mediante
   RANSAC determinista y regresión robusta. Exige celdas únicas y al menos dos
   observaciones por fila y columna respaldadas; una observación aislada no
   puede ampliar los límites de la cuadrícula.
4. Puntúa soporte, ocupación, residuo normalizado y cantidad de evidencia. La
   confianza es un indicador geométrico, no una probabilidad calibrada.

En este ajuste por ilustraciones, las dimensiones se infieren independientemente de las
dimensiones configuradas para `PanelGrid`. Menos de seis observaciones, una sola
fila/columna o un patrón inestable no autorizan ajustes. La confianza mínima
para usar el grid como referencia es 0,78. El ajuste tolera residuos de hasta
el 20 % del espaciado al asignar observaciones. Ese umbral comprueba si una
detección pertenece al patrón; no limita el movimiento posterior de su corte.
Cada corte asignado recibe exactamente `layout.position(columna, fila)`.

`apply_logical_layout` mantiene tamaño, identificador, score, bounding box,
centro original e inclusión. El tamaño, la forma y el centro individual del
bounding box no desplazan el corte respecto a su celda. La posición tampoco
se recorta hacia los bordes de la cama ni se desplaza para eliminar solapes:
esos problemas físicos se señalan después de colocar el conjunto. Los outliers
y duplicados conservan su detección y aparecen identificados para revisión.
Cuando la confianza es baja, las posiciones individuales son provisionales.

Para los cortes del grid, `valid_cut` comprueba los límites físicos de la cama;
`overlaps_cut` sigue comprobando colisiones. `artwork_clipped` registra por
separado si parte del bounding box queda fuera del cuadrado. Esa información se
muestra en el inspector y el preflight, pero no invalida el corte del grid ni
cambia su centro. Los cortes individuales sin grid conservan sus comprobaciones
de contención previas. Los cuadrados mantienen su tamaño físico y orientación
actual; los vectores del grid determinan la orientación de las filas/columnas.

`Detection.original_center_px` conserva el centro del detector;
`layout_anchor_px` registra el centro exacto del grid y `layout_cell` la columna
y fila. `center_cuts_on_visual_anchors` y `resolve_cut_overlaps` mantienen fijos
esos cortes. Cuando todos están colocados, el centrado aparece ya completado.
Los conflictos entre cortes del grid requieren revisar tamaño, calibración o
hacer una excepción manual; el solver no deforma la cuadrícula.

El análisis usa bounding boxes originales, nunca centros corregidos. Mover un
corte manualmente conserva su observación y deja una excepción explícita sin
reajustar los demás. Borrar o excluir evidencia recalcula las asignaciones y,
cuando el modelo procede de ilustraciones, también su ajuste. Un grid visual
conserva su geometría aunque falten ilustraciones. Los cortes inferidos automáticos
nunca aportan evidencia al ajuste. Al recalcular, siguen la posición exacta de su
celda mientras el grid sea fiable. Si el usuario elimina uno, la celda queda
suprimida hasta una nueva detección; Deshacer restaura también esa supresión. Deshacer
restaura geometría, fuentes, asignaciones e inclusiones. Cambiar unidades, zoom,
tamaño de corte o calibración conserva las posiciones en píxeles del grid.

Los huecos dentro de la extensión observada se guardan como `MissingPosition`:

- `review_state` conserva internamente la fuerza de la evidencia para depuración.
  No genera controles ni estados adicionales en la interfaz.
- Cuando el grid global es fiable, cada hueco crea automáticamente un corte
  `Detection.inferred=True`, sin bounding box ni centro del detector. Esa marca
  no se muestra al usuario y solo permanece en el modelo y el JSON de diagnóstico.

Un grid fiable materializa sus celdas vacías y esos cuadrados participan en el SVG
como cualquier otro. El usuario puede borrarlos en Review cuts. Con confianza baja
no se crean. Un bloque interior denso puede extender una única fila o columna
adyacente cuando existe al menos una detección exterior muy próxima a la posición
extrapolada; ese punto no reajusta la geometría y los outliers desalineados no
amplían el grid.

**Show grid evidence** muestra puntos originales, bounding boxes, propuestas azules
y guías inclinadas. La lista indica outliers/duplicados; el inspector muestra
posición original, propuesta y residuo. El JSON opcional junto al SVG incluye
modelo afín, confianza, asignaciones, huecos y datos originales/finales, sin
cambiar las unidades ni la política de exportación existentes.

Las pruebas `test_logical_layout.py` cubren fondos sin divisiones usando el
detector real, diferentes dimensiones, rotación/cizallamiento, ruido, outliers,
duplicados, huecos, baja confianza, dibujos anchos, cortes manuales, colisiones,
colocación exacta sin límites de desplazamiento, recorte del dibujo, límites de
cama sin desplazar centros, solapes sin deformar el grid, SVG y round-trip en
todas las unidades. Las pruebas de UI comprueban colocación automática antes de
confirmar, redetección idéntica, excepciones manuales, creación automática de
celdas vacías sin realimentación, borrado persistente, deshacer y nueva imagen.
`test_visual_grid.py` añade la foto original de cámara como regresión (24 dibujos),
otras seis distribuciones generadas, márgenes, fondo de cama, ausencia de bandas,
celdas vacías y asignaciones independientes del centro del dibujo. La prueba UI
de cámara comprueba detección sin configurar dimensiones, centros exactos, revisión,
tamaño, guías provisionales y deshacer. La foto vive en `tests/fixtures/`.
El ajuste afín por ilustraciones no corrige perspectiva fuerte ni deformación
local de la tela; la búsqueda de bandas visuales utiliza los ejes de la imagen.

`camera_panel.py` añade un fallback para patchwork fotografiado con fondos que
se tocan. Aísla una región de tela cuadrilateral y rectifica una copia solo para
analizarla. Las divisiones se buscan por cambios de color amplios, en varias
escalas, exigiendo acuerdo en dimensiones y separación respecto a alternativas.
La evidencia debe abarcar la mayor parte del eje perpendicular, evitando tomar
los bordes repetidos de los dibujos por costuras. No se especifican filas ni
columnas, y esta ruta no sustituye una disposición ya respaldada por el detector.

La segmentación local auxiliar usa GrabCut con el borde de celda como fondo, sin
semillas obligatorias de primer plano. Mantiene el área mínima configurada y
permite no encontrar un dibujo: los huecos fiables se proponen para revisión.
Los resultados se proyectan a la foto original. `PanelGrid.projection` y
`LogicalLayout.projection` conservan una sola homografía del grid regular; no se
hacen ajustes independientes por dibujo ni se modifica el mapeo físico de la
imagen. Filas y columnas siguen siendo líneas rectas, aunque su separación
aparente cambie con la perspectiva. Las divisiones automáticas se dibujan con
esa transformación. Editar las guías manuales la descarta al confirmar, como el
modelo afín anterior. Los cuadrados mantienen tamaño y orientación de exportación.
La deformación local de tela y la calibración de la cámara siguen siendo asuntos
distintos de encontrar las celdas.

`test_camera_panel.py` reproduce la foto tenue de patchwork que antes daba seis
detecciones: encuentra 6×4, conserva 22 dibujos y propone dos huecos (luna y
corderito). Comprueba otras dimensiones y ángulos, coordenadas proyectadas,
fondos vacíos, y que el fallback no degrade la colección anterior de vehículos.
La prueba UI verifica la imagen y calibración originales, aceptación explícita
de huecos, centrado, tamaño y deshacer. Un solape físico no deforma el grid.

La regresión `test_pattern_grid.py` incluye la foto original de transportes:
5 columnas × 4 filas, 19 ilustraciones (la jirafa atraviesa dos filas), sin celdas
configuradas a mano. Comprueba agrupación, escala de imagen, otras dimensiones,
rechazo de imágenes irregulares y huecos. La prueba UI conserva los centros al
revisar, deshacer, cambiar tamaño y restaurar el grid. Con la escala de la foto,
los cortes de 5 pulgadas se solapan entre filas: se señalan sin deformar el grid
ni reducir el tamaño solicitado. El caso de paneles pastel sigue cubierto aparte.

## Exportación

`SVGExporter` crea un SVG con el tamaño físico completo de la cama y un `viewBox` en la misma unidad. Solo escribe elementos `<rect>` exportables.

`verify_export_geometry` convierte la geometría a la unidad SVG, la reconstruye a pulgadas y finalmente a píxeles. Este recorrido permite detectar errores de escala, offset o conversión.

`export_debug_json` registra máquina, unidades, colocación de imagen, escalas y estado de cada detección.

## Configuración persistente

Los perfiles personalizados se guardan en:

```text
%APPDATA%\Lalikul\CutPrep\machines.json
```

Las referencias de cama vacía proporcionadas por el usuario se guardan por
máquina en:

```text
%APPDATA%\Lalikul\CutPrep\bed_references\
```

La referencia predeterminada de Epilog se distribuye en
`assets/references/epilog/empty_bed.png`. Los resultados de detección no se
guardan automáticamente.

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
