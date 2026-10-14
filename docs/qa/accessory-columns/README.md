# Columnas repetidas de animales y accesorios

13 de octubre de 2026. Revisión `2026-10-13-sustained-panel-divisions`.
Cambios locales, sin publicación.

## Fallo reproducido

El segundo original contiene 12 paneles, cada uno con un animal y accesorios
alineados a su derecha. El detector de cámara interpretaba la repetición de
bordes verticales como 8 columnas, generando 24 grupos. La recuperación por
contraste no encontraba otra cuadrícula y la corrección anterior de propiedad
no tenía una hipótesis alternativa que comprobar.

## Corrección general

Se exige evidencia de separadores sostenidos sobre la mayor parte de cada eje,
con coincidencia de número de filas/columnas entre color y Lab, al menos dos
escalas por vista y coincidencia de posición en dos escalas de color. Solo se
sustituye la cuadrícula de cámara cuando esta subdivide regularmente la nueva
partición corroborada. No se utiliza el nombre de la colección ni un recuento
fijo de 12 figuras. Se mantienen las comprobaciones posteriores de propiedad.

La sombra diagonal reveló un segundo fallo: la compensación de iluminación por
filas hacía desaparecer la cuadrícula, aunque los separadores aún eran visibles
en el original. Cuando ocurre eso, se recupera únicamente una propuesta con
separadores corroborados en los píxeles originales. No se modifican los píxeles
mostrados, la calibración ni las dimensiones físicas de corte.

## Pruebas

| Entrada | Antes | Después | Composiciones con animal y dos accesorios |
| --- | ---: | ---: | ---: |
| Original | 24 | 12 | 12 |
| Tamaño 75 % | 24 | 12 | 12 |
| Tamaño 50 % | 24 | 12 | 12 |
| Menor iluminación | 24 | 12 | 12 |
| Sombra diagonal | 37 | 12 | 12 |
| Dominante cálida | 24 | 12 | 12 |
| Rotación | 24 | 12 | 12 |
| Perspectiva | 24 | 12 | 12 |
| Margen añadido | 24 | 12 | 12 |

Cada caso verifica 36 puntos seleccionados sobre el original: animal y dos
accesorios de cada composición, con un único propietario y 12 propietarios
diferentes. Los puntos se transforman con la imagen. Para las reducciones se
escalan también los parámetros expresados en píxeles. Estas pruebas no equivalen
a nueve colecciones independientes ni certifican todas las siluetas píxel a píxel.

- [Diagnóstico inicial](before.json), [variaciones antes](variants-before.json)
  y [variaciones finales](variants-final.json).
- [21 controles anteriores](regression-comparison.json): mismas cajas y centros.
- [Interfaz real: original](original-ui.png) y [sombra](diagonal_shadow-ui.png).
  Se ejecutó Detect en segundo plano con sus ajustes predeterminados y referencia
  de cama cargada. Ambas entradas devuelven 12 grupos, sin exclusiones.
- [Batería de 224 pruebas](unittest.txt): 223 correctas y un error en un doble de
  prueba antiguo que no incluía el nuevo dato de evidencia de cámara. Se sustituyó
  por el objeto real `CameraPanel`, manteniendo las mismas comprobaciones; las dos
  pruebas del módulo se repitieron y pasaron en
  [verificación posterior](final-disputed-grid-tests.txt). No quedan fallos abiertos
  de esa ejecución.

## Qué sigue siendo una advertencia

Con la imagen colocada a 36×24 pulgadas, los cuadrados de 5 pulgadas son menores
que estas composiciones. Por ello la interfaz mantiene los avisos de dibujo
mayor que el corte. Recuperar los grupos no autoriza a reducir sus dibujos ni a
cambiar la medida de corte. Se mantienen también los avisos de detalle ambiguo.

El original está en
`tests/fixtures/customer_20261012/animals_accessories_columns_4x3.png`, copiado
sin modificaciones. La captura con superposiciones no se utiliza como entrada.
Las variantes se calculan de forma determinista y en memoria mediante
`tests/evaluate_accessory_columns.py`.
