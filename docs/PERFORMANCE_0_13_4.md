# Rendimiento de Lalikul Cut Prep 0.13.4

Medición del 16 de noviembre de 2026. Se evalúa exactamente el código de la
entrega validada, sin modificar la detección para esta prueba.

## Equipo del cliente y antecedente

HP Laptop 15-db0xxx, AMD A6-9225 de **dos núcleos CPU a 2,60 GHz**, Radeon R4
integrada, 4 GB de RAM (3,89 utilizables, 1866 MHz), SSD Kingston de 240 GB y
Windows de 64 bits. La inscripción 2C+3G distingue CPU y gráfica.
Estas especificaciones ya estaban documentadas en la revisión del 1 de noviembre.

El informe original del cliente registró **238,501 s** de detector:
3,216 s de referencia/iluminación, 169,471 s de layout, 62,768 s de apariencia
y 3,047 s de revisión final. Runtime comunicado: Python 3.14.7, OpenCV 4.14.0,
NumPy 2.5.3. No contiene una medición de memoria máxima o paginación del portátil.

## Método y límites

Se ejecutan **42 procesos nuevos, de forma secuencial**, con tres repeticiones
por combinación, alternando el orden de las versiones. Se conservan originales,
referencias, ajustes y huellas de entrada. No se utiliza un perfilador durante
estas mediciones. Se comparan el código histórico `2379006`, la copia congelada
de 0.13.3 y la entrega congelada de 0.13.4. El histórico se prueba solo con el
original que produjo la espera de cuatro minutos; 0.13.3 y 0.13.4, con tres originales.

Estación: **AMD Ryzen 7 9800X3D, 16 procesadores lógicos, 61.41 GiB de RAM**.
Runtime: Python 3.12.13, OpenCV 4.14.0,
NumPy 2.5.2. La ejecución normal usa 16 hilos de OpenCV.
La limitada usa afinidad a dos procesadores lógicos y dos hilos de OpenCV;
las variables de hilos de OMP/BLAS se fijan a uno en ambos modos.

**No es una emulación del AMD A6 ni de un sistema completo con 4 GB de RAM.**
No se igualan rendimiento por instrucción, cachés, frecuencia, temperatura,
memoria disponible para Windows, paginación ni velocidad del SSD. No se aplica
un límite de RAM y no se deduce que el portátil vaya a tardar los segundos de
esta estación. Tampoco se ha reservado una máquina dedicada: los rangos muestran
variación de carga y tres repeticiones no establecen significación estadística.

El tiempo del detector excluye carga inicial de imagen e instalación. Se mide
por separado la aplicación de su resultado a la interfaz Qt. La memoria es el
máximo del proceso completo, incluida Qt y escritura de diagnóstico/superposición;
no es el uso total de Windows ni la suma de todos los programas del cliente.
Los MiB de las tablas corresponden al conjunto residente máximo; el compromiso
privado máximo también se conserva en los datos.

## Estación completa: 16 procesadores lógicos

| Imagen | Versión | Detector: mediana [mín.–máx.] | Aplicar a UI | Memoria máxima del proceso | Cortes activos |
|---|---|---:|---:|---:|---:|
| Original del cliente, 2340 × 1560 | historic | 11.78 s [11.50–15.78] | 5.1 ms | 601 MiB | 24 |
| Original del cliente, 2340 × 1560 | 0.13.3 | 7.74 s [7.37–11.25] | 7.4 ms | 350 MiB | 24 |
| Original del cliente, 2340 × 1560 | 0.13.4 | 10.00 s [7.50–10.46] | 8.0 ms | 350 MiB | 24 |
| 01 — fondos pastel y franjas blancas | 0.13.3 | 3.81 s [3.74–4.02] | 7.1 ms | 229 MiB | 24 |
| 01 — fondos pastel y franjas blancas | 0.13.4 | 3.82 s [3.81–5.70] | 7.9 ms | 228 MiB | 24 |
| 02 — marcos y margen inferior vacío | 0.13.3 | 5.80 s [5.36–10.01] | 12.2 ms | 228 MiB | 30 |
| 02 — marcos y margen inferior vacío | 0.13.4 | 6.85 s [4.91–7.59] | 7.4 ms | 228 MiB | 24 |

## Afinidad limitada a dos procesadores lógicos

| Imagen | Versión | Detector: mediana [mín.–máx.] | Aplicar a UI | Memoria máxima del proceso | Cortes activos |
|---|---|---:|---:|---:|---:|
| Original del cliente, 2340 × 1560 | historic | 27.81 s [24.00–29.84] | 4.4 ms | 413 MiB | 24 |
| Original del cliente, 2340 × 1560 | 0.13.3 | 9.07 s [8.28–9.20] | 7.7 ms | 287 MiB | 24 |
| Original del cliente, 2340 × 1560 | 0.13.4 | 8.53 s [8.36–8.79] | 8.6 ms | 287 MiB | 24 |
| 01 — fondos pastel y franjas blancas | 0.13.3 | 3.77 s [3.74–5.79] | 7.2 ms | 226 MiB | 24 |
| 01 — fondos pastel y franjas blancas | 0.13.4 | 3.82 s [3.81–6.99] | 7.7 ms | 226 MiB | 24 |
| 02 — marcos y margen inferior vacío | 0.13.3 | 5.54 s [5.52–6.88] | 8.3 ms | 226 MiB | 30 |
| 02 — marcos y margen inferior vacío | 0.13.4 | 5.16 s [5.12–10.50] | 7.9 ms | 227 MiB | 24 |

## Interpretación

En el original histórico y con dos procesadores lógicos, el tiempo pasa de
**27.81 a 8.53 segundos**, una reducción local del **69.3 %**.
Las comparaciones con 0.13.3 deben leerse por caso y por modo: no se afirma que
0.13.4 sea más rápida en todas las entradas. La lectura adicional de divisiones
originales tiene un coste; en la estación completa algunas medianas aumentan.
Se mantienen los rangos para no ocultar la variación observada.

El 02 pasa de 30 a 24 cortes porque elimina la fila falsa, no porque se haya
retirado contenido válido para acelerar el análisis. Las pruebas funcionales y
las comparaciones geométricas se registran aparte en la ficha de versión.
Estas medidas no justifican omitir evidencia o debilitar las comprobaciones.

**Tiempo en el portátil con 0.13.4: todavía no medido.** Como cálculo orientativo,
si toda la proporción de mejora de la prueba de dos procesadores se trasladase
sin cambios al A6, 238,501 × 8.5301 / 27.8115 daría **unos 73 segundos**.
Esa hipótesis no está demostrada: es una extrapolación aritmética, no una
simulación ni un tiempo que se pueda prometer al cliente. No se publica un
intervalo de garantía inventado a partir de ella.

Para confirmar el tiempo real: en el portátil, cerrar la versión anterior,
abrir 0.13.4, repetir tres veces el mismo original con los mismos ajustes y
guardar el informe de detección de cada ejecución. Sus `timings_seconds` permiten
comparar medianas del detector con los 238,501 s originales. El tiempo visible
desde el clic hasta que aparecen los cortes debe anotarse por separado.

## Evidencia y publicación

[Datos resumidos, entornos, huellas y repeticiones](PERFORMANCE_0_13_4.json).
Los registros completos, script de medida y originales permanecen en el archivo
privado `docs/qa/release-0.13.4/performance/`. No se publican imágenes del cliente,
identificadores de su dispositivo ni paquetes de diagnóstico.
La [ficha de versión](RELEASE_0_13_4.md) documenta las 339 pruebas funcionales,
62 entradas anteriores, ocho variantes de los paquetes nuevos y el SVG.
