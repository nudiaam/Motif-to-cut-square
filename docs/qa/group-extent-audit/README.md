# Auditoría general de grupos, límites y centrado — 14/10/2026

Este documento conserva el análisis previo a la implementación. Las intervenciones de `experiments.py` se aplicaron temporalmente para aislar causas. La corrección instalada y sus comprobaciones se documentan en [fixed/README.md](fixed/README.md).

## Hallazgo principal

La aplicación confunde **distribución geométricamente completa** con **composiciones completas**. Hay rutas que pueden reemplazar o reconstruir grupos correctos usando evidencia parcial, mantener la misma cantidad de detecciones y desplazar los cortes. La recuperación jerárquica de números solo actúa cuando el resultado queda sin cuadrícula; no audita las cuadrículas aceptadas.

## Resultados reproducidos

Se inspeccionaron las imágenes limpias aportadas y se definieron puntos independientes sobre motivos, ingredientes, texto y adornos. Se corrigió durante la preparación un punto de control que había quedado en el espacio vacío bajo el tercer cóctel; todos los resultados guardados usan la lista corregida de `audit.py`.

| Entrada | Cantidad automática | Grupos cuyos testigos quedan juntos en un único límite | Cantidad de cuadrados actuales de 4 pulgadas que contienen los testigos |
|---|---:|---:|---:|
| Cócteles | 18 | 14 de 18 | 3 de 18 |
| Frases y dibujos | 16 | 7 de 16 | 0 de 16 |

Dos ejecuciones por entrada producen el mismo hash de resultado. El fallo es reproducible con ajustes predeterminados de detección. Las medidas físicas de corte se aplican después y no alteran este conteo.

## Cadena causal: cócteles

- Existe una propuesta de patrón con 18 regiones completas y una alternativa automática también de 6 × 3.
- La alternativa automática define separadores verticales que pueden pasar entre el vaso y sus ingredientes. Por ejemplo, el primer separador queda en x=263, junto a los ingredientes de la primera composición.
- El selector favorece esa alternativa: puntuación 0,6428 frente a 0,6000 del patrón completo. Ambas cuentan como ocupadas todas sus celdas. La comparación de contención conserva 83,33 % de las regiones del patrón, y la pérdida no alcanza el umbral actual para vetar la propuesta.
- Se vuelve a extraer contenido localmente en esas casillas. El resultado mantiene 18 detecciones pero pierde algunos extremos o elementos separados y puede incorporar fondo. La misma casilla es usada como evidencia para justificar su distribución.
- Más tarde aparece una propuesta de fondo compartido que conserva todos sus componentes de referencia. Tampoco se aplica: la ruta actual gana por 0,0354, la fase de las geometrías difiere y la ruta actual ya se considera completa.
- Los cortes terminan en una cuadrícula cuya primera posición es `(157,55; 236,50)` píxeles, frente a `(214,14; 269,06)` de la alternativa basada en los grupos completos. La diferencia afecta al centrado además de a los límites.

## Cadena causal: frases

- Antes de la recuperación de apariencia se dispone de 16 regiones. La lectura libre conserva los 16 conjuntos de testigos de frase y decoración.
- Se acepta una propuesta `chroma`, con confianza 0,996, centrada principalmente en los adornos de color. El negro aporta luminancia pero no una desviación cromática equivalente, de modo que esas regiones no certifican el texto.
- La geometría de 4 × 4 coloca la primera fila en y=262,22. La alternativa de fondo compartido que conserva el grupo completo la coloca en y=215,95: un desplazamiento de 46,27 píxeles, unas 1,08 pulgadas con el mapeo supuesto.
- El recuento y la correspondencia única son perfectos para los adornos. Por eso no se activa la comprobación adicional de pertenencia que se exige cuando hay duplicados, ni se busca necesariamente fondo compartido.
- La nueva extracción local pierde texto o incorpora texto de la fila siguiente. Un ejemplo termina con un límite de y=151 a y=376, atravesando el inicio de la siguiente frase. El conteo sigue siendo 16.

## Experimentos de aislamiento

| Intervención temporal | Cócteles: testigos conservados | Frases: testigos conservados |
|---|---:|---:|
| Ruta automática actual | 14/18 | 7/16 |
| Escala de grises | 18/18 | 13/16 |
| Solo comparación de fondo compartido | 14/18 | 16/16 |
| Conservar prioritariamente regiones completas del patrón | 18/18 | No aplicado |
| Evitar sustitución por la recuperación de apariencia | 14/18 | 15/16 |

Forzar una ruta demuestra dónde se pierde información, pero no es una política general segura. La diferencia entre intervenciones evidencia que el fallo depende de qué evidencia y qué ruta se privilegian, no de los nombres de las colecciones.

