# Auditoría del alfabeto y la alineación — 13/10/2026

Se detienen los cambios funcionales a petición del usuario. Esta revisión solo
añade un script de diagnóstico y sus resultados. No modifica `app/`, no publica
una versión y no declara solucionados estos fallos.

## Reproducción exacta

Entrada limpia: `codex-clipboard-12d6d19e-0d2e-4ece-89ac-c03fa1b40cd2.png`,
1536×1024, 24 composiciones A–X en 6 columnas y 4 filas. Las otras dos entradas
son capturas de la interfaz, no entradas válidas para medir la detección.
Revisión ejecutada: `2026-10-13-sustained-panel-divisions`.

| Prueba | Resultado |
| --- | --- |
| Automático predeterminado | Rejilla 7×5; 34 regiones finales |
| Repetición idéntica | Misma huella del resultado, vuelve a fallar |
| Interfaz real, referencia configurada | 35 cuadrados: 34 regiones + 1 posición inferida; 35 solapamientos; 26 dibujos exceden el corte |
| Sin planificación adaptativa | Sigue escogiendo 7×5; 35 regiones |
| Guías manuales aproximadas 6×4, solo como control | 24 regiones, pero solo 8 de 24 parejas de puntos letra/dibujo quedan juntas en una caja |

La última prueba NO certifica guías exactas ni contornos completos. Sirve para
demostrar que obtener 24 regiones no resuelve la pertenencia de letras y dibujos.
En automático solo 7 parejas pasan esta comprobación mínima. Incluso una pareja
contenida no demuestra que la caja no invada otro motivo ni que incluya su silueta.
Los puntos de referencia están definidos en `audit.py`, independientemente de
las predicciones. JSON completos: `auto.json`, `repeat.json`, `no_adaptive.json`,
`manual_oracle.json` y `ui.json`.

## Causas confirmadas

1. **Una repetición de bordes se acepta como división entre composiciones.**
   La ruta de cámara propone 7×5 con confianza interna 0,883. Al compararla con
   las regiones iniciales, solo el 7,4 % está alineado según su propia métrica,
   y el apoyo de separadores es 0,225. `choose_grid` la acepta porque supera el
   umbral de confianza del productor y no cumple simultáneamente las dos
   condiciones de rechazo. No exige un mínimo absoluto de evidencia final.
   Esa confianza no es una probabilidad calibrada de acierto.

2. **La geometría errónea contribuye a confirmar su propio resultado.**
   Se segmenta por las 35 celdas propuestas y se vuelven a evaluar esos recortes.
   Ocupación y alineación mejoran al usar regiones obtenidas dentro de esa misma
   partición; no equivalen a corroboración independiente.
   La ruta de fondo compartido sí encuentra una alternativa 6×4, con acuerdo
   en 24 pasadas de análisis. Su comprobación local retiene solo el 53,3 % de
   las regiones de contraste según el criterio de cobertura del código. No
   supera el 90 % requerido. La comparación conserva 7×5 con puntuación 0,582
   frente a 0,550 y deja una advertencia. Forzar la alternativa sin reparar la
   agrupación ocultaría pérdida de contenido.

3. **No hay reconocimiento de la relación letra–ilustración.**
   La agrupación depende de color, contraste, proximidad y celdas. La segmentación
   local puede conservar el dibujo y omitir la letra separada; por ejemplo, en
   el control manual las cajas de pastel, tambor y globo no incluyen C, D y E,
   respectivamente, y esas cajas no reciben avisos de extensión. La revisión
   de extensión busca principalmente señales conectadas con el contenido ya
   detectado; eso no garantiza descubrir una letra separada que falta.
   No se ha aislado en esta auditoría la operación exacta que pierde cada letra.

4. **La interfaz materializa una rejilla dudosa.**
   `_sync_automatic_grid_cuts` añade el hueco restante como cuadrado inferido.
   Así aparecen los 35 de la captura. Hay avisos, pero la duda no impide presentar
   una distribución completa como propuesta de corte. La casilla inferida no es
   una figura encontrada en la imagen.

5. **La geometría de evaluación y la de colocación no coinciden plenamente.**
   `grid_evidence` asigna y puntúa mediante líneas X/Y; `LogicalLayout.position`
   coloca usando una transformación proyectiva cuando existe. `review_extents`
   también selecciona la celda con líneas X/Y. Esto requiere un contrato común
   para no evaluar una geometría y colocar con otra. No se atribuye todo el fallo
   de agrupación a esta discrepancia sin una prueba aislada.

## Por qué los cuadrados no quedan alineados con los ejes

