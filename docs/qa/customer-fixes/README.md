# Corrección de agrupación y límites de corte

Validación iniciada el 12 de octubre de 2026 y completada el 13 de octubre.

## Fallos reproducidos y corrección

- **Animales con accesorios:** el original del usuario devolvía 18 propuestas en
  una cuadrícula 6×3. La cuadrícula de cámara llena impedía revisar la propiedad
  de los componentes. Ahora se permite esa revisión cuando la geometría no tiene
  corroboración independiente: el original devuelve 12 composiciones 4×3.
  Se verifican 36 puntos elegidos sobre el original (animal y dos accesorios en
  cada una de las 12 casillas), con un único propietario por composición.
- **Regla general de límites:** cualquier corte o dibujo fuera de la cama
  configurada, o composición incompleta en la imagen, queda excluido. Se comprueba
  la geometría de la celda, incluidos sus vértices proyectados, además del contacto
  del dibujo con el borde de imagen. No depende de nombres de colecciones.
- **Pájaros originales:** se conservan 18 composiciones completas para revisión y
  se excluyen las 6 de la cuarta fila parcial. Se prueban también un alfabeto con
  fila recortada y celdas que exceden cada uno de los cuatro bordes de imagen.
- **Exportación:** el exportador rechaza cualquier corte bloqueado que se intente
  pasar como activado. El archivo anterior no se sobrescribe en ese caso. Los
  cortes bloqueados no aparecen en la previsualización de exportación. La interfaz
  los conserva identificados como excluidos y sin rectángulo de corte, salvo al
  seleccionarlos para inspección. Reducir el cuadrado o moverlo no recupera los
  píxeles ausentes de una composición parcial.

## Evidencia

- [Antes: animales](animals-before.json), [después](animals-after.json).
- [Animales en la aplicación](animals-ui.png), [pájaros](birds-ui.png),
  [otro caso de fila parcial](partial-row-ui.png). Capturas de la aplicación real
  mediante `render_results.py`, con detección real y tamaño predeterminado de 5 in.
- [Comparación de 21 imágenes anteriores](regression-comparison.json): sin cambios
  en cajas ni centros respecto a la versión anterior de diagnóstico. Esta
  comprobación no demuestra precisión universal ni corrige todos los detalles
  tenues; evita una regresión geométrica en estos controles.
- [Batería completa inicial](unittest.txt): 220 pruebas, 219 correctas; una prueba
  antigua de exportación de la demo asumía que se permitían cortes fuera de cama.
  Se actualizó esa expectativa para verificar la exclusión y se volvió a ejecutar
  junto con las pruebas afectadas en [validación final](final-targeted-tests.txt).
- **91 pruebas finales correctas**, más una comprobación adicional de celdas
  inferidas en una fila parcial: también quedan excluidas y no reaparecen como
  cuadrados activados al refrescar la cuadrícula.

## Límites que se mantienen

La exclusión depende de la cama y la colocación de imagen configuradas. No infiere
la escala física real de una imagen generada. Los dibujos de animales ocupan más
que el cuadrado de 5 in con la colocación predeterminada: las 12 composiciones se
agrupan correctamente, pero siguen avisando de que el dibujo excede el corte.
No se cambia silenciosamente el tamaño físico. Los avisos de detalle fino,
propiedad incierta y solapes siguen necesitando revisión.

Cambios locales, sin publicación ni envío al cliente.
