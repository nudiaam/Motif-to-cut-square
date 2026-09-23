# Propuesta de solución global — 21-09-2026

Estado actualizado: se ha implementado una primera corrección transversal en
los cuatro puntos, con 166 pruebas automatizadas superadas. El diseño completo
descrito más abajo sigue siendo un objetivo, no una descripción de funcionalidad
ya terminada. El código actual comparte agrupación y revisión, pero aún usa
distintos extractores y no conserva máscaras de todos los componentes.

Resultados y límites observados: [evaluación de la implementación](qa/global-rework/README.md).
Se mantiene OpenCV y NumPy, sin incorporar modelos pesados. No se ha demostrado
detección perfecta de siluetas ni generalización a todas las colecciones.

## Evidencia de defectos comunes

1. `_detect_layout` tiene retornos anticipados con resultados de distinta unidad:
   las ramas de paneles producen como máximo un candidato local por casilla;
   la rama `pattern` devuelve regiones, incluidos accesorios independientes.
   Un resultado geométricamente fiable no demuestra que esas regiones sean piezas.
2. `camera_panel._axis_choices` usa `step = length / count`. Después de estimar
   el número de divisiones, `infer_camera_panel` crea `PanelGrid.regular(w,h,...)`
   sobre todo el contorno rectificado de tela. Los márgenes no se estiman como
   parámetros independientes del área impresa.
3. `detect_in_grid` elimina un margen del 3,5 % antes de analizar cada casilla.
   `_local_colour_region` aplica a continuación GrabCut con un rectángulo interior
   del 80 % de anchura y 86 % de altura. En `GC_INIT_WITH_RECT`, todo lo exterior
   a ese rectángulo es fondo definitivo. No puede recuperarse durante esa pasada.
4. `Detection.contains_artwork` comprueba solo la caja detectada. Si esa caja
   perdió extremos, `READY` no puede advertirlo: se valida contra información ya
   incompleta y no se representa la incertidumbre sobre la extensión del motivo.

### Pruebas de mecanismo previas a los cambios, sin colecciones nuevas

Los resultados están en [global_detection_experiments.json](qa/straight-panels/global_detection_experiments.json).

- Figura geométrica de color uniforme con un extremo inferior progresivamente
  más largo: la caja real llega a `(70,45,61,152)`, pero el método anterior devuelve
  `(70,45,61,141)`. La extensión deja de crecer en el límite impuesto por el
  rectángulo, aunque el objeto sigue teniendo el mismo color claramente separado
  del fondo. Una inicialización por máscara con semillas correctas conocidas y
  el resto incierto recupera la extensión completa en las cinco variantes.
  Esto prueba el mecanismo; las semillas conocidas de esta prueba no constituyen
  un algoritmo automático para telas arbitrarias.
- Misma imagen de perros, sin modificar los píxeles originales: al añadir 160
  píxeles de fondo oscuro por cada lado, pasa de 24 candidatos / cuadrícula 6×4
  (`camera`) a 15 / 6×3 (`automatic`). Con 80 píxeles mantiene 24. Pastel conserva
  25 y corazones 24 en las tres variantes. El defecto de estabilidad existe,
  aunque no se manifieste en todos los estilos. Solo se evaluó detección; no se
  reinterpretaron esas imágenes ampliadas como camas con la misma escala física.

## Un solo contrato para todos los paneles regulares

El resultado intermedio debe separar `layout`, `components`, `compositions`,
`unassigned_evidence` y `extent_uncertainty`. Las estrategias actuales pueden
aportar evidencia, pero no decidir por separado qué es una pieza. Ninguna región
se convierte en corte antes de pasar por la misma asignación global.

Una composición puede contener componentes desconectados. Una celda es una guía
espacial, no una garantía de que haya exactamente una pieza ni un límite rígido
del dibujo. Deben representarse celdas vacías, composiciones que abarcan varias
y asignaciones ambiguas. No añadir detecciones para conseguir un recuento objetivo.
La detección libre, si se conserva, será un modo explícito y no un cambio silencioso
provocado por colores o por encuadre.

## 1. Agrupación consistente

Todos los extractores producen componentes candidatos con máscara, posición y
procedencia. Un único paso asigna esos componentes a composiciones mediante
distancia normalizada por el espaciado del panel, separación respecto a vecinos,
continuidad y evidencia de repetición del fondo. El color aporta evidencia, pero
no se exige que un accesorio tenga el mismo color que la figura principal.

No fusionar todo lo que caiga en la misma casilla ni eliminar todos los objetos
pequeños. Un accesorio puede estar separado y un motivo completo puede ser pequeño.
Si varias asignaciones son plausibles, conservar el componente como no resuelto
y no crear automáticamente una pieza nueva. La textura repetida se estima desde
la propia foto; no requiere archivos originales ni plantillas de colección.

## 2. Cuadrícula independiente de los márgenes

