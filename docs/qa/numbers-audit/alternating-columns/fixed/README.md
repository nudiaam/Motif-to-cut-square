# Comparación condicional de grupos compuestos

Este documento conserva la validación del cambio anterior. El fichero
`at-risk-comparison.json` fue regenerado al comparar la recuperación de tinta
completa posterior; acredita esa comparación actual y no la intervención
histórica de desactivar la ruta compuesta. Sus resultados actuales se conservan
también en [el informe siguiente](../../../holdout-20261014/README.md).

Implementación del 14/10/2026. Alcance de pruebas limitado a las colecciones que
pidió el usuario: números, alfabeto, frases, cócteles, animales con accesorios,
flores, mariposas y transportes. No se ejecutó la batería completa.

## Resultado

- La imagen nueva pasa de **40 regiones y 10 × 4** a **20 composiciones y 5 × 4**.
- **Nueve variantes** conservan las veinte composiciones completas y sus testigos,
  sin incorporar elementos de un vecino ni modificar la imagen original.
- Las **15 imágenes anteriores** de la comparación mantienen exactamente sus
  resultados completos, no solo sus cantidades: candidatos, límites, cuadrículas,
  estados de incompletitud y motivos de revisión.
- **27 pruebas dirigidas pasan**: 5 del grupo nuevo, 2 de generalización, 1 de
  fuente incompleta y 19 de
  regresión. Los registros son `../compound-tests-final.txt`,
  `../compound-generalization.txt`, `../compound-partial-source.txt` y
  `../selected-regressions.txt`.
- Los casos sintéticos de 9, 12 y 18 grupos se recuperan sin cantidades prefijadas.
  Los de figuras grandes junto a una pequeña, y figuras junto a conjuntos pequeños
  con espaciado uniforme, conservan cortes separados.

`at-risk-comparison.json` compara cada imagen con la nueva ruta desactivada y
activada en el mismo código, sin editar la aplicación entre ejecuciones. Incluye
las dos versiones del alfabeto, números anteriores y nuevos, los dos nuevos
originales de animales y el de aceptación, cócteles, frases, dos flores, cuatro
transportes y un mosaico con mariposa y motivos independientes.

La comprobación específica de mariposas utiliza una escena sintética con flores
y mariposas independientes. No acredita una colección fotográfica exclusiva de
mariposas: su original limpio no está entre las entradas disponibles.

## Condiciones para proponer otra agrupación

La ruta se aplica a cuadrículas automáticas de al menos tres filas y suficiente
repetición horizontal. Se conserva la geometría de guías manuales, impresas,
de cámara o de referencia; se descartan propuestas con observaciones incompletas,
proyección explícita o soporte fuerte de separadores impresos.

Antes de reconstruir grupos, exige:

1. Columnas recurrentes de elementos altos y otras de múltiples piezas pequeñas,
   corroboradas por al menos dos lecturas de contraste.
2. Un periodo deducido de esas columnas. No se divide siempre la cantidad por dos
   ni se reconocen números mediante OCR.
3. Espacios internos menores que los espacios entre grupos en la mayoría de las
   comparaciones, además de una diferencia suficiente entre sus medianas.
4. Anclas de altura y disposición que acuerden una geometría común en varias
   lecturas; límites completos extraídos de otra lectura de menor contraste.
5. Conservación de al menos el 98 % del contenido de cada región anterior en un
   único nuevo propietario. La agrupación no puede justificar pérdidas de tinta.

La escena se analiza a una resolución acotada común para reducir diferencias de
segmentación por escala. La lectura jerárquica anterior comparte únicamente el
resolutor de posiciones y pertenencia; mantiene sus anclas de área existentes.

Para sombras, dos estimaciones espaciales de iluminación deben coincidir. Cuando
el fondo original no admite una máscara de tinta fiable, se exige contener las
cajas originales enteras mediante la misma prueba de conservación geométrica.
Se mantiene el aviso de compensación. No se alteran los píxeles mostrados,
la escala física ni los datos exportados de la fotografía.

## Interfaz y límites físicos

`numbers-compact-ui.json` y `numbers-compact-3in-ui.png` muestran **20 detecciones**,
**20 avisos de dibujo que excede el corte** y **ningún solapamiento** con los
cuadrados de tres pulgadas de la captura del usuario. Esto es esperado: el grupo
completo es más ancho que el tamaño seleccionado con la escala supuesta. No se
agrandan los cortes para simular que cabe todo.

La alineación se mantiene mediante una sola cuadrícula común. Las pruebas de la
interfaz verifican que confirmar la detección no mueve los cortes ni crea cortes
vacíos. Las guías confirmadas y las observaciones incompletas quedan protegidas.
La imagen recortada mantiene nueve observaciones incompletas excluidas incluso
al reducir el tamaño de corte; no se fuerza una agrupación del campo parcial.

Los resultados acreditan estas entradas y controles; no garantizan todas las
distribuciones posibles. Un campo sin alternancia fiable, con grupos verticales,
filas escasas o pertenencia ambigua conserva las rutas y la revisión anteriores.

## Reproducción

Desde la raíz, con el entorno virtual del proyecto y `QT_QPA_PLATFORM=offscreen`:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_compound_grid -v
.venv\Scripts\python.exe -m unittest tests.test_number_compositions tests.test_alphabet_compositions tests.test_composition_content tests.test_accessory_columns tests.test_accessory_ownership tests.test_irregular_shadows.IrregularShadowTests.test_original_shadowed_transport_preserves_distinct_complete_motifs tests.test_irregular_shadows.IrregularShadowTests.test_resized_shadowed_original_keeps_geometry_and_extent -v
```

`../../evaluate_at_risk.py` guarda la comparación limitada a las imágenes acordadas.
`../../render_compact_ui.py` genera el estado y la captura de la interfaz real.
