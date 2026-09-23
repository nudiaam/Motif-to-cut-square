# Grid impreso descartado por una primera detección fragmentada

Original aportado el 23 de septiembre, preservado sin superposiciones en
`tests/fixtures/acceptance/mixed_icons_6x4.png`. Contiene 24 motivos, seis columnas
y cuatro filas. El oscurecimiento de la captura de interfaz corresponde a la
previsualización de cortes; no se utiliza esa captura para detectar ni medir sombras.

## Diagnóstico reproducido

El código anterior a la última coordinación y el código de esa coordinación
producen 13 candidatos sin grid en este original (`before.json`). Existe una
propuesta 6×4, de confianza interna 0,929 y soporte de separaciones 0,999. Se
descarta porque la segmentación global solo aporta 13 fragmentos, con alineación
0,077 y asignación única 0,692. La protección contra grids que agrupan dibujos
distintos trata esos fragmentos como si fueran dibujos completos.

Una ablación que desactiva exclusivamente ese veto devuelve 24 candidatos y
6×4 (`veto-probe.json`). Aísla causalmente la regla, aunque no equivale a ejecutar
un instalador histórico completo. El fallo no apareció por la última coordinación;
esa coordinación tampoco lo había solucionado.

La diferencia de esta tela respecto al patchwork de 20 animales no es su número
de casillas: el contraste del perímetro blanco contra el exterior negro domina
la medida de bordes de la nueva vía de separaciones. Sus picos internos no superan
el umbral global y esa vía no produce una alternativa. A la vez, los motivos y
los estampados de fondo fragmentan la segmentación global. La ruta del panel
fotografiado sí encuentra la distribución, pero el veto la bloqueaba.

## Corrección

Se conserva la protección contra agrupaciones de dibujos. Antes de rechazar una
propuesta de panel por fragmentos mal alineados, se comprueba si:

- Las separaciones tienen apoyo fuerte en los píxeles (soporte ≥0,75 y confianza
  de la propuesta ≥0,85).
- La primera detección es escasa respecto a las posiciones propuestas (<85 %),
  en vez de aportar un conjunto mayor de dibujos que se pretende agrupar.
- El análisis local respalda ocupación ≥85 %, alineación ≥65 % y correspondencia
  única ≥85 %. Se utiliza el mismo análisis local existente y se guarda el resultado
  para no repetirlo al elegir la propuesta.

Esa evidencia vuelve al coordinador común, donde también se mantienen las
contradicciones con composiciones independientes. No se introduce un número de
filas/columnas, nombre de colección o coordenadas de esta imagen en producción.

La alineación regular funciona como una preferencia estructural respaldada por
píxeles: en el original, las 24 regiones locales tienen alineación y asignación
única de 1,0. La primera detección fragmentada no puede anular esa evidencia.
No se modifica el manejo de composiciones que abarcan dos posiciones ni se
certifica una casilla vacía como dibujo.

## Resultados y límites

- Original: 24 candidatos, grid 6×4; también a media resolución y con 60 píxeles
  de margen exterior añadido. Se conserva la imagen de entrada.
- Los 18 controles de la actualización anterior conservan exactamente cajas y
  centros, además del recuento (`previous-controls.json`).
- La batería completa pasa: **196 pruebas**, registradas en `unittest.txt`.
- La prueba nueva comprueba 24 puntos de cuerpo inspeccionados en el original y
  un propietario distinto para cada uno. Otro control impide usar la revisión
  local para justificar un grid que agrupa 24 observaciones en seis posiciones.
- La interfaz genera 24 cortes sin posiciones inferidas (`ui.json`, `ui.png`).
  Con el tamaño fijo de 5 pulgadas hay solapes: la separación vertical estimada
  es ligeramente inferior a 5 pulgadas al colocar esta foto en 36×24 pulgadas.
  No se altera el tamaño del usuario para ocultarlos.
- Se conservan nueve avisos de extensión. Algunas cajas incluyen estampado de
  fondo y otras omiten tinta tenue (por ejemplo, pétalos blancos). El recuento
  y la alineación recuperados no prueban siluetas perfectas.

Reproducción:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_disputed_grid -v
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m tests.evaluate_disputed_grid
.venv/Scripts/python.exe -m tests.evaluate_disputed_grid --ui
```

`detector-before.py` y `seam-grid-before.py` son copias de diagnóstico de la
versión al comienzo de esta corrección; no son módulos activos de la aplicación.
