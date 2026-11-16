# Lalikul Cut Prep 0.13.4

Versión con corrección conjunta de límites, filas vacías y colores.
La validación final y los resultados se registran en
[el informe visual](qa/release-0.13.4/index.html).

## Cambios

Las casillas automáticas proyectadas se contrastan con franjas blancas y marcos
en la fotografía original. Los vértices compartidos evitan que ajustes vecinos
creen secciones incompatibles. Los cortes conservan el tamaño elegido y el
centro geométrico de su propia sección.

Un marco cerrado y la terminación de las divisiones perpendiculares permiten
separar estampado y margen sin imprimir. Los huecos de una cuadrícula dejan de
crear cortes por sí solos. Una lectura local puede recuperar una composición
tenue si existe tinta coherente respaldada por las dos lecturas; la textura
pequeña y dispersa de una silueta fallida no prueba otro dibujo.

Verde significa sin cruce de sección medido; morado, cruce de sección; rojo,
geometría imposible. Las dudas de contorno, la posible pérdida de parte del
dibujo, los solapes y la confianza de las guías siguen en los detalles. El verde
no certifica la silueta completa ni una calibración física. La misma regla se
usa en lienzo, miniatura, lista, recuentos y resumen de exportación.

## Comprobaciones específicas

Los paquetes 01 y 02 se conservan con la reproducción exacta de 0.13.3 en
[el diagnóstico original](qa/diagnosis-20261116/index.html).
En 01 se contrastan las separaciones internas con lecturas independientes de
las franjas blancas. En 02 deben quedar cuatro filas impresas y 24 cortes,
sin cortes sobre el margen. Se prueban 4 y 5 pulgadas, espejo vertical y dos
resoluciones reducidas; cambiar tamaño no mueve centros.

Se añade un control de otra colección que muestra 23 animales: una posición
vacía y una oveja muy tenue. La salida antigua de 24 rellenaba ambos huecos sin
imagen. La nueva lectura conserva la oveja con caja real y retira el relleno
vacío. Se comprueban 23 puntos de dibujo, cada uno con propietario distinto.

## Exportación y alcance

El algoritmo de serialización del SVG no cambia. Los avisos marcados dentro de
cama permanecen exportables; los cortes fuera de cama se omiten. Zoom, unidades,
Navegador y deshacer conservan la geometría exportada. Las notas de segmentación
no eliminan cortes marcados de la salida. El campo diagnóstico `cut_state`
describe la presentación; `valid` y `legacy_solver_exportable` conservan los
criterios internos históricos del solucionador. `exportable` refleja ahora la
inclusión efectiva en el SVG.

Los originales generados no fijan medidas físicas. Se conservan los conflictos
reales de tamaños incompatibles. Las referencias manuales de malla son
aproximadas; los puntos de dibujo no certifican cada píxel de una silueta.
No se ha verificado un corte físico, el controlador de impresión o la calibración
cámara/máquina. La distribución se identifica con la etiqueta `v0.13.4` en GitHub.

El [contrato vigente](CUTTING_RULES.md) sustituye los criterios de colores y de
relleno automático descritos en informes históricos.

## Resultado final de la validación

339 pruebas, 44 módulos, sin fallos, errores ni omitidas.
Se comparan 62 entradas anteriores y ocho variantes de los dos paquetes nuevos.
Las separaciones internas medidas del 01 pasan de 3.72 a 0.86 px de error máximo aproximado.
Se conservan las discrepancias de las referencias antiguas y los límites de la comprobación en el informe.

## Rendimiento

El [informe de rendimiento](PERFORMANCE_0_13_4.md) identifica el portátil del
cliente, la medición histórica y las nuevas comparaciones con recursos limitados.
No confunde esos resultados locales con tiempos medidos en el portátil.

Las fotografías del cliente, paquetes de diagnóstico y capturas de QA se conservan
localmente y no se publican en GitHub. Los enlaces `qa/` de los informes históricos
son referencias al archivo privado de evidencias, no descargas públicas.
