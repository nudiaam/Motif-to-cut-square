# Validación de telas en Lalikul 0.14.3

23 de noviembre de 2026. Validación local con originales recuperados, imágenes
de control y los paquetes de diagnóstico disponibles.

## Origen de la decisión anterior

La propuesta geométrica de `895062b` combina periodicidad de bordes con el
recuento y la distribución de los dibujos. Si los dibujos están completos y
separados, corroboran filas y columnas aunque el fondo sea continuo. Por
ejemplo, `transport_camera` conserva **19 composiciones en 5 × 4**, con una
jirafa que ocupa dos casillas. Forzar un dibujo por casilla la partiría.

En `c24e04c` se añadió una ruta que mide cambios de color y marcos repetidos
dentro del contorno de la tela. Está pensada para recuperar divisiones y
mantener juntas las partes de un dibujo. Funciona con el panel beige de
aspecto débil (24 en 6 × 4), los pájaros en perspectiva (21 en 7 × 3) y el
margen sin imprimir (24 en 6 × 4, sin una fila extra). El original de
rendimiento de Eugenio utiliza la lectura de contraste local (24 en 6 × 4).

El panel pastel nuevo tiene divisiones poco contrastadas y un contorno de
tela ambiguo. El método de contorno y croma carecía de evidencia suficiente.
Con la lectura adicional desactivada, reaparece una propuesta de **5 × 4**
y 12 detecciones fuera de sitio o duplicadas. La reproducción a 4″ obtiene
27 candidatos y 23 cortes visibles, como la captura. Al iniciar con 5″,
un corte más queda fuera de cama y se muestran 22. Al reducir esa misma foto a la
mitad, se acepta **4 × 2**: solo el 12,5 % de los centros respalda su fase,
pero seis de ocho fragmentos ocupaban celdas distintas y superaban la
condición conjunta de rechazo. El problema está en la evidencia usada para
contar y colocar las casillas, antes de dibujar o exportar los cuadrados.

La lectura incorporada en la 0.14.2 mide cambios sostenidos de luminancia y
color por franjas, exige acuerdo en ambos ejes y dos suavizados y busca
contenido en las secciones resultantes. En propuestas geométricas que ya
parecen fiables, solo puede sustituirlas si encuentra subdivisiones
corroboradas. La prueba con la lectura desactivada aísla esta decisión sin
atribuirle cambios anteriores del detector.

### Qué propuesta gana cuando están disponibles las dos lecturas

Con el flujo normal de Lalikul 0.14.3 y tamaño inicial de 4″, la foto nueva
da 24 cortes en 6 × 4. La cuadrícula de 5 × 4 reaparece al desactivar solo
la lectura adicional. A media resolución la propuesta de 4 × 2 queda
sustituida por 6 × 4, aunque la primera tenía alta confianza geométrica.

En una comprobación aparte se ejecutó la lectura nueva por sí sola sobre
las 66 entradas. Propuso una cuadrícula en nueve. En ocho coincidió con
las dimensiones elegidas por el flujo normal. En la reconstrucción de
grises (caso 62), propuso 6 × 3 pese a que son visibles las cuatro filas.
Lalikul conservó la lectura de cámara, con 24 cortes en 6 × 4. Es una
comprobación de por qué importa la prioridad entre las dos lecturas.
[Trazas del flujo normal](qa/release-0.14.3/selection-check.json) y
[propuestas de la lectura aislada](qa/release-0.14.3/direct-challenger.json).

La sesión de Chrome permitió recuperar dos imágenes generadas adicionales
desde **Mis imágenes**. El panel floral botánico y el de animales de colores
dan 24 cortes en 6 × 4, sin cruces ni solapes a 4″. Desactivar la lectura nueva
produce exactamente las mismas coordenadas en ambos. A 5″ aparecen cruces
y solapes en los dos controles. Sus huellas son distintas de las del corpus
anterior. [Resultados de las dos imágenes de la biblioteca](qa/release-0.14.3/biblioteca-resultados.json).

## Corpus y pruebas por familia

Se procesaron **66 entradas**. Son las 62 conservadas en el inventario del
proyecto, los dos paquetes 01 y 02 de noviembre, la foto nueva y su versión
a media resolución. Las familias corresponden a la dificultad visible y
pueden compartir rasgos. Los números remiten al [detalle por imagen](qa/release-0.14.3/casos.csv).

