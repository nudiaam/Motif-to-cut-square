# Mejoras de revisión y diagnóstico de colecciones

12 de octubre de 2026. Revisión `2026-10-12-reproducible-collection-review`.
Implementación local; no se ha publicado ni enviado una versión al cliente.

## Qué está implementado

| Área | Cambio efectivo |
| --- | --- |
| Repetibilidad | Huellas de píxeles del original y referencia, ajustes efectivos, ruta, guías confirmadas, versiones y huella del resultado. Los tiempos se guardan por separado. |
| Soporte | Botón **Save diagnostic package…**, dentro de ajustes avanzados: ZIP con original PNG sin superposiciones, informe y referencia coincidente cuando sigue disponible. Si cambió la referencia, se registra su ausencia; nunca se adjunta otra como si fuera la usada. |
| Comparación | `python -m app.compare_detection_reports primera.zip segunda.zip`, también admite JSON. Distingue entradas cambiadas, resultado del detector y cortes revisados por el operador. Los informes antiguos sin huellas se declaran insuficientes. |
| Interfaz | El botón principal **Detect + check** y la acción Detect usan un trabajador con progreso por fase y cancelación. Cada trabajo tiene copia de los píxeles y su propio detector. Cancelar o fallar conserva los cortes anteriores; cerrar espera a la cancelación. |
| Planificador | Registra hipótesis con puntuaciones cercanas pero distinto origen, paso o dimensiones. Mantiene revisión si no se resuelve; la evidencia independiente posterior puede resolver la duda sin añadir avisos a toda una colección innecesariamente. |
| Coste | Los perfiles de divisiones que dependen solo de la imagen se calculan una vez por comparación. No se ha añadido una caché persistente ni se ha eliminado una ruta para obtener mejores tiempos. |
| Filas parciales | Aviso de casilla parcialmente fuera de la imagen, distinto de un cuadrado fuera de cama. No se eliminan automáticamente filas reales ni se fuerza 6×4. |
| Extensión | Una extracción muy pequeña sobre fondo con mucho detalle exige revisión de partes tenues/desconectadas. Evita certificar el centro de un dibujo como composición completa. |
| Avisos y escala | Desglose de solapes, límites de cama, dibujo que excede el corte, distribución, detalle, posiciones inferidas y paneles parciales. Una misma pieza puede aparecer en varias categorías. Se muestra separación estimada entre centros en unidades físicas. |

El análisis adaptativo existente permanece activo; no hay ajustes por nombres
de colección, aprendizaje entre pasadas ni modificación automática del tamaño
físico de los cuadrados. Las rutas de recuperación manual conservan su contrato;
algunas operaciones auxiliares de estimación de guías continúan siendo síncronas.

## Imágenes generadas

Se utilizaron dos llamadas a la herramienta integrada `image_gen`, siguiendo la
petición del usuario. Originales guardados en el proyecto:

- [Alfabeto](../../../tests/fixtures/generated/customer_20261012/alphabet_6x4.png):
  6×4, letras A–X y dibujos separados sobre fondo de puntos.
- [Navidad](../../../tests/fixtures/generated/customer_20261012/christmas_6x4.png):
  6×4, fondos de puntos, cuadros, rayas y estrellas; figuras agrupadas y detalles finos.
- [Prompts exactos](../../../tests/fixtures/generated/customer_20261012/prompts.json)
  y [huellas de los archivos](../../../tests/fixtures/generated/customer_20261012/manifest.json).

Ambas son imágenes sintéticas de 1536×1024 revisadas visualmente, no los originales
de Eugenio. El recuento esperado y los puntos testigo viven en las pruebas, no
en el detector. No tienen una calibración física real.

## Verificación

- **216 pruebas de la batería completa correctas**, incluidas 11 nuevas:
  [registro](unittest.txt). Se usó un directorio temporal dentro del proyecto
  para evitar las restricciones de escritura del entorno sobre temporales externos.
- Tras el pequeño ajuste final de historial se repitieron las comprobaciones
  afectadas: [12 pruebas de interfaz](final-ui-tests.txt). Las pruebas de
  diagnóstico incluyen además resolución equivalente y última fila recortada:
  [registro final](final-diagnostics-tests.txt).
