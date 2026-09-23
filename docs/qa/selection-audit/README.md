# Auditoría de selección y cobertura — 23 septiembre 2026

**No se ha cambiado el código de producción durante esta auditoría.** El objetivo
es establecer qué errores son anteriores al cambio de sombras y qué evidencia
debe exigirse antes de permitir que una ruta sustituya a otra.

## Comparación controlada

Se conservaron originales sin superposiciones en `tests/fixtures/acceptance/`.
Se ejecutaron tres variantes con los mismos píxeles y parámetros predeterminados:

1. Detector actual.
2. Detector actual desactivando únicamente la propuesta nueva de contraste.
3. Además de desactivarla, reconstrucción en memoria del selector y de las rutas
   de fallback anteriores al cambio de sombras del 22 de septiembre. No es una
   ejecución de un binario histórico: es una ablación explícita de ese cambio.

| Caso | Esperado por inspección | Actual | Sin propuesta nueva | Selección anterior |
|---|---:|---:|---:|---:|
| Animales pastel 4×4 | 16 | 19, grid 5×4 | 19, grid 5×4 | 19, grid 5×4 |
| Espacio oscuro 3×5 | 15 | 1, sin grid | 1, sin grid | 1, sin grid |
| Animales con adornos 4×3 | 12 composiciones | 14 | 14 | 14 |
| Animales con jirafa de dos casillas | 19 | 19 | 19 | 19 |
| Figuras finas 7×3 | 21 | 21 | 21 | 21 |

La interfaz del pastel completa una casilla inferida y muestra 20 cortes. No
significa que haya 20 animales. Estos dos primeros fallos se reproducen sin el
cambio nuevo; no queda probado que sean regresiones introducidas por él. Eso no
descarta regresiones en otras imágenes y no valida la afirmación amplia de que
todo lo anterior seguiría funcionando.

## Causa confirmada: el selector desecha una segmentación correcta

En el pastel, `infer_repeated_artwork` ya produce **16 regiones completas y una
cuadrícula 4×4**, con confianza interna 0,973. La superposición
`pastel-existing-pattern-proposal.png` permite inspeccionar las cajas sobre el
original, incluidos cuerpos y patas.

La comparación de grids, sin embargo, se hace con las detecciones de la primera
segmentación, que en esta imagen son incompletas. La ruta correcta recibe una
puntuación 0,407 y la propuesta de cámara 5×4 recibe 0,620. El soporte de líneas de
esta última es 0,860 y compensa su escasa alineación, de 0,333. La ruta correcta
no alcanza el umbral de protección cuando se mide con esas detecciones ajenas.

El fallo no requiere aumentar sensibilidad. Hace falta que las propuestas
conserven su evidencia de composiciones y que una sustitución tenga que explicar
esas mismas composiciones, sin inventar columnas ni dividir dibujos completos.
La confianza interna de un productor no demuestra por sí sola exactitud.

## Causa confirmada: contraste de una sola polaridad

La nueva propuesta de contraste estima detalles más oscuros que su entorno.
En la tela azul marino, los motivos relevantes son mayoritariamente más claros.
Las otras rutas tampoco consiguen una cuadrícula en ese original.

Una intervención aislada invirtiendo únicamente la polaridad de luminancia de la
vista de análisis obtiene una cuadrícula 3×5, concordante en 30 pasadas. El análisis
local posterior sobre el original devuelve 15 figuras. La imagen
`space-light-polarity-probe.png` muestra el resultado. Es una prueba causal,
**no una corrección desplegada ni una validación de toda la extensión de las figuras**.

## Causa confirmada: patchwork de 20 animales

El original añadido después, `Imagen de Codex 23 sept 2026, 00_38_25.png`, está
conservado como `tests/fixtures/acceptance/patchwork_animals_5x4.png`. Las tres
variantes devuelven cuatro cortes y grid 2×2: tampoco este resultado depende del
último cambio de sombras. Resultados completos en
`patchwork_animals_5x4-ab-comparison.json`.

La primera segmentación aporta solo cuatro fragmentos, con cajas
`(1308,335,69,129)`, `(676,561,68,61)`, `(1226,759,58,100)` y
`(1447,773,63,79)`. No son veinte animales completos. La ruta visual de bandas no
produce una propuesta; la alternativa `infer_panel_grid` usa ese recuento débil
para puntuar dimensiones y devuelve 2×2 con confianza interna 0,98. Ejecutar
esa misma inferencia sin los cuatro candidatos devuelve `None`.

El selector recibe solo esa propuesta: soporte de líneas 1,0, ocupación 0,75,
alineación 0,25. La acepta; el análisis posterior se limita a cuatro grandes
zonas. La nueva ruta de contraste no encuentra consenso y no interviene.
Por tanto, aquí todavía falta producir una hipótesis 5×4 respaldada por los
cambios de fondo; no basta con elegir mejor entre las propuestas existentes.
Además hay dependencia circular: los fragmentos condicionan el grid y ese grid
limita después qué composiciones se buscan.

`restored-contact-sheet.jpg` y `restored-index.json` documentan los archivos
inspeccionados y sus SHA-256. Se eliminaron duplicados por contenido en ese índice;
las capturas históricas se identifican visualmente y no se usan como originales.

## Cambio necesario en la validación

- Mantener originales permanentes y expectativas explícitas: número de
  composiciones, relación con las casillas, partes del dibujo y elementos accesorios.
- Comparar posiciones, pertenencia y extensión, además del recuento. Mantener
  los puntos de control anteriores de sombras y dibujos que abarcan varias casillas.
- Registrar cada propuesta, su evidencia y el motivo de su sustitución. Una nueva
  ruta no puede reemplazar otra solo por tener un número interno de confianza mayor.
- Exigir que cualquier alternativa explique composiciones ya respaldadas; no
  usar únicamente centros de una segmentación incompleta para evaluar todas las rutas.
- Probar ambas polaridades del contraste y comprobar desacuerdos entre ellas;
  no aplicar una inversión global indiscriminada a las imágenes del usuario.
- La polaridad no resuelve por sí sola tela oscura con dibujos oscuros. Evaluar
  diferencias locales de cromaticidad, contornos y textura además de luminancia;
  conservar las evidencias independientes y exigir respaldo para distinguir
  dibujos de adornos repetidos del fondo. Son alternativas pendientes de prueba.
- La comprobación mutua debe detectar desacuerdos, no hacer que ambas rutas
  confirmen una partición previamente impuesta. Registrar agrupaciones,
  divisiones de composiciones y contenido fuera de las casillas; limitar las
  reevaluaciones y mantener revisión cuando no haya evidencia suficiente.
- Incluir estas imágenes en la comparación anterior/posterior antes de presentar
  otra versión como validada. No prometer funcionamiento universal por pasar una
  batería finita de casos.

## Reproducción

```powershell
.venv/Scripts/python.exe -m tests.diagnose_selection_audit
```

El script aplica las ablaciones solo en memoria y verifica las huellas del código
de producción antes y después. `ab-comparison.json` guarda resultados, cajas,
propuestas y huellas. Los originales usados son los cinco archivos del usuario
del 23 de septiembre, de 00:16:17 a 00:16:43, y el patchwork de 00:38:25,
conservados sin alterar sus bytes. Para repetir solo el patchwork:

```powershell
.venv/Scripts/python.exe -m tests.diagnose_selection_audit --image patchwork_animals_5x4.png
```
