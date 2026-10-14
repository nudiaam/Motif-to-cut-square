# Conservación de composiciones — implementación del 14/10/2026

Validación definitiva: **238 pruebas pasan**, en 672,214 segundos, sin fallos
(`tests-verified.txt`). No se modificaron las expectativas de los testigos de
sombras para resolver las dos regresiones iniciales.

El selector y la recuperación de apariencia comprueban ahora el contenido del
grupo completo antes de aceptar límites nuevos. Se compara luminancia y color;
una composición conocida debe conservar al menos el 98 % de su tinta en un único
resultado. Varias piezas pueden unirse, pero no justificar un grupo dividido.
No hay reglas por nombre de colección, OCR ni cantidades prefijadas.

## Resultados de las imágenes aportadas

| Entrada limpia | Política anterior: grupos completos | Implementación: grupos completos |
|---|---:|---:|
| Cócteles, ingredientes y hielo | 14/18 | 18/18 |
| Frases negras y adornos de color | 7/16 | 16/16 |

Los controles usan puntos sobre contenido inspeccionado en las imágenes originales,
independientes de las cajas del detector. También comprueban que un grupo no
incorpore el elemento principal de un vecino y que los píxeles originales no cambien.
Se prueban nueve variantes por entrada: cambios de escala, encuadre, iluminación
y ajustes de análisis. `variants.json` conserva la evaluación de agrupación de
la primera implementación; `tests-verified.txt` comprueba el código definitivo.

La comparación previa se reproduce con `../reproduce_baseline.py`, mediante
intervenciones en memoria sobre la política de selección y sin conservación de
contenido. Sus resultados están en `../baseline/`; no es un checkout histórico.

## Protección de las colecciones anteriores

`regression-verified/results.json` contiene 21 entradas anteriores, comparadas con
`../../composition-recovery/regression-final/results.json` mediante el mismo hash
de imagen. `regression-comparison.json` resume:

- 21/21 mantienen su cantidad de detecciones y su cuadrícula.
- 19/21 mantienen exactamente el resultado completo anterior.
- Animales con accesorios conservan 12 grupos y su cuadrícula; los límites cambian
  ligeramente al sustituir la extracción local por evidencia de composición.
- Hojas conservan 15 grupos y su cuadrícula; se recupera un límite que antes
  abarcaba erróneamente toda la imagen. Sus testigos independientes siguen pasando.

La batería incluye alfabeto, números y objetos, animales con accesorios, Navidad,
flores, transportes, corazones, campos con sombras, figuras que atraviesan celdas,
celdas vacías, guías manuales y exclusiones de dibujos incompletos. Dos regresiones
de sombras aparecieron en la primera ejecución completa (`tests-final.txt`):
se resolvieron antes de la ejecución definitiva, sin eliminar las comprobaciones.

## Cuándo se permite cambiar geometría

- La tinta de referencia debe estar respaldada por asignaciones únicas,
  ocupación y alineación. Una caja provisional de fondo o una partición incorrecta
  no puede impedir recuperar las composiciones verdaderas.
- Los modos locales del fondo deben ser compatibles antes de usar un modelo
  global de tinta. Ante sombras amplias, se conservan las rutas locales existentes.
- Una caja provisional que toca el marco solo se protege como fragmento de borde
  si hay tinta de tela en ese borde o ya está marcada como incompleta.
- Las guías impresas o confirmadas conservan su posición. Un campo escaso continúa
  en revisión y no autoriza inventar cortes.

## Contención y tamaño físico

El nuevo ajuste de fase mueve toda la cuadrícula automática con la misma
traslación, cuando existe un intervalo común que contiene todos los grupos en
el tamaño elegido y dentro de la cama. Mantiene vectores, filas y columnas; no
recoloca los cuadrados individualmente. No modifica guías manuales/impresas,
campos incompletos ni tamaños que no permiten contener todos los dibujos.

Las imágenes no están calibradas físicamente. Con el mapeo supuesto de la foto a
36 × 24 pulgadas, los estados reales de la interfaz (`*-ui-sizes.json`) son:

| Entrada | Tamaño | Grupos cuyo dibujo excede el corte | Cortes con solapamiento |
|---|---:|---:|---:|
| Cócteles | 4 pulgadas | 18 | 0 |
| Cócteles | 5 pulgadas | 4 | 0 |
| Frases | 4 pulgadas | 11 | 0 |
| Frases | 4,6 pulgadas | 2 | 0 |
| Frases | 5 pulgadas | 0 | 16 |

Estos avisos son correctos y permanecen visibles. Detectar el grupo completo no
garantiza que quepa en cualquier tamaño. Los 4,6 pulgadas no tienen un intervalo
común viable para todas las frases. El caso sintético de la prueba de fase sí
comprueba una traslación viable, sin deformar alineaciones ni salir de la cama.

`*-4in-ui.png` muestra los controles configurados a cuatro pulgadas y sus avisos.
`render_ui.py` reproduce las capturas. La captura anterior
`quotes-feasible-ui.png` era una prueba a 4,6 pulgadas y no acredita viabilidad;
consultar `quotes-4.6in-ui.png` y los estados actuales.

## Reproducción

Desde la raíz, con el entorno virtual del proyecto y `QT_QPA_PLATFORM=offscreen`:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m tests.evaluate_composition_groups --output docs/qa/group-extent-audit/fixed/variants.json
.venv\Scripts\python.exe -m tests.evaluate_customer_collections --output docs/qa/group-extent-audit/fixed/regression-verified
```

El alcance probado es el conjunto guardado de imágenes y variantes; todavía
se requiere revisar el resultado y validar escala, origen y SVG en la máquina.