- **21 imágenes comparadas antes/después, con cajas y centros idénticos en las 21**:
  [comparación](comparison.json), [antes](before/results.json) y [después](after/results.json).
  Incluyen 19 controles anteriores y las dos nuevas imágenes. No se ha demostrado
  una mejora en recuento: se ha mejorado la trazabilidad, revisión y operación.
- Los avisos nuevos de detalle afectan al copo de nieve sintético y una extracción
  pequeña del patchwork de cámara. Las dudas iniciales de cuadrícula de pastel y
  figuras finas quedan resueltas por la evidencia independiente ya disponible.
- **Dos detecciones consecutivas desde la interfaz para cada imagen nueva**:
  mismas entradas, resultado y cortes; [comparación](ui-repeatability.json).
- [Variantes exploratorias](variants.json): añadir margen conserva 24 detecciones
  en ambas; recortar la parte inferior conserva la propuesta de 24 y señala las
  seis casillas de la última fila como parciales en ambas.
- Al reducir Alfabeto a media resolución conservando el área mínima de 500 px²
  aparecen 23 detecciones. Con ajustes equivalentes (125 px² y distancias a la
  mitad) vuelve a dar 24; esto se comprueba en la prueba de colecciones generadas.
  No demuestra un error de estado, y evita atribuir a una segunda pasada una
  mejora causada por entradas o parámetros no equivalentes.
- Se han renderizado e inspeccionado las pantallas reales de Qt con estilos y
  tipografía de la aplicación: [Alfabeto](alphabet_6x4-ui.png) y
  [Navidad](christmas_6x4-ui.png). Script: [render_ui.py](render_ui.py).
- Se han generado paquetes de diagnóstico reales de ambas pruebas y se ha
  comprobado su lectura con el comparador. Las pruebas automatizadas verifican
  igualdad de los píxeles, rechazo de un original cambiado y ausencia de una
  referencia incorrecta en el ZIP.

Los tiempos antes/después son observaciones locales de una ejecución por caso,
no un benchmark aislado. No se afirma una aceleración porcentual. La mejora
comprobada de respuesta es que el bucle de interfaz sigue atendiendo eventos y
cancelación mientras trabaja el detector. Algunas operaciones de OpenCV deben
terminar antes de alcanzar el siguiente punto de cancelación.

## Límites que siguen abiertos

1. **El copo de nieve de Navidad aún no tiene todas sus puntas segmentadas.** Ahora
   requiere revisión; no se ha ampliado una caja arbitrariamente para declarar
   resuelto el caso. Tampoco se garantiza recuperar cada ala, rama o accesorio.
2. El patchwork tenue histórico sigue teniendo 22 candidatos. Los controles
   conservan ese resultado previo; no se presenta como 24 detecciones confirmadas.
3. Con la colocación predeterminada 36×24 pulgadas, las imágenes generadas tienen
   separación vertical estimada menor que los cuadrados de 5 pulgadas: las dos
   pantallas muestran 24 solapes y cero listos. Es una incompatibilidad física
   bajo esa escala, no un fallo de recuento. No se cambió el tamaño para volverlos verdes.
4. Las capturas del cliente no permiten validar que los errores originales de
   Alfabeto/Navidad estén corregidos. Para esa comprobación siguen haciendo falta
   sus originales y los paquetes de las dos pasadas.
5. La nueva revisión de fondo texturado es conservadora y puede avisar de un
   motivo legítimamente pequeño. No es un reconocedor semántico ni una máscara
   completa anotada del dibujo.
6. No se han creado perfiles específicos por colección ni se ha introducido un
   modelo neuronal. Serían decisiones posteriores basadas en fallos reproducibles.

## Reproducción

Desde la raíz del proyecto:

```powershell
.venv/Scripts/python.exe -m tests.evaluate_customer_collections --output docs/qa/customer-improvements/after
.venv/Scripts/python.exe docs/qa/customer-improvements/render_ui.py
.venv/Scripts/python.exe -m app.compare_detection_reports docs/qa/customer-improvements/alphabet_6x4-repeat-1.json docs/qa/customer-improvements/alphabet_6x4-repeat-2.json
```

Los ZIP contienen imágenes, no código ejecutable; no se envían automáticamente.
Para investigar el cliente, pedir un paquete por pasada y anotar si volvió a
capturar, pegar, cambiar ajustes o confirmar guías entre ellas.
