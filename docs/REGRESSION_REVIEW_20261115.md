# Revisión detenida por regresiones — 15 de noviembre de 2026

Registro histórico de la parada solicitada por el usuario. Después de la auditoría,
el usuario autorizó la corrección. El estado posterior y sus comprobaciones se
describen en [la ficha de 0.13.0-rc2](RELEASE_0_13_0_RC2.md). Los apartados siguientes
conservan los hechos y limitaciones de aquella revisión, sin reescribir sus resultados.

## Conclusión comprobada

La detección nueva de divisiones impresas introdujo una regresión de colocación
en la fotografía de corazones con flores. No es solo una diferencia de colores.
El código guardado anteriormente no producía los solapes de esa fotografía.

Se ejecutó la misma imagen a 5 × 5 pulgadas, con los valores iniciales de la app,
en copias aisladas de tres estados. No se modificó la app durante esta revisión.

| Estado | Casillas de corazones | Cortes con solape | Cortes que cruzan su sección medida | Centro Y de primera fila, columna 3 |
|---|---:|---:|---:|---:|
| Código guardado en Git (`57b91f008b196de1e90fc3313b93ca4dd7715746`) | 24 | 0 | 0 | 177,63 px |
| Entrega asociada a las 312 pruebas | 24 | 12 | 6 | 195,57 px |
| Cambios pendientes anteriores a la parada | 24 | 0 | 0 | 168,31 px |

El centro de referencia aproximado de esa casilla, tomado sobre las divisiones
de la foto, es 170 px. Los resultados pendientes mejoran este caso, pero no se
consideran validados para todas las telas ni justifican continuar sin revisar.
El estado anterior tampoco queda certificado como correcto en todos sus
contornos o exportaciones por pasar esta comparación geométrica.

Los registros por corte y las huellas de imagen están en
[la comparación anterior](qa/regression-review-20261115/head.json),
[la entrega de 312 pruebas](qa/regression-review-20261115/delivered-312.json) y
[los cambios pendientes](qa/regression-review-20261115/pending.json).

## Qué lo produjo

1. La nueva ruta de divisiones impresas sustituyó a la ruta anterior
   `local_contrast` en los corazones. Se aceptó el número correcto de filas y
   columnas sin detectar suficientemente el error del borde superior.
2. Una escala de análisis confundió una respuesta del borde de los corazones
   con el límite exterior del estampado. La otra escala localizó el borde de la
   tela. Se comprobaba el acuerdo de las divisiones interiores, pero se combinó
   el borde exterior eligiendo el más interior de ambos resultados.
3. La primera fila quedó demasiado baja y estrecha. Con cortes de 5 pulgadas
   aparecieron seis cruces de sección y doce cortes solapados.

La corrección pendiente localiza los bordes exteriores a partir de las divisiones
vecinas medidas. Hay una regresión de prueba para una respuesta repetida de
dibujo más fuerte que el borde y otra para la fotografía real. Son comprobaciones
iniciales; falta verificar el efecto sobre el resto de las tipologías.

## Problema independiente: significado del rojo

La entrega convirtió demasiadas discrepancias de límites detectados en una
afirmación roja de recorte. Que dos lecturas coincidan en ciertos píxeles no
resuelve un contorno que el propio análisis considera incierto.

En la foto de animales descentrados, los tres estados conservan 15 casillas sin
solapes ni cruces. La entrega muestra 15 avisos rojos a 5 pulgadas. El cambio
pendiente reduce esos avisos a tres; eso no demuestra que esos tres sean
semánticamente correctos ni que el problema visual esté completamente resuelto.

El contrato acordado en [CUTTING_RULES.md](CUTTING_RULES.md) es:

- Morado: duda concreta que debe explicarse, incluido posible recorte de un
  contorno incierto. No significa «no lo hagas» ni se presenta como listo.
- Rojo: conflicto comprobado, como un cruce de sección o recorte de un contorno
  resuelto. Una sospecha del detector no basta.
- Verde: sin conflictos detectados ni dudas pendientes.
- Los avisos marcados dentro de cama se pueden exportar. Los cortes fuera de
  cama se omiten. Los colores no deben mover ni redimensionar el SVG.

## Por qué las pruebas aprobadas no bastaron

Las 312 pruebas sí pasaron en el estado entregado, pero no demostraban ausencia
de regresiones visuales. Acertar el recuento y reconstruir fielmente un SVG
pueden validar numéricamente una cuadrícula mal colocada. El conjunto fotográfico
no incluía esta nueva foto de corazones, y algunas referencias de centros eran
aproximadas o interpoladas. Se publicaron sus discrepancias, pero no se usaron
como un criterio suficientemente estricto para detener la entrega.

Fue incorrecto presentar esos resultados como garantía de que no se había roto
el comportamiento anterior. La aceptación debe comparar geometría anterior y
nueva sobre las mismas imágenes y límites independientes, no solo recuentos y
coherencia entre la app y su propio SVG.

## Qué queda pendiente, sin darlo por entregado

Antes de la petición de parada se habían cambiado siete archivos de producción:
`models.py`, `review_summary.py`, `printed_partition.py`, la revisión del detector,
`canvas.py`, `side_panel.py` y `main_window.py`. Se conservan sus diferencias en
[pending-production.diff](qa/regression-review-20261115/pending-production.diff)
y las huellas en [source-state.json](qa/regression-review-20261115/source-state.json).

Los cambios pendientes pasaron 56 pruebas enfocadas; la suite completa no se ha
repetido para este estado. Tampoco se han regenerado los diez informes de fotos
ni los paquetes de entrega. El diff y el ZIP anteriores corresponden al estado
de 312 pruebas y no deben considerarse una entrega aprobada tras esta revisión.

