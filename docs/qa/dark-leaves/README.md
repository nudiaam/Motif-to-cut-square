# Hojas oscuras sobre tela oscura — 23 septiembre 2026

## Diagnóstico reproducido

El original contiene 15 composiciones en 5 columnas y 3 filas. Antes del cambio,
el programa devolvía cuatro regiones en una cuadrícula de 2 × 2 (`before.json`).
La diferencia relevante es el contraste débil y extendido: hay grandes superficies
de tinta próximas al color del fondo, sin contornos negros fuertes ni separadores
de casillas. La textura y las nervaduras no representan por sí solas toda la hoja.

Las comparaciones locales de luminosidad y color sustraían parte del propio
interior de las hojas. Las tres alternativas anteriores —oscura, clara y
cromática— no daban una geometría estable. Además, llenar las cuatro casillas
provisionales parecía confirmar una detección completa: una partición puede
llenarse sin que exista evidencia independiente de que sea la partición correcta.

## Cambio

- Cuando las alternativas anteriores no proporcionan geometría y la partición no
  está respaldada por observaciones independientes, se busca un color de fondo
  dominante que reaparezca en distintas zonas de la fotografía.
- La distancia en Lab se normaliza por la variación medida del fondo. No se
  presupone que el dibujo sea más claro ni más oscuro. No hay una regla por
  colección, número de hojas, nombre del archivo o cuadrícula esperada.
- Las regiones deben coincidir en alineación y separación en distintas escalas
  y umbrales. Su geometría y evidencia propia compiten en el coordinador existente.
- El análisis local recibe ese modelo del fondo y vuelve a examinar los píxeles
  originales con contexto. Conserva evidencia de color conectada al dibujo para
  evitar que la segmentación absorba tallos finos, especialmente al reducir la foto.
- Se conservan los criterios anteriores para las rutas de contraste claro y
  cromático. Una prueba intermedia desplazó la colección floral; se acotó la
  activación antes de aceptar el cambio final.

No se añaden modelos, descargas, servicios remotos ni dependencias. La geometría
usa una imagen con lado mayor de 960 píxeles; la comprobación de extensión usa
los píxeles originales. Los tiempos del registro se midieron mientras corrían
otras pruebas y no son un benchmark del equipo del usuario.

## Verificación

`witness-variants.json` registra el original, media resolución, resolución ×1,5
y un margen exterior adicional: 15 composiciones, 5 × 3 y 45 puntos de control
contenidos en sus respectivos dibujos. Cada grupo de tres puntos corresponde
a un único propietario distinto; incluyen tallos y extremos de hojas.
La matriz original no se modifica durante la detección.

`previous-controls.json` compara las cajas y centros con los 18 controles de la
actualización previa. `mixed-icons-control.json` comprueba además los 24 iconos
con fondos variados contra el detector guardado antes de este cambio.
Los 19 controles conservan exactamente cajas y centros. La pasada final de las
199 pruebas automáticas termina sin fallos (`unittest-final.txt`).

`test_shared_background.py` añade pruebas del original a tres resoluciones,
figuras de igual luminosidad con fondos claros y oscuros, y negativos de tela
uniforme, ruido fino y franjas. Los paneles sintéticos positivos contienen 9 y
12 composiciones: se conserva el requisito existente de suficiente evidencia
repetida; no se rebaja la confianza para paneles con pocos ejemplos.

Para reproducir:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_shared_background -v
.venv/Scripts/python.exe -m tests.evaluate_shared_background
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Límites y resultado en la aplicación

`ui.png` y `ui.json` muestran 15 detecciones, ninguna inventada y ningún
solapamiento entre cortes. Con el tamaño configurado de 5 × 5 pulgadas, las 15
composiciones exceden el cuadrado: se conserva el aviso morado `CLIPPED`.
Detectar el dibujo no hace que sus dimensiones físicas quepan en un corte menor.
Se mantienen la escala y el tamaño configurados por el usuario.

Los puntos de control verifican extensión y pertenencia; no equivalen a una
anotación exhaustiva de cada píxel del contorno. La evidencia sintética no
garantiza todas las telas reales. Si tinta y fondo carecen de diferencias
visibles, o el fondo no es compartido, esta ruta no debe inventar un dibujo.
