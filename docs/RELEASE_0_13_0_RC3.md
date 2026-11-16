# Lalikul Cut Prep 0.13.0-rc3 — recuperación del marco exterior

Candidata local. Esta corrección trata la colocación geométrica de las casillas;
la guía de colores propuesta por el usuario es una decisión de presentación separada.

## Problema reproducido

El informe recibido se reprodujo con idénticas huellas de entrada y resultado.
La propuesta alternativa basada en bandas situaba el borde superior demasiado
abajo. El afinado corregía las divisiones interiores pero no encontraba el marco
superior, fuera de su ventana de búsqueda. Conservaba esa estimación antigua y
hacía la primera fila artificialmente más baja y pequeña.

La reproducción y sus datos originales se conservan en
[el diagnóstico](qa/user-first-row-20261115/index.html).

## Corrección general

Si un borde exterior no ha sido observado y dos divisiones vecinas medidas
contradicen su posición, se vuelve a buscar el marco desde esas divisiones.
La predicción solo sitúa una ventana; nunca se convierte por sí sola en borde.
Dos lecturas de línea oscura sostenida deben acordar el centro del trazo,
sin confundir sus flancos, otra línea parecida o la transición entre tela y cama.
La regla funciona en los cuatro lados. Una búsqueda fallida queda explícitamente
sin confirmar. Se conserva el suelo previo de incertidumbre.

No se cambian las dimensiones solicitadas, la calibración, los guías manuales
ni los proyectivos. Los centros se calculan desde los límites de las casillas.
El cambio no contiene nombres de fotos, especies, recuentos ni tamaños de corte.

## Comprobaciones de la nueva foto

Con el mismo corte elegido de 4 pulgadas:

- Borde superior: Y=99,62 pasa a Y=59,65, contrastado con el marco del original.
- Centro de primera fila: Y=175,41 pasa a Y=155,43.
- Los seis cruces de sección superiores desaparecen; el centro de la última
  fila permanece en Y=714,4.
- La foto original, el espejo vertical y dos resoluciones reducidas conservan
  24 cortes; el error vertical máximo contra las referencias pasa de unos
  20 píxeles a 3,2 píxeles o menos, normalizado a la resolución original.
- SVG conserva dimensiones, coordenadas e inclusión de los avisos marcados
  dentro de cama. Zoom, cambio de unidades y deshacer conservan su geometría;
  desmarcar un corte lo retira de la salida.

Las referencias horizontales aproximadas admiten 4 píxeles de error de medida.
El control no certifica físicamente cada punto de todos los marcos ligeramente
inclinados ni la silueta completa de cada animal.

## Estado de validación

La suite completa termina con **330 pruebas, 43 módulos, sin fallos, errores ni
omitidas**. Las 62 entradas anteriores conservan exactamente geometría, estados,
recuentos y SVG respecto a rc2. Esto conserva sus limitaciones anteriores; no
certifica todos los dibujos ni todos los bordes físicos. El resultado está en
[la comparación visual](qa/release-0.13.0-rc3/index.html).

Se conservan los paquetes y las fuentes de rc2 para comprobar la regresión.
Esta candidata no es un tag publicado ni una validación física de la Epilog.
