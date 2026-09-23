# Coordinación de evidencia de dibujos, grid y apariencia

23 de septiembre de 2026. Revisión `2026-09-23-joint-evidence`.

## Qué cambia

La primera detección deja de ser la única evidencia con la que se puntúan todas
las propuestas. `choose_grid` recibe las regiones de cada productor. Una ruta de
composiciones estables puede aportar evidencia común a las demás: se registran
ocupación, alineación, regiones exteriores, asignaciones múltiples y cuánto
contenido de sus cajas conserva cada alternativa. Estas medidas comparan
hipótesis; no recortan dibujos ni sustituyen la revisión de extensión.

`seam_grid.py` propone divisiones por cambios de color sostenidos a través de la
imagen, con acuerdo en dos escalas. La separación y el origen se estiman de los
picos observados, sin fijar un número de filas/columnas ni repartir el encuadre.
Los límites exteriores extrapolados también necesitan apoyo de píxeles. El
coordinador confronta esa propuesta con el análisis local y las otras rutas.

La recuperación por contraste ya no sustituye un resultado solo por tener un
grid distinto. Pasa por el mismo comparador y conserva sus regiones de apoyo.
En escenas sin una interpretación suficientemente respaldada y sin consenso
de contraste oscuro, se prueban contraste claro y excursiones cromáticas locales.
Esto no clasifica la tela por su brillo medio. Una prueba con tinta y fondo
oscuros de luminancia similar comprueba el canal cromático.

Cuando hay acuerdo geométrico pero una máscara provisional elimina contenido
respaldado, se reanalizan únicamente las casillas sin extracción conservada, sobre
el original. Cuando cambia la interpretación global de la distribución, se
analizan sus nuevas zonas. No hay una iteración ilimitada ni entrenamiento.

Se mantienen la agrupación de composiciones, revisión de extensión, tratamiento
de dibujos que atraviesan casillas, tamaño físico del corte, revisión de solapes,
colores e interfaz existentes. No se han incorporado modelos, red, GPU ni
dependencias nuevas.

## Originales recientes

| Original | Detector anterior | Detector actualizado | Distribución actual |
| --- | ---: | ---: | --- |
| Animales, fondos diferentes | 4 | 20 | 5×4 |
| Animales pastel | 19 (20 cortes en interfaz) | 16 | 4×4 |
| Espacio oscuro | 1 | 15 | 3×5 |
| Animales con adornos | 14 | 12 | 4×3 |
| Figuras finas | 21 | 21 | 7×3 |
| Jirafa que ocupa dos posiciones | 19 | 19 | 5×4, una composición ocupa dos posiciones |

Los recuentos no certifican siluetas completas. `test_joint_coordinator.py` añade
puntos de control independientes en los cuatro primeros originales, comprueba
que cada uno pertenece a una detección distinta, verifica cuatro asociaciones
animal-accesorio y conserva pruebas de píxeles originales, fondo vacío/rayado,
cromática a luminancia similar y estabilidad del grid con resolución y márgenes.

## Verificación

`unittest.txt` registra la batería completa: **194 pruebas correctas**. Incluye
los controles anteriores de sombras en tres colecciones, resolución, puntos de
extremos de vehículos, dibujos entre casillas, exportación y flujo de interfaz.
Los fallos de las primeras iteraciones se conservan en archivos separados; no son
el resultado final.

`comparison.json` compara el código anterior preservado con el actual, en el
mismo proceso, con los mismos originales y ajustes. Incluye recuentos, geometría,
tiempos, huellas del código y de las imágenes. Los tres archivos Python en esta
carpeta son las versiones anteriores utilizadas exclusivamente por ese evaluador.
No son archivos activos de la aplicación.

`ui-results.json` y las capturas `*-ui.png` comprueban el flujo de detección real
en la interfaz con cuadrados de 5 pulgadas, además del detector aislado.

La comparación de 18 originales conserva exactamente cajas y centros en las
once colecciones anteriores y el transporte con sombras. También conserva los
dos originales recientes que ya daban 19 y 21 composiciones. Cambian los cuatro
originales con fallos reproducidos de 4→20, 19→16, 1→15 y 14→12.

Mediana de detección completa en este equipo: 3,25 s antes y 3,42 s después.
Patchwork nuevo: 2,79 s; pastel nuevo: 1,34 s; espacio oscuro: 2,49 s; grupos:
3,49 s. Pico del proceso evaluador: 312,1 MiB, incluyendo ambas versiones;
no representa memoria añadida por el coordinador ni una medición universal.

Con el ajuste de 5 pulgadas, la interfaz muestra 20 cortes de patchwork sin
solapes (15 con avisos), 16 del pastel sin solapes (2 con avisos) y 15 del espacio
con solapes. En el espacio, las cinco filas no tienen separación física suficiente
para cuadrados de 5 pulgadas en esta colocación. En el patchwork, las cajas
contaminadas por fondo contribuyen a los avisos; no se han ocultado.

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m tests.evaluate_joint_coordinator
.venv/Scripts/python.exe -m tests.evaluate_joint_coordinator --ui
```

## Límites observados

- Las cajas del patchwork pueden incluir parte del estampado de fondo. Algunas
  cajas del panel espacial incluyen estrellas cercanas. Se conserva la revisión
  de extensión; recuperar el recuento no demuestra segmentación perfecta.
- El tamaño físico sigue siendo independiente: si 5 pulgadas superan la
  separación disponible o la figura no cabe, deben aparecer avisos.
- Un control adicional de casillas de colores completamente lisas, sin dibujos,
  todavía produce falsas detecciones en ambas versiones (18). Las divisiones de
  fondo por sí solas no demuestran que haya figuras. Este fallo previo queda
  documentado; no se presenta esta versión como detector universal.
- La textura como señal alternativa de figura/fondo no tiene aquí un modelo
  nuevo específico. Hay mediciones existentes de detalle y paleta local, y el
  canal cromático añadido; no se ha implementado todo el diseño experimental.
- Las regiones de contraste sirven de evidencia geométrica; sus cajas no se
  usan como siluetas finales. Los porcentajes internos no son probabilidades.
- Las colecciones usadas durante el desarrollo no constituyen una evaluación
  independiente de colecciones desconocidas.

[Diez pruebas nuevas con telas y criterios de revisión](10-pruebas-telas.md).