En esta reproducción todos los 35 cuadrados están anclados a la misma rejilla,
no desplazados individualmente por el solucionador de solapamientos. La rejilla
se proyecta a la foto inclinada: dentro de la primera fila hay 48 px de diferencia
vertical; en la última columna, 93 px de diferencia horizontal entre extremos.
Los pasos entre columnas también varían por perspectiva.

Los cortes son rectángulos paralelos a los ejes. El mapeo físico actual
(`CoordinateMapper`) es una escala y traslación, sin calibración proyectiva de
la cama. Por tanto hay tres cosas diferentes: perspectiva de cámara, posición
de la tela y forma física del corte. La rectificación interna de una tela para
analizarla no calibra la cortadora. Alinear los centros a ojo sobre la pantalla
puede alejar los cortes del dibujo. Primero hay que definir la geometría física
y la política de alineación; después representar esa geometría correctamente.

## Navidad y las demás capturas

En la captura nueva de Navidad se ven 24 propuestas, 3 listas y 21 con problemas:
10 con solapamiento, 12 con dibujo fuera del corte y 8 con revisión de detalle.
Los grupos se superponen entre categorías. La separación estimada es
5,49×4,96 pulgadas frente a un corte de 5×5. Esto ya permite solapamientos
verticales aun con recuento correcto. No certifica una medida real de la tela:
depende de la colocación de la imagen. Sin el original limpio de esa Navidad
no se ha reproducido su ruta ni cuantificado su error de perspectiva.

Las capturas iniciales de Eugenio representan varias clases de fallo:

| Colecciones | Qué muestran las capturas | Qué no puede concluirse solo de ellas |
| --- | --- | --- |
| Alfabeto | Rejilla/centros cambiantes, composición separada | Que el segundo pase aprenda o arregle la causa |
| Navidad, perros | Separaciones equivocadas y/o solapamientos | Qué proporción se debe a geometría, tamaño o segmentación sin originales |
| Pájaros, flores | Regiones extra en márgenes | Que todo dibujo tenue sea fondo |
| Mariposas, gatos | Recuento plausible con muchos avisos | Que recuento correcto equivalga a contornos completos o cortes válidos |
| Corazones, vehículos, pájaros parciales | Filas incompletas en los bordes | Que una fila propuesta sea físicamente cortable |

Los límites de cama/fuente y los casos animales corregidos antes son problemas
distintos. Sus pruebas no demuestran que el alfabeto general esté resuelto.

## Por qué las verificaciones anteriores no fueron suficientes

- La corrección más reciente busca divisiones continuas de color para evitar
  subdividir paneles de animales. Este alfabeto tiene fondo continuo sin esas
  divisiones; el mecanismo no aborda su ambigüedad principal.
- El test del alfabeto anterior utiliza otra imagen, comprueba 24 candidatos y
  cuatro grupos de puntos, no las 24 composiciones completas. La reducción de
  tamaño comprueba principalmente el recuento.
- Las nueve variantes de animales proceden de un mismo original; no son nueve
  colecciones independientes. Los 21 controles sin cambios prueban ausencia de
  cambios en esas salidas, no que todas sus salidas sean correctas.
- El perfil global `profile_scene` registra estadísticas; no dirige por sí solo
  una clasificación semántica de colección. Sí existen decisiones adaptativas
  locales, pero no un intérprete que entienda letras, accesorios o escenas.
- Las pruebas unitarias validan los contratos actuales, que pueden aceptar una
  rejilla con advertencias. No sustituyen criterios de aceptación del usuario.

## Trabajo necesario antes de afirmar otra mejora general

1. Definir cada composición completa en los originales y separar tres criterios:
   pertenencia de sus partes, geometría de centros y viabilidad física del corte.
2. Comparar las propuestas con evidencia común obtenida antes de recortar en
   celdas; no completar automáticamente una rejilla contradictoria.
3. Resolver letras y accesorios separados conservando toda la evidencia; si la
   imagen no permite decidir, solicitar una corrección estructurada de la rejilla
   o pertenencia en vez de generar certeza aparente. OCR/visión semántica serían
   posibles apoyos a evaluar, no una solución ya implementada ni garantizada.
4. Unificar las coordenadas proyectivas usadas para evaluar, asignar y colocar;
   distinguir calibración de cámara, inclinación de tela y ejes físicos de corte.
5. Medir las 24 composiciones, contornos/partes, posiciones y exclusiones en
   originales independientes de varias colecciones. No aceptar solo el número
   final de cuadros ni que desaparezcan las alertas.

No se ha implementado ninguna de estas propuestas en esta auditoría.