La siguiente implementación debe partir de esta revisión, conservar una referencia
anterior y verificar por separado: bordes y centros, composición y accesorios,
certeza del color, ausencia de solapes y geometría real del SVG. Una mejora en
esta comparación no basta para dar el conjunto por corregido.

## Auditoría ampliada y consulta a otros chats

Se consultaron expresamente «Conservar análisis y propuestas» y «Analizar mejoras
de detección», además del historial disponible de «Generar imágenes de telas» y
«Eliminar recuadros de imagen». Los dos primeros recuperaron sus versiones,
originales, expectativas y limitaciones sin modificar aplicación, tests ni Git.
Sus respuestas se conservan en [consultations.md](qa/regression-review-20261115/consultations.md).

Se reunieron **62 imágenes con píxeles distintos**: las de esta revisión,
controles anteriores, los cinco originales posteriores de octubre, la imagen
del paquete real del cliente y cuatro reconstrucciones generativas recuperadas
del 1 de noviembre. Estas cuatro últimas no son fotos originales auténticas ni
verdad geométrica de las capturas que intentaban reconstruir.

La comparación produjo **124 ejecuciones**, todas con los mismos ajustes por
imagen, colocación inicial y cortes de 5 × 5 pulgadas. Se usaron exclusivamente
las dos copias aisladas: HEAD guardado y entrega asociada a las 312 pruebas.
No se probó ni aprobó con ello el código pendiente posterior. Se verificaron las
huellas de las entradas y que la aplicación en el workspace permaneció intacta.

### Qué cambió en otras pruebas

| Imagen | Cortes con solape antes → entrega | Cruces de sus secciones medidas antes → entrega | Interpretación |
|---|---:|---:|---|
| Corazones con flores, aportada ahora | 0 → 12 | 0 → 6 | Regresión de borde y colocación confirmada. |
| `generated/pastel_animals_6x4.png`, control antiguo | 0 → 12 | 0 → 7 | Otra incidencia geométrica: requiere contrastar todos sus bordes reales. El estado anterior sin solapes no certificaba su centrado. |
| Perros frontales generados | 0 → 0 | 0 → 0 | No se reproduce ese aumento de solapes. |
| Corazones frontales generados | 0 → 0 | 0 → 0 | No se reproduce ese aumento de solapes. |

Hay **26 entradas con solapes ya presentes en la referencia anterior** a ese
tamaño supuesto. No se clasifican como regresiones nuevas: algunas imágenes no
permiten cuadrados de 5 pulgadas y otras conservan problemas previos de malla.
Los cruces de la tabla se miden contra el polígono de cada versión, no contra una
anotación física exacta. Tampoco se califica como fallo un simple aumento de rojo.

Se conservan 55 recuentos y cambian siete. Parte de esos cambios son mejoras:
animales con accesorios pasa de 20 fragmentos a 12 composiciones; beige, de 14
a 24; contraste muy bajo, de 15 a 24; sombra diagonal, de 18 a 24. La eliminación
de seis propuestas de una fila parcial conserva los 18 cortes marcados dentro de
cama. Estos aciertos no compensan ni justifican las regresiones geométricas.

En los puntos de dibujo muestreados no aparecen grupos nuevos fallidos al aplicar
las tolerancias originales de las pruebas. También se conserva la medición
estricta: en `animals_panels` un testigo queda un píxel fuera de una caja nueva,
dentro de los dos píxeles que ya admitía la prueba original. No se han relajado
tests en esta auditoría. Los testigos no representan siluetas completas.

### Exportaciones y límites de la evidencia

En los 124 SVG, los rectángulos corresponden a los cortes marcados dentro de cama;
no aparecen coordenadas inesperadas ni rectángulos fuera de cama. Las páginas
declaran 36 × 24 pulgadas. Esto comprueba serialización e inclusión, no colocación
correcta respecto a la tela ni alineación física con la Epilog: un archivo fiel
puede reproducir una cuadrícula mal colocada.

Solo **14 de las 62 imágenes** tienen referencias geométricas independientes,
y son aproximadas. Para las otras 48 no se puede concluir que centros y límites
sean correctos porque el recuento coincida o no haya solapes. La colección revisada
tampoco equivale a 62 productos reales independientes ni a una validación de máquina.

Se publican [la galería comparativa completa](qa/regression-review-20261115/corpus/index.html),
[el resumen](qa/regression-review-20261115/corpus/summary.json),
[las diferencias por imagen](qa/regression-review-20261115/corpus/comparison.json) y
[las entradas y sus huellas](qa/regression-review-20261115/corpus/manifest.json).
No son una nueva declaración de pruebas aprobadas.

### Control de versiones que faltaba hacer efectivo

La referencia anterior tiene un commit concreto. La entrega cuestionada era un
diff y un paquete de evidencia, sin commit propio; se ha reconstruido exactamente
para compararla. La huella SHA-256 del diff es
`737acdb8a0914b61601f2cd67d50260480576c4f9cb1a07ab2f2be6fda5cc8f6`.
El título común `v0.12.0` no distingue esos estados y no basta para identificar
la aplicación que produjo una captura.

Antes de otra entrega se necesita una referencia identificable e inmutable,
imagen/ajustes/escala registrados y comparación anterior/nueva. Los criterios
deben exigir por separado propiedad de composición, bordes independientes,
centros, solapes, certeza del color y SVG. Un nuevo fallo geométrico debe detener
la entrega aunque toda la suite automática pase. El recuento de tests no puede
sustituir ese criterio. Durante esta auditoría se mantuvo la parada de implementación.
