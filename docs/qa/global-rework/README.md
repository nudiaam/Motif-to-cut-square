# Corrección general y evaluación — 21-09-2026

Se ha modificado el código para corregir mecanismos comunes, sin reglas por
nombre de colección, clases de animales ni recuentos objetivo en el detector.
La agrupación mejora y el encuadre es más estable. La segmentación completa de
cada dibujo sigue sin estar resuelta: esta versión no acredita detección perfecta.

## Cambios implementados

1. **Un criterio compartido para formar composiciones.** Las cuadrículas fiables
   de todas las procedencias pasan por la misma agrupación. Fragmentos próximos
   y accesorios pequeños próximos al motivo principal se combinan con límites
   relativos al espaciado. Dos dibujos distantes se conservan para revisión.
   Una rama automática sin cuadrícula fiable ahora avisa de que la propiedad de
   las regiones está sin resolver. La mariposa junto al gato deja de crear un
   segundo corte en el panel pastel recto.
2. **El marco de análisis y el área impresa se separan.** Cuando hay evidencia de
   tela clara sobre fondo oscuro se normaliza el encuadre de análisis respecto a
   esa tela. Se conservan las coordenadas y la calibración de la imagen original.
   En la rama de cámara, el origen y el paso se ajustan a divisiones internas
   observadas, sin repartir automáticamente todo el contorno de tela. Si las
   divisiones no permiten estimar el área impresa, se señala incertidumbre.
3. **Ventanas solapadas y máscara revisable.** El análisis local añade contexto
   del 10 % alrededor de la casilla. La muestra de fondo se obtiene dentro de la
   casilla para no mezclar el fondo vecino, pero no se eliminan esos píxeles del
   análisis. GrabCut usa una máscara de fondo/figura probable; desaparece el
   rectángulo que convertía todo el exterior en fondo definitivo. Solo se fijan
   píxeles del borde compatibles con el fondo muestreado. Esto todavía puede
   fallar si el dibujo y el fondo tienen aspecto parecido.
4. **Revisión contra píxeles originales.** Una comprobación de color y continuidad
   examina también el contexto fuera de cada caja detectada. Puede contradecir
   una caja aparentemente válida. Sus avisos llegan a lista, color del corte,
   detalles, comprobación de salida y JSON. Los huecos inferidos tampoco se
   presentan como dibujos detectados. Esta comprobación es una evidencia adicional,
   no un verificador semántico infalible ni un segundo modelo aprendido.

Las marcas fuera de la cuadrícula que siguen perteneciendo a una región física
posible se conservan con aviso. Antes se podían borrar solo por quedar fuera.
Esto puede aumentar los elementos que requieren revisión: una diferencia frente
a la cama vacía también podría ser una segunda pieza, no necesariamente suciedad.

`review_reasons` expresa incertidumbre de detección, mientras que `exportable`
sigue expresando elegibilidad geométrica. El aviso no modifica el tamaño del
corte ni elimina silenciosamente un rectángulo del SVG; sigue siendo necesaria
la revisión del usuario dentro del flujo de confirmación existente.

## Evidencia

Las 166 pruebas pasan: `python -m unittest discover -s tests -q` (73,8 s en esta
ejecución). Las nuevas pruebas ejercitan agrupación independiente de la rama,
márgenes del área impresa, una extremidad que crece hasta casi el borde, una caja
deliberadamente incompleta, separación de un vecino, fallback incierto, estabilidad
al añadir marco y propagación del aviso hasta interfaz e informe.

- La figura de prueba con extremidad ya devuelve su caja completa en cinco
  longitudes; antes quedaba truncada por el rectángulo fijo de GrabCut.
- Añadir 0, 80 o 160 píxeles oscuros alrededor de la misma foto de perros mantiene
  24 composiciones, cuadrícula 6×4 y centros equivalentes tras descontar el margen
  (tolerancia de prueba: 6 píxeles). Antes, con 160 píxeles, cambiaba a 15 / 6×3.
- En los tres paneles rectos, cada una de las 24 casillas anotadas tiene exactamente
  una composición. El evaluador recibe las anotaciones; el detector no las recibe.

| Panel recto | Candidatos antes → ahora | Casillas únicas | Listos / con avisos en UI, corte 5 pulgadas |
| --- | ---: | ---: | ---: |
| Pastel | 25 → 24 | 24/24 | 17 / 7 |
| Perros | 24 → 24 | 24/24 | 4 / 20 |
| Corazones | 24 → 24 | 24/24 | 6 / 18 |

Los avisos incluyen geometría y extensión; **no son un recuento de errores reales**.
Al ampliar el contexto algunas cajas absorben fondo, por lo que también aumentan
los avisos de recorte. No se han reducido avisos artificialmente para dejar todo verde.
Las imágenes generadas carecen de escala física de fabricación: esta prueba no
certifica que un corte real de 5 pulgadas deba abarcar cada ilustración.

Los cuatro fixtures anteriores conservan sus recuentos: pastel 24, patchwork 22,
transporte 19 y vehículos 24. En patchwork siguen faltando dos detecciones reales;
la interfaz propone posiciones de cuadrícula con aviso, no las cuenta como
evidencia de dos dibujos reconocidos. Las otras imágenes generadas conservan
24, 24 y 19 composiciones.

No se han añadido dependencias, GPU, servicios externos ni inferencia neuronal.
Los diez casos tardaron aproximadamente 0,63–3,25 s por detección en este equipo.
Esto no es un perfil de CPU/RAM ni una garantía de rendimiento en el ordenador del cliente.

## Qué falta resolver

La inspección de [las cajas de perros](dogs_6x4-bounds.png) muestra aún detecciones
parciales y cajas que incorporan parte del fondo. El revisor detecta algunas,
pero no todas las omisiones; también produce falsos avisos por estampados.
Por tanto, aumentar el número de avisos **no equivale a mejorar la silueta**.

El siguiente problema general es estimar qué textura pertenece al fondo de cada
casilla y contrastar varias evidencias de extensión antes de cerrar una composición.
Para comprobarlo hay que anotar siluetas o extremos esperados en un conjunto
separado de evaluación; contar casillas no basta. Tampoco se ha implementado toda
la propuesta de máscaras por componente y asignación explícita de evidencia no
resuelta. El modo con referencia de cama conserva la extensión de posiciones
posibles sobre tela; esas posiciones no certifican que haya impresión.

La garantía defendible sigue siendo: no ocultar la incertidumbre detectada y
permitir revisar el resultado. Estos cambios no garantizan acierto en cualquier foto.

## Reproducción y archivos

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -q
.venv/Scripts/python.exe -m tests.evaluate_straight_panels --output docs/qa/global-rework/cell-coverage.json
.venv/Scripts/python.exe -m tests.evaluate_global_detection --output docs/qa/global-rework --screenshots
```

- [Cobertura de casillas](cell-coverage.json), [diez fixtures y tiempos](fixture-results.json),
  [estados de interfaz](ui-results.json).
- Interfaz: [pastel](pastel_6x4-ui.png), [perros](dogs_6x4-ui.png), [corazones](hearts_6x4-ui.png).
- Cajas detectadas: [pastel](pastel_6x4-bounds.png), [perros](dogs_6x4-bounds.png), [corazones](hearts_6x4-bounds.png).
- Informes UI: [pastel](pastel_6x4.json), [perros](dogs_6x4.json), [corazones](hearts_6x4.json).
- La [evaluación previa](../straight-panels/README.md) se conserva sin sobrescribir.
