# Evaluación de paneles rectos — 21-09-2026

Se generaron tres entradas nuevas con filas y columnas rectas, sin la perspectiva
introducida en los casos anteriores. Se mantuvo el detector existente sin ajustar
sus reglas a estas imágenes. Las tres tienen 24 composiciones y se procesaron
con los ajustes predeterminados. También se ejecutó la detección desde la interfaz
con cuadrados de 5 pulgadas y se inspeccionaron las capturas.

| Panel | Candidatos | Casillas con detección | Duplicados | Avisos automáticos de recorte | Solapamientos |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pastel | 25 | 24 de 24 | 1 | 3 | 5 |
| Perros | 24 | 24 de 24 | 0 | 0 | 0 |
| Corazones | 24 | 24 de 24 | 0 | 2 | 0 |

Los avisos cuentan cortes, no parejas. Un mismo corte puede tener varios problemas.
Ninguno de estos resultados incluye cortes añadidos por inferencia de huecos.
La ejecución completa en la interfaz tardó aproximadamente 1,20 / 2,87 / 1,20 s
respectivamente en este equipo; no es una medición de rendimiento del cliente.

## Fallos observados

**Pastel:** la mariposa junto al gato, en la fila 3 y columna 5, se interpreta como
un motivo independiente. Los candidatos 13 y 17 ocupan esa misma casilla. Sus
cajas son `(1167, 579, 31, 38)` y `(1022, 580, 142, 155)`. No falta ninguna casilla:
el fallo es la separación del accesorio respecto a la composición principal.
La interfaz avisa de un duplicado, pero sigue creando su cuadrado.

**Perros:** el recuento es correcto y la aplicación indica 24 listos. Sin embargo,
en la captura se ve que algunos cuadrados de la primera fila dejan parte de las
patas fuera. Es una limitación del aviso: solo comprueba la caja que el detector
ha encontrado, no las partes que haya omitido. La cuadrícula elegida por el
detector usa el contorno de la tela (`camera`); por ejemplo, su primera división
horizontal está aproximadamente en y=270 frente a la división impresa anotada
en y=282. Ese desplazamiento y el recorte local pueden explicar la pérdida de
extremos. Esta explicación de la causa requiere una prueba específica posterior.

**Corazones:** detecta una composición por casilla, sin duplicados. Marca dos
cortes con aviso de recorte. La inspección muestra que los límites detectados
pueden incluir motivos pequeños del estampado de fondo, así que estos avisos no
equivalen por sí solos a que la silueta principal del corazón quede cortada.

Estos casos confirman que siguen existiendo problemas de agrupación y de límites
de las figuras con la tela recta. No permiten cuantificar el efecto de la perspectiva
porque son diseños nuevos, no pares de una misma escena antes y después de rectificar.
Tampoco establecen precisión física: las imágenes generadas no tienen una escala
de fabricación conocida.

## Evidencias y reproducción

- [Entradas y prompts](../../../tests/fixtures/generated/straight/README.md).
- [Evaluación reproducible del detector](evaluation.json), con hashes de los PNG,
  ajustes, cajas y cobertura de casillas. Falla pastel por el duplicado.
- [Captura pastel](pastel_6x4-ui.png) y [datos de la ejecución](pastel_6x4.json).
- [Captura perros](dogs_6x4-ui.png) y [datos de la ejecución](dogs_6x4.json).
- [Captura corazones](hearts_6x4-ui.png) y [datos de la ejecución](hearts_6x4.json).

El siguiente ajuste debería distinguir accesorios de motivos independientes y
comprobar las partes del dibujo cerca de los límites de las casillas antes de
considerar un corte listo. No se modificó la aplicación durante estas pruebas.