| Familia | Casos | Qué se comprueba y qué se observó |
|---|---|---|
| Pasteles y estampados contiguos de contraste débil | 02, 03, 07, 13, 14, 23, 37, 40, 52, 62–65 | La foto nueva y la reducida recuperan 24 casillas, sin cruces ni solapes a 4″. Otros pasteles usan las rutas previas. La foto 14 conserva 24 centros y tiene 10 cortes que cruzan y 7 que se solapan a 4″. Una casilla estrecha entre x ≈ 948 y 1120 px mide ≈ 3,8″ con la escala de la app. |
| Grises, foto original de Eugenio | 58 | 24 cortes en 6 × 4, 0 cruces a 4″ y 2 a 5″. La lectura adicional no interviene. Se conserva la medición de límites en píxeles originales aplicada en la 0.14.1. |
| Patchwork de fondos diferenciados | 04, 10–12, 18, 22, 24, 41, 43, 47, 49–51, 59, 60 | Se conservan recuentos y posiciones frente a la 0.13.4. Iconos variados, animales, vehículos y corazones ejercitan colores, costuras y centros descentrados. Un testigo de arte del caso 10 sigue pendiente. |
| Fondo continuo, motivos florales y trazos finos | 27, 36, 44–46, 61 | Se preservan la repetición de los dibujos y las posiciones del histórico. El caso 61 es una reconstrucción de flores. La segunda prueba de Eugenio requiere su foto original. |
| Transporte, fondo compartido y motivos que abarcan celdas | 15–17, 26, 38, 42 | La jirafa del 15 sigue siendo un dibujo. El 16 conserva 24 composiciones con divisiones discontinuas y el 17 mantiene 24 bajo sombras irregulares. |
| Composiciones con accesorios o partes separadas | 01, 05, 06, 19, 21, 29, 30, 32, 57 | Se conserva el recuento y la geometría histórica. El caso 01 mantiene 12 grupos y el 06 conserva 21. En el 57 quedan 11 de 12 grupos testigo con propietario único, igual que en 0.13.4. |
| Letras, números y frases | 28, 33–35, 48, 53–56 | Se conservan posiciones y cantidades. Se comprueba el grupo completo con sus elementos cuando hay puntos testigo independientes. |
| Fondo oscuro | 20, 25, 39 | Se conserva la rejilla en fondos oscuros. El caso 20 mantiene 15 cortes en 5 × 3. |
| Sombra sobre tejido claro | 09 | Se mantienen 24 cortes y los tres grupos testigo; la sombra diagonal no se toma por una división. |
| Fila incompleta o margen sin imprimir | 08, 31, 66 | Los parciales conservan los 18 cortes completos y el margen sin imprimir conserva 24. |

Se detectó con el tamaño inicial de 5″ de la auditoría histórica. Se midieron
los mismos cortes a 4″ y 5″, con sus cruces de casilla, solapes, contenido
fuera del contorno y geometría SVG. La reproducción puntual del panel nuevo
parte también de 4″, como la captura. Hay 16 referencias geométricas
aproximadas, incluida la fila parcial de la que solo están anotadas las
filas completas. Los puntos testigo prueban pertenencia de partes del dibujo,
sin medir el contorno completo. En el corpus hay material generado y cuatro
reconstrucciones de capturas, identificadas en el inventario histórico.

En **21 comparaciones emparejadas** solo cambió la salida en la foto nueva
y en su reducción. Los **62 casos históricos** conservaron el recuento y las
dimensiones de cuadrícula de la 0.13.4. En **61** se conservaron también los
rectángulos de 5″ con una tolerancia de 0,00001″. La diferencia geométrica
fue el original de Eugenio (58), donde la 0.14.1 refinó los límites del
estampado y aparecen dos avisos. Los **132 SVG** reprodujeron las coordenadas
de los cortes seleccionados. En 97 de 99 grupos testigo se mantuvo una
composición única. Los dos fallos ya aparecen en el registro histórico.
Pasaron 19 pruebas automatizadas de regresión, exportación y envío a Dashboard.

Los resultados incluyen geometría que exige revisión. A 5″, 37 entradas
tienen cruces detectados y 32 tienen solapes. A 4″, ambos aparecen solo en
la foto 14, mientras que 60 entradas conservan algún aviso de dibujo
recortado. El recuento de cuadrados, el encaje dentro de la casilla y la
cobertura de todo el dibujo son tres comprobaciones diferentes.

## Original y rendimiento de Eugenio

El paquete `Analisis_Lalikul` contiene los píxeles originales de 2340 × 1560,
la referencia y el informe. La huella de píxeles, referencia y ajustes
reproduce exactamente el identificador de la ejecución de **238,501 s**
del portátil. Aquel informe registró **28 detecciones en 7 × 4**. La copia
local actual detecta **24 en 6 × 4**, con los ajustes originales. El informe
del portátil atribuye 169,471 s a la selección del trazado y 62,768 s a la
comparación de apariencia. La transferencia a Epilog queda fuera de esa
medición.

Se repitieron tres procesos nuevos por versión, de forma secuencial y
alternando el orden, con afinidad a dos procesadores lógicos de la estación
Ryzen y dos hilos OpenCV. Se usó el mismo paquete en todas las repeticiones.

| Versión | Mediana del detector [mín., máx.] | Cortes | Memoria residente máxima |
|---|---:|---:|---:|
| 0.13.4 | 8,39 s [8,38–8,55] | 24 en las tres | 375 MiB |
| 0.14.3 | 8,72 s [8,61–9,27] | 24 en las tres | 375 MiB |

La mediana local subió un 4 %. Quedan por medir el tiempo de esta versión
en el portátil y la superposición del SVG con la tela en la máquina física.

## Evidencia disponible

- [Inventario de imágenes recuperadas de los chats](qa/image-audit/README.md).
  La primera prueba usó el archivo local de esas conversaciones. Las dos
  imágenes adicionales se recuperaron después desde el perfil de Chrome.
  Las fotos exactas de la segunda prueba de flores y de Cheeky Animals de
  Eugenio siguen sin identificar en el archivo disponible.
- [Detalle por imagen](qa/release-0.14.3/casos.csv), [reproducción con tamaño inicial de 4 pulgadas](qa/release-0.14.3/repro-4in.json)
  y [datos del ensayo de rendimiento](qa/release-0.14.3/performance/runs.json).
- [Script de reproducción del corpus](../tests/evaluate_fabric_corpus.py).
  Los manifiestos y resultados originales están en `docs/qa/release-0.14.3`.
