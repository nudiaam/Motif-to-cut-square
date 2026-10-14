# Auditoría de números y grupos compactos — 14/10/2026

La corrección posterior está implementada y documentada en [fixed/README.md](fixed/README.md).
Este documento conserva la auditoría inicial. El `results.json` de esta carpeta
incluye una iteración de desarrollo; la comparación anterior/actual definitiva
está en `fixed/at-risk-comparison.json` y las pruebas finales en los registros
citados en el informe de implementación.

Revisión de la nueva imagen limpia aportada. Esta auditoría no modifica código de
la aplicación. Las intervenciones de prueba se ejecutan solo en memoria.

## Reproducción

| Escala de entrada | Detecciones | Cuadrícula elegida | Grupos completos según testigos |
|---|---:|---|---:|
| 50 % | 45 | 10 × 4, patrón | 0/20 |
| 100 % | 40 | 10 × 4, patrón | 1/20 |
| 150 % | 41 | 10 × 4, patrón | 1/20 |

`results.json` contiene trazas, resultados y propietarios de los puntos de
control. Las cantidades variables incluyen fragmentos adicionales; la geometría
incorrecta de diez columnas se mantiene en las tres resoluciones.

## Causa

1. La lectura inicial ya obtiene 40 regiones y una cuadrícula de diez columnas.
   El número y el conjunto de objetos ocupan columnas alternas. La lectura de
   luminancia y la lectura de fondo compartido proponen también diez columnas.
   Ninguna aporta en esta entrada un grupo completo número/objetos que pueda
   contradecir esa partición.
2. La cuadrícula actual parece completa por criterios geométricos: ocupación
   97,5 %, alineación 92,5 % y asignación única 97,5 %. Su puntuación es 0,59076,
   frente a 0,57690 de luminancia y 0,56743 de fondo compartido. Por eso se mantiene.
   Conservar todas las regiones ya detectadas no basta para advertir que deben
   unirse de dos en dos en esta composición.
3. La recuperación jerárquica solo se invoca automáticamente si no se recuperó
   apariencia y no existe una cuadrícula. Aquí existe una de patrón, por lo que
   esa ruta se omite. Además, probarla directamente tampoco produce una propuesta:
   hay un segundo problema que no se arregla cambiando únicamente esa condición.
4. La recuperación busca anclas por cuantiles del área de componentes. En la
   imagen anterior los objetos pequeños daban 168, 193 y 211 componentes en sus
   tres lecturas; aquí dan 56, 64 y 72. Las sombras y la proximidad conectan objetos
   en regiones grandes. Estas regiones compiten en área con los números.
   Las lecturas de anclas no reúnen ocupación, confianza y repetición consistentes.

Los resultados de cada lectura están en `new-hierarchy-readings.json` y
`previous-hierarchy-readings.json`; `component-scales.json` registra cajas y áreas.
La fuente anterior sigue recuperando 20 grupos con el código actual.

## Experimentos que no constituyen una solución

- Ampliar los cuantiles de área desde 0,45 a 0,91: la propuesta continúa siendo
  nula en esta entrada; la anterior sigue recuperando veinte grupos.
- Ampliar también las lecturas de contraste de 35–55 a 35–95: continúa siendo nula.
- Unir las columnas pares de la cuadrícula como guías de prueba: veinte resultados,
  pero solo 18/20 grupos conservan todos los testigos. Unirlas con la otra fase
  produce dieciséis resultados y 0/20 grupos completos. Dividir siempre la cantidad
  de columnas por dos no es una corrección general segura.

La implementación necesita comparar niveles de repetición aun con una cuadrícula
aceptada, evaluar anclas con evidencia de forma/altura y partes internas además
del área, y comprobar la fase y los límites de todos los grupos. Los controles
de figuras independientes deben impedir unir dos dibujos que sí sean cortes
distintos. No debe fijarse por código una cantidad de veinte ni depender del OCR.

## Tamaño de corte

La captura configura cuadrados de tres pulgadas. La cantidad de detecciones se
decide antes de aplicar esa medida. Un grupo ancho puede no caber en tres pulgadas
incluso después de corregir su pertenencia. Cambiar el tamaño no arregla las diez
columnas detectadas; escala/calibración y contención se deben revisar por separado.

## Límite de la validación anterior

Las 238 pruebas anteriores pasaban, incluida otra imagen de números con nueve
variantes. No cubrían esta estructura de objetos compactos conectados por sombras.
La nueva reproducción invalida cualquier afirmación de cobertura universal de la
tipología: los datos anteriores prueban sus entradas, no todas las telas posibles.