Separar cuatro geometrías: imagen de cámara, contorno de tela, área impresa y
distribución de composiciones. Buscar origen y espaciado de filas/columnas como
parámetros independientes, usando cambios de color/textura sostenidos a lo largo
de la tela y periodicidad. Comparar hipótesis de dimensiones, evitando elegir
como filas los lunares o rayas del estampado. Cuando no haya divisiones impresas,
la repetición de las composiciones aporta evidencia al mismo modelo geométrico.

Normalizar el análisis al área de tela, conservar la transformación a los píxeles
originales y expresar umbrales en proporción al panel, no a la imagen completa.
No repartir automáticamente todo el ancho o alto de la tela entre N posiciones.
No aceptar una cuadrícula débil solo porque una rama anterior no produjo resultado.

## 3. Análisis con contexto y sin exclusiones injustificadas

Analizar ventanas solapadas que incluyan contexto más allá de las guías. Marcar
como fondo definitivo solo píxeles con evidencia suficiente; mantener como
probables o desconocidos los límites de casilla. Usar `GC_INIT_WITH_MASK` cuando
existan semillas fiables, sin asumir que el centro de la casilla es objeto.

Si la región llega al borde de la ventana, ampliar y repetir hasta estabilizar
la extensión o marcarla incierta. La asignación global impide que un fragmento
visto en dos ventanas se cuente dos veces. Conservar coordenadas y máscara sobre
la imagen original. No basta con ampliar todos los rectángulos un porcentaje fijo.

## 4. Validación capaz de contradecir la primera detección

Separar validez geométrica del cuadrado y suficiencia de la evidencia visual.
La revisión debe volver a la imagen original, con mayor contexto y una extracción
de evidencia alternativa: examinar continuidad más allá de los límites detectados,
componentes no asignados y estabilidad al ampliar la ventana o variar moderadamente
la segmentación. Bordes de fondo repetido no deben tratarse automáticamente como
dibujos cortados. Dos umbrales similares no constituyen evidencia independiente.

No mostrar un motivo como listo si toca un límite de análisis, su extensión crece
al ampliar el contexto, existen componentes próximos sin asignar o la cuadrícula
es ambigua. Ninguna comprobación de este tipo certifica la ausencia de todas las
partes invisibles o indistinguibles: el estado debe reflejar esa incertidumbre.

El tamaño físico del corte es una restricción separada. Si la pieza completa no
cabe, señalarlo; no encoger su máscara ni desplazar silenciosamente la retícula
para que el resultado parezca válido. Una calibración errónea exige corregir la
calibración, no el reconocimiento.

## Implantación y aceptación

1. Definir el resultado común y las pruebas de estabilidad antes de cambiar
   parámetros. Fijar las reglas y registrar las decisiones de cada fase.
2. Sustituir la geometría dependiente del encuadre por origen/espaciado/márgenes
   estimados; utilizar el mismo paso de composición en todas las ramas.
3. Eliminar el recorte destructivo, añadir contexto y revisar los estados de
   calidad. Evitar que un resultado parcial se convierta en evidencia de sí mismo.
4. Evaluar conteo, asignación y contención con anotaciones de la composición
   completa. Probar margen añadido, traslación, resolución, iluminación y contraste
   moderados, llevando siempre las coordenadas de vuelta al mismo sistema.
5. Reservar colecciones nuevas para evaluación después de fijar el método. Las
   imágenes actuales ya han sido inspeccionadas y no son un conjunto independiente.

Pruebas esenciales: un accesorio separado no crea otra pieza; añadir margen no
cambia piezas ni geometría sobre la tela; una extremidad que cruza una guía sigue
siendo visible; un extremo omitido impide declarar listo el corte; fondos repetidos
no obligan a unir vecinos; una casilla realmente vacía no se rellena como detección.

Coste previsto: análisis global a resolución reducida, máscaras y componentes
ligeros, refinado secuencial de zonas dudosas. No necesita una GPU ni nuevos modelos.
La latencia total y los límites de memoria deben medirse cuando exista el prototipo;
las mediciones anteriores no demuestran el rendimiento de esta arquitectura nueva.

## Fuentes técnicas primarias

- [OpenCV: GrabCut e inicialización por máscara](https://docs.opencv.org/4.x/d8/d83/tutorial_py_grabcut.html).
  Explica la exclusión definitiva fuera del rectángulo y las cuatro etiquetas.
- [OpenCV: Sobel y Scharr](https://docs.opencv.org/4.x/d2/d2c/tutorial_sobel_derivatives.html).
  Herramientas para obtener evidencia direccional de divisiones impresas.
- [OpenCV: componentes y geometría](https://docs.opencv.org/4.x/d3/dc0/group__imgproc__shape.html).
  Primitivas disponibles para describir regiones sin clasificarlas semánticamente.
- [OpenCV: watershed con marcadores](https://docs.opencv.org/4.x/d3/db4/tutorial_py_watershed.html).
  Alternativa para zonas de contacto con marcadores fiables; no se propone como
  reemplazo universal, pues la textura también puede producir sobresegmentación.

La arquitectura propuesta es una inferencia de ingeniería a partir de los fallos
observados y estas capacidades; las fuentes no demuestran su eficacia en estas telas.
