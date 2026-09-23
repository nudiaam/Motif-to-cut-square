# Detección guiada con OpenCV — 21 de septiembre de 2026

Se mantiene el motor existente, sin SAM, YOLO, modelos descargados ni nuevas
dependencias. La generación de las imágenes de prueba se hizo con la herramienta
integrada `image_gen`; no forma parte del funcionamiento de la aplicación.

## Cambios

- Antes de aceptar una cuadrícula visual, se comprueba si deja fuera varios
  motivos alineados con una fila o columna adyacente. Esos motivos deben tener
  evidencia en un umbral más estricto y ocupar distintas posiciones. Una marca
  aislada, un margen vacío o fragmentos de la misma casilla no bastan. Se conserva
  la posición de las líneas existentes y no se extrapolan guías manuales.
- Antes de aceptar dos recortes vecinos, se contrasta la imagen completa. Un
  dibujo estrecho que ocupa dos casillas puede conservarse como una sola pieza
  si también aparece completo sin agrupar componentes por proximidad. Los grupos
  amplios de fondo y los vecinos sin esa evidencia no se fusionan.
- La comprobación de dibujos completos también se aplica al volver a detectar
  dentro de las guías confirmadas, sin modificar sus divisiones.
- Una casilla cubierta por un dibujo asignado a otra casilla deja de generar un
  corte automático adicional. Se retira un corte automático obsoleto, pero se
  respeta uno que el usuario haya convertido en una elección manual.
- Los diagnósticos registran las extensiones y los dibujos conservados completos.
  Los avisos existentes de recorte, solapamiento y asignación siguen activos.

## Imágenes generadas y resultados

Los [PNG y los prompts](../tests/fixtures/generated/README.md) están guardados en
el proyecto sin modificar las imágenes generadas.

| Caso sintético | Motivos esperados | Candidatos antes | Candidatos después |
| --- | ---: | ---: | ---: |
| Animales pastel | 24 | 18 | 24 |
| Transporte con jirafa de dos casillas | 19 | 20 | 19 |
| Floral sin líneas de panel | 24 | 20 | 24 |

Una ejecución local de la detección completa en la interfaz tardó 1,93 / 1,45 /
1,39 segundos respectivamente. Son mediciones orientativas de este equipo, no
una garantía de rendimiento en el ordenador del cliente ni una comparativa de
memoria. La lógica añade pasadas de OpenCV; la comprobación adicional de
continuidad solo se ejecuta si existen posibles dibujos de varias casillas.

## Límites comprobados

El recuento y la cobertura de las casillas mejoran; eso no certifica la silueta
completa ni la posición física del corte. En la revisión con cuadrados de 5
pulgadas permanecen avisos: dos motivos recortados en pastel, nueve en transporte
y cuatro en floral. En floral también hay solapamientos entre filas. Las imágenes
generadas no tienen una escala física conocida y el tamaño del cuadrado no se
ajusta automáticamente para ocultar estos problemas. La jirafa completa requiere
revisar tamaño y posición, no dos cortes automáticos sobre el mismo dibujo.

Estas imágenes han servido para desarrollar las reglas, por lo que no constituyen
una evaluación independiente. Tampoco prueban todas las colecciones de Eugenio.
Se deben añadir imágenes nuevas no utilizadas para ajustar el algoritmo y, cuando
sea posible, fotografías de la cámara sin las detecciones superpuestas.

Validación realizada: las 158 pruebas pasan, incluidas ocho nuevas y las imágenes
anteriores del proyecto. Se inspeccionó visualmente la interfaz renderizada con
los tres casos nuevos. La prueba de transporte anterior exige ahora 19 cortes,
en lugar de perpetuar el corte adicional como resultado esperado.

La política existente que completa otros huecos fiables de la cuadrícula sigue
activa: esta corrección excluye específicamente las posiciones ya cubiertas por
otro dibujo. Un corte inferido sigue necesitando comprobarse contra la imagen.
