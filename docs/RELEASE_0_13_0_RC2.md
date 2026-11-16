# Lalikul Cut Prep 0.13.0-rc2 — corrección y comprobaciones

Estado: candidata local comprobada. No es una validación física de la Epilog.
La versión aparece en la ventana; debe cerrarse la instancia anterior y abrir
la app de nuevo para cargar el código actualizado.

## Qué cambia

- Una división observada se distingue de una predicción por espaciado. La
  concordancia entre lecturas incluye los bordes exteriores. Los bordes sin
  respaldo suficiente conservan revisión explícita, sin eliminar composiciones
  recuperadas ni recortar las filas hacia una predicción más interior.
- El límite oscuro de la copia rectificada no se trata como borde impreso:
  allí faltan píxeles a ambos lados del filtro. Esto corrige la confusión entre
  estampado, margen sin imprimir y borde de análisis.
- Los centros siguen las casillas y no se desplazan para contener un dibujo.
  Los cambios de tamaño conservan esos centros y las dimensiones solicitadas.
- Morado explica una duda de contorno, posible recorte o guía. Rojo exige un
  contorno resuelto recortado, fuente incompleta o cruce más allá de la
  incertidumbre medida. Los cortes que salen de cama se omiten; los demás
  marcados pueden exportarse con sus avisos.

## Resultados registrados

- Suite completa: **325 pruebas**, 42 módulos, sin fallos, errores ni omitidas.
- **62 entradas distintas**: se conservan todos los recuentos y dimensiones de
  malla de la entrega anterior y los grupos de puntos de dibujo comprobados.
  No aparece ningún verde con un cruce superior a la tolerancia de las
  referencias independientes disponibles, ni verdes con revisión pendiente.
- **45 variaciones fotográficas y 531 grupos de puntos** conservan sus propietarios.
- Flujo real de diez fotos: **194 cortes**, tamaño adaptado de prueba, esquinas,
  SVG serializado, exclusión manual, zoom, unidades y deshacer comprobados.
- Los dos casos de filas solapadas que motivaron la revisión pasan de **12 a
  0 cortes solapados**. Sus centros centrales se contrastan con medidas sobre
  los originales, también a dos resoluciones inferiores.
- En el control frontal pastel, los 24 centros quedan como máximo a **2,12 px**
  de las anotaciones independientes. Al seleccionar 4,6 pulgadas, las cuatro
  esquinas de todos los cortes quedan dentro del estampado, con al menos
  **4,73 px** de margen anotado, y se exportan sus 24 rectángulos.

Los datos completos están en [la comparación visual](qa/release-0.13.0-rc2/index.html),
[release-gate.json](qa/release-0.13.0-rc2/release-gate.json) y
[valid-size-control.json](qa/release-0.13.0-rc2/valid-size-control.json).

## Por qué no todo se vuelve verde a 5 pulgadas

Las imágenes generadas no respetan necesariamente medidas físicas ni casillas
idénticas. En el control pastel frontal la casilla anotada más corta tiene
207 píxeles de altura, mientras 5 pulgadas representan 213,33 píxeles con su
colocación actual. Ese corte no cabe. Antes había centros desplazados; corregir
los centros puede hacer visible un conflicto de tamaño que antes se ocultaba.

La comparación a 5 pulgadas conserva esos conflictos. En dos entradas aparecen
más solapes a ese tamaño: el control frontal pastel y el panel claro de cinco
columnas. No se aprueban sus salidas de 5 pulgadas. Se mantienen los avisos;
sus centros y tamaños no se alteran silenciosamente. El control positivo de
4,6 pulgadas y la prueba de diez imágenes con tamaño adaptado son operaciones
de prueba explícitas, no un ajuste automático de la aplicación.

Además se comprueba numéricamente la geometría de los mismos centros con
cuadrados de 3 pulgadas: en las 62 entradas no hay solapes. Este cálculo aísla
la distribución de centros; **no certifica que un cuadrado de 3 pulgadas contenga
todo el dibujo** y no sustituye los SVG reales de la configuración elegida.

## Qué no demuestra esta comprobación

Solo 14 entradas tienen referencias de malla independientes aproximadas. Las
otras 48 no quedan certificadas físicamente por conservar un recuento. Los puntos
de dibujo son muestras y no siluetas completas. Se mantienen revisiones donde
faltan datos y no se declara resuelta toda segmentación tenue o decorativa.

Se corrigió una esquina mal medida de la referencia de contraste bajo, comprobando
el marco en el original con reglas de píxeles. Se conservan el valor anterior,
el nuevo y la imagen justificativa en
[reference-notes.json](qa/release-0.13.0-rc2/reference-notes.json). Las referencias
no se entregan al detector como entradas.

Los SVG reproducen los cortes marcados dentro de cama, con página de 36 × 24
pulgadas y petición de margen cero. Esto no verifica la calibración cámara/máquina
ni las opciones de impresión del controlador. No se ha realizado un corte físico.

## Identificación y recuperación

Se conserva el commit anterior, el diff de la entrega cuestionada y las copias
aisladas usadas en la auditoría. La candidata `0.13.0-rc1` pasó 324 tests pero fue
rechazada por la comprobación fotográfica del marco inferior: se conserva su
snapshot y el motivo. Esa comprobación detuvo la entrega, como debía.

`0.13.0-rc2` identifica el estado corregido; su revisión de detector es
`2026-11-15-observed-divisions-rc2`. Los manifiestos de fuentes y archivos de
entrega permiten reconstruir y comprobar esta candidata sin confundirla con
la ventana anterior `v0.12.0`. Es un snapshot y un parche identificados, no un
tag publicado ni una instalación enviada al cliente.

La auditoría histórica está en [REGRESSION_REVIEW_20261115.md](REGRESSION_REVIEW_20261115.md).
Los [diez prompts](TEST_PROMPTS_10.md) permiten preparar otras pruebas visuales.
