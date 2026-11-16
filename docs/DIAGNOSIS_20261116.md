# Diagnóstico de los paquetes 01 y 02 — 16 de noviembre de 2026

Estado: análisis y reproducción, sin cambios de producción.

## Evidencia y alcance

Ambos ZIP se copiaron a carpetas separadas. Sus report.json coinciden byte a
byte con los JSON independientes recibidos. Al reproducir con imagen,
referencia y ajustes originales coinciden tanto la identidad de entrada como
la huella del resultado en los dos casos. Ambos proceden de la revisión de
detector `2026-11-15-outer-frame-recovery-rc3`, también usada por 0.13.3.

Se probaron cortes de 4 y 5 pulgadas después de detectar. Los centros no cambian
al variar el tamaño. Se conservan las capturas y los SVG reales de ambas medidas.

## 01 — alineación

La ruta aceptada es `independent_printed_partition`, método
`sustained_printed_colour`. Se rectifica la tela mediante un cuadrilátero global,
se leen perfiles agregados a dos escalas y se proyectan polígonos y centros de
cada casilla a la fotografía. Las líneas medidas no se sustituyen por una malla
regular al colocar el corte: se conservaron los centros individuales, por lo que
no se atribuye erróneamente este caso a una pérdida de sus posiciones desiguales.

Sin embargo, algunas líneas proyectadas no coinciden con el centro de las
separaciones blancas del original. Lecturas independientes del bajo croma de
esas franjas muestran discrepancias internas de hasta aproximadamente 3,7 px.
La posición concreta depende de la fila o columna. Son referencias aproximadas
sobre píxeles, no una calibración física de la máquina ni un contorno exacto.
Las lecturas por cambio de color y por franja blanca no definen necesariamente
el mismo centro cuando el filtro mezcla colores distintos de los dos fondos.

El problema estructural confirmado es que ese modelo se acepta sin una
comprobación local posterior contra las divisiones del original. El afinado
`refine_printed_boundaries` se abstiene cuando hay una proyección; aquí se
confirma `projection_present=true, changed=false`. La corrección anterior de
rc3 actuaba sobre la ruta visual sin proyección y, por tanto, no resuelve este
caso. El detalle de cuánto error aporta el cuadrilátero global y cuánto aporta
el perfil filtrado no queda separado en este análisis; no se presenta una
atribución numérica única a uno de ellos.

Con 5 pulgadas se registran 23 cortes solapados y 18 cruces de las propias guías;
con 4 pulgadas ambos recuentos son cero, pero los centros son exactamente los
mismos. Por eso reducir la medida elimina esos conflictos de tamaño y no corrige
el desajuste de alineación. Que un corte quepa en las guías calculadas tampoco
prueba que esas guías reproduzcan fielmente la impresión.

## 02 — quinta fila inexistente de seis cortes

Hay cuatro filas impresas. El detector devuelve seis columnas por cinco filas:
30 candidatos. La fila adicional está dentro de la cama y sobre tela sin dibujo;
la regla de omitir cortes fuera de cama no puede retirarla.

La ruta es la misma familia `independent_printed_partition`, ahora con método
`sustained_printed_frames`. El ajuste considera la altura de la tela completa,
incluido el margen sin imprimir. Las divisiones del estampado encajan en una
hipótesis de cinco filas, donde el marco inferior real se interpreta como otra
separación interior. En el plano rectificado aparecen líneas en Y=14,0 / 166,5 /
312,3 / 448,8 / 585,5 / 724,5. La última no tiene observación en ninguna de las dos
lecturas: `observed=false`, `estimated=[5]`. Aun así, conserva la fila añadida.
No existe truncamiento de la fuente que autorice esa extensión.

Después se analiza cada celda de la hipótesis. En las seis celdas inferiores,
la lectura de silueta recurre a la lectura original de baja confianza. Esta
acepta entre 522 y 1065 píxeles como primer plano: textura, bordes o variación
de iluminación sobre la tela vacía. Se devuelven candidatos con extensión
incierta, algunos con cajas que abarcan casi toda la celda. Se supera el mínimo
de celdas segmentadas y la hipótesis se acepta con confianza geométrica 0,94.
La incertidumbre añade avisos pero no cuestiona la existencia de la fila.

No son seis dibujos parcialmente fuera de cama ni seis exclusiones manuales:
son seis falsos positivos dentro de la tela. En el informe incluso aparecen como
`inferred=false` porque ya se crearon como candidatos de segmentación.

## Por qué aparece Review

La lógica de color sigue siendo la anterior a la simplificación propuesta por
el usuario. `cut_status_color` convierte cualquier `review_reasons`, contorno
incierto o aviso de revisión en morado, sin exigir un cruce concreto de sección.

En 01, con 4 pulgadas, quedan 10 revisiones de contorno y 14 cortes verdes. Con
5 pulgadas se añaden conflictos de solape y de límites. En 02 hay 27 contornos
inciertos y el aviso global de divisiones sin confirmar se propaga a los 30
candidatos, incluidos los seis falsos positivos. Tres cortes tienen además
recorte de dibujo confirmado según el criterio anterior, que se pinta rojo.
El color mezcla dudas de detección con la evaluación del corte final. La guía
verde/morado/rojo acordada aún no se ha implementado.

## Causa común y por qué las pruebas anteriores no bastaron

Se mezclan tres decisiones distintas: que una cuadrícula sea plausible, que
exista una composición en cada celda y que un corte final tenga un conflicto.
Dos escalas concordantes comparten el mismo modelo y pueden coincidir en el
mismo error. Un resultado incierto conserva el candidato y añade Review; esto
no basta para discriminar una figura tenue de un margen vacío.

La comparación de las 62 imágenes previas demostró que rc3 no cambiaba sus
salidas respecto a rc2. No certificaba todos sus límites ni cubría estos dos
originales. Los controles de borde exterior anteriores ejercitaban otra ruta.
Este diagnóstico añade reproducción exacta y puntos de contraste sobre los
originales; no se atribuye a un SVG ni al tamaño del corte un fallo anterior
que ya está en la cuadrícula de detección.

## Dirección de la corrección

- Contrastar también las divisiones proyectadas con evidencia local del original,
  preservando centros propios y diferencias reales entre casillas.
- Separar el marco inferior del estampado del final de la tela. La continuación
  de un periodo no demuestra otra fila, y la textura aislada no prueba un dibujo.
  Evitar retirar dibujos tenues legítimos por un umbral de contraste único.
- Separar las dudas de segmentación de los estados del corte que ve el usuario.
  Aplicar la guía de colores acordada con motivos concretos y sin cambiar la
  geometría ni la inclusión de avisos marcados en el SVG.

No se ha aplicado una corrección durante este análisis. Los datos y las capturas
están en [el informe visual](qa/diagnosis-20261116/index.html).