Se repitieron también tres controles anteriores con sus testigos independientes: alfabeto 24/24, números 20/20 y animales con accesorios 12/12. Pasan; la mejora anterior sigue siendo válida para esas entradas.

## Debilidades generales del funcionamiento

1. **Cierre prematuro por cantidad y alineación.** Una figura por casilla puede ser solamente la parte coloreada de una composición. La variable `complete` no certifica el conjunto del primer plano.
2. **Validación desigual entre rutas.** La recuperación de propiedad se activa en condiciones particulares de duplicación; otra propuesta con una correspondencia única puede aceptarse solo por ocupación y alineación. No todas pasan la misma prueba de conservación.
3. **El contenido puede degradarse al cambiar la geometría.** Una casilla sirve para volver a segmentar, sin garantizar que las regiones completas ya descubiertas sigan dentro de algún propietario único.
4. **Comparaciones parciales y umbrales permisivos.** Se comparan cajas de las regiones seleccionadas por cada canal. La tinta ignorada por ese canal puede no entrar en la comparación. Una pérdida del 16,67 % de las composiciones tampoco veta aquí la cuadrícula.
5. **Revisión de extensión centrada en continuidad.** `review_extents` detecta sobre todo componentes que continúan desde el interior hacia fuera. Texto, ingredientes o adornos completamente separados requieren una comprobación de pertenencia adicional. Algunos avisos sí existen en estas entradas; no equivalen a una recuperación del contenido omitido.
6. **Centros y límites tienen criterios distintos.** Los cortes conservan las posiciones de la cuadrícula. Si la fase se aprendió de vasos o adornos, no se recentra automáticamente sobre el conjunto completo. Mover cada cuadrado por separado rompería la alineación; hay que ajustar una geometría común compatible con los grupos.
7. **Recuperación jerárquica restringida a ausencia de cuadrícula.** Aquí una cuadrícula aceptada bloquea esa recuperación. Además, la prueba independiente jerárquica no obtiene una propuesta estable para las frases; cambiar solo esa condición tampoco resuelve todas las tipologías.

## Tamaño del corte: problema adicional

Con el mapeo supuesto de toda la fotografía de 1536 × 1024 a una cama de 36 × 24 pulgadas:

- Los límites completos recuperados por la ruta de patrón no caben en cuadrados de cuatro pulgadas en ninguno de los 18 cócteles; 17 caben dimensionalmente en cinco pulgadas. El mayor lado detectado es de 5,04 pulgadas.
- Para las frases recuperadas con fondo compartido, siete de los 16 grupos caben dimensionalmente en cuatro pulgadas y los 16 en cinco. El mayor lado es de 4,59 pulgadas.

Esto comprueba límites con una escala asumida, no medidas físicas reales. Que un grupo quepa dimensionalmente no garantiza que el cuadrado actual lo contenga: todavía hay que comprobar posición, solapamientos y área útil. Las dimensiones solicitadas al generador no garantizan que la imagen las respete.

## Corrección general recomendada

- Establecer un único criterio de conservación y propiedad para todas las rutas, incluidas las que ya ofrecen una cuadrícula confiada.
- Comparar geometría, fase y límites con primer plano fiable obtenido conjuntamente de luminancia y color, excluyendo fondo estampado, textura y marco.
- Mantener las regiones completas ya detectadas; una resegmentación debe demostrar que las conserva y que no incorpora elementos del grupo vecino.
- Evaluar en conjunto los intervalos de centros que permiten contener cada grupo con el tamaño seleccionado. Ajustar la fase común si es viable y comunicar cuándo falta tamaño o escala; no alterar automáticamente la medida.
- Permitir recuperar una cuadrícula con buen conteo pero mala conservación de contenido.
- Ampliar la regresión con texto monocromo y adornos de color, composiciones laterales, composiciones verticales, transparencia, detalles finos y diferentes proporciones de componente principal/accesorios. Cada prueba debe comprobar propietarios, límites y vecinos, además del conteo.

## Archivos

`baseline/*.json`: reproducción en memoria de la política previa (14/18 y 7/16); no corresponde a un checkout histórico. `reproduce_baseline.py` permite repetirla.
Los `*-auto.json`, `*-repeat.json` y `*-ui.json` de esta carpeta fueron regenerados durante una primera iteración de desarrollo y no deben usarse como evidencia de la versión previa.
`*-free.json`: lectura libre de la auditoría.
`fixed/`: resultados, variantes y cortes de la implementación actual. `audit.py` guarda allí sus nuevas ejecuciones por defecto.
`experiments.json`: intervenciones temporales.
`controls.json`: controles anteriores.
`size-analysis.json`: análisis dimensional con el mapeo supuesto.
`audit.py` y `experiments.py`: reproducción del análisis, sin modificaciones permanentes del detector.
