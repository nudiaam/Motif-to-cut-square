# Pruebas de entrega de Lalikul para Eugenio

23 de noviembre de 2026 · versión local 0.14.3

La mejor comprobación antes de entregar combina la repetición de los fallos
históricos con imágenes nuevas y una prueba en el equipo del taller. La parte
local permite revisar detección, geometría y exportación. La instalación, el
tiempo real y la superposición con la tela requieren el equipo de Eugenio.

[120 prompts listos para copiar](PROMPTS_TELAS_EUGENIO.txt), diez por cada
familia mencionada en los mensajes y capturas disponibles.

## Qué se reportó por tela

Se agrupan los nombres equivalentes, como Hearts y Corazones. «Animales» se
mantiene como el panel genérico que Eugenio distinguió de Cheeky Animals.
Los contadores históricos describen lo que mostraba la interfaz en aquel
momento. La columna de prueba indica qué evidencia hace falta para decidir
si la versión actual mejora el caso.

| Familia | Aviso o resultado de Eugenio | Qué probar |
|---|---|---|
| **Perros** · `PER` | Una captura mostró 30 cortes y solapes con una quinta fila parcialmente visible. Más adelante dijo que los perros se reconocían mucho mejor y los cuadrados eran casi perfectos. | Cuatro filas completas más un borde parcial, una quinta fila real y perros pálidos o descentrados. Medir número de motivos, solapes y recorte de orejas o colas. |
| **Pájaros** · `PAJ` | Una captura mostró 28 detecciones, con 24 posiciones centrales y cuatro propuestas arriba. Después los citó entre los paneles casi perfectos. | Eliminar marcas del margen sin perder ramas, hojas ni flores de un ave. Ejercitar fila parcial y cuadros con 7 × 3. |
| **Mariposas** · `MAR` | Eugenio las vio casi perfectas. La captura mostraba 24 cortes y diez avisos. El motivo de cada aviso histórico quedó sin confirmar. | Contrastar las alas y antenas con la caja del dibujo, y el cuadrado con su casilla. Ver cuándo una advertencia refleja un cruce real y cuándo queda una duda de contorno. |
| **Alfabeto** · `ALF` | Dos capturas mostraban 24 cortes. En la primera se veían descentrados respecto al conjunto letra y dibujo. Eugenio indicó que la segunda pasada se veía mejor. | Cada letra y su dibujo deben conservarse juntos. Repetir el mismo PNG, comparar el origen de la cuadrícula y comprobar por separado la redetección con guías manuales. |
| **Flores** · `FLO` | Una prueba mostró 26 propuestas donde se veían 24 ramos, con dos extras cerca de los bordes. Luego algunos cuadrados encajaban y otros no. En el aviso reciente, la primera identificación fue casi perfecta, la segunda falló y el corte físico de la primera prueba quedó desplazado. | Repetir con el PNG original de la segunda prueba cuando esté disponible. Mientras tanto, probar ramos sin marco, tallos tenues, motas de borde y repetición del mismo archivo. La colocación física se comprueba aparte. |
| **Navidad** · `NAV` | Pasó de 30 cortes en la primera prueba a 24 en una segunda de mejor aspecto. No se confirmó que los píxeles, ajustes y guías fueran idénticos. | Distinguir margen en blanco, quinta fila real y fila incompleta. Repetir el mismo PNG, incluidos copos con puntas finas. |
| **Corazones** · `COR` | Detectaba todos o casi todos según la prueba, pero los cuadrados no siempre encajaban. Una captura mostró 30 propuestas con una quinta fila parcial. Más adelante, los cortes invadían las casillas superiores. | Medir la primera y última fila y el borde superior de los cortes. Probar filas de alturas distintas y tamaños que quepan o que deban producir aviso. |
| **Gatos** · `GAT` | La captura mostraba 24 cuadrados visualmente bien distribuidos, todos morados. Falta confirmar la causa de los avisos con la entrada original. | Usar controles que caben, casos estrechos que sí deben avisar y dibujos con colas largas. Comparar cada aviso con una medida o con una duda de contorno. |
| **Transportes** · `TRA` | Reconocía la mayoría de los vehículos, pero los cuadros no encajaban. Una captura mostró 30 propuestas con quinta fila parcial. En otra versión aparecieron como «Excluded». En el aviso más reciente, algunos recorrían la casilla de al lado. | Probar fondo compartido, borde parcial y casillas estrechas. Conservar un único dibujo si un tren o una jirafa atraviesa dos casillas. Inspeccionar el motivo de cada exclusión y los avisos a tamaño fijo. |
| **Animales** · `ANI` | Eugenio los citó como uno de los paneles que ya se reconocían bien. Las pruebas internas con animales de poco contraste, marcos y accesorios reproducen dificultades relacionadas. | Mantener este panel como control frente a cambios de regla. Probar el marco superior, un animal tenue, los accesorios y un hueco deliberado. |
| **Cheeky Animals** · `CHE` | Se reportaron cortes «Excluded» y, después, cuadrados que invadían a vecinos. La captura reciente muestra 24 propuestas, cinco conflictos alrededor de la fila inferior. | Mirar la última fila corte por corte. Probar fondos contiguos y anchuras distintas. Sigue pendiente localizar el PNG limpio exacto de Eugenio. |
| **Grises** · `GRI` | Hubo falsas detecciones en el lateral. El paquete original registró 28 detecciones en 7 × 4, 24 activas y cuatro excluidas. Después, apreciaron una detección casi perfecta, aunque la captura aún mostraba desajustes y los contornos no se superponían a la tela al mandar el trabajo. | Repetir con `Analisis_Lalikul/source.png`, su referencia y sus ajustes. La 0.14.3 local da 24 en 6 × 4, con dos avisos de casilla a 5″. Usar también un caso de séptima columna real y comprobar este panel en la Epilog del taller. |

Fuentes: correos compartidos en **Analiza fallos de detección**, **Analizar
mejoras de detección**, **Diagnostica cortes y lentitud**, **Aclara cortes de
borde y navegador** y **Analiza comentarios sobre detección**. Consultar el
[análisis de las primeras capturas](ANALISIS_COLECCIONES_2026-10-12.md), el
[paquete original de grises](qa/customer-20261025/customer-real-20261101/README.md)
y las [pruebas actuales por familia](FABRIC_VALIDATION_0_14_3.md).

El panel infantil pastel que falló en la prueba interna de Nuria queda como
regresión adicional. Mostraba 23 cortes en 5 × 4 y su copia reducida caía a
8 cortes en 4 × 2. La 0.14.3 local da 24 en 6 × 4 en las dos imágenes. Conservar
ambos archivos junto a los originales del taller en la repetición de entrega.

## Incidencias que van más allá de la tela

| Incidencia | Qué sabemos | Qué falta para darla por comprobada |
|---|---|---|
| **Instalación y actualización** | Eugenio recibió un error al instalar y preguntó si debía descargar todo otra vez o sustituir archivos. | Probar el mismo paquete de entrega en una carpeta nueva de Windows 10 de 64 bits, comprobar el número de versión en la ventana y hacer un flujo corto de detección y exportación. Registrar el error exacto si reaparece. |
| **Tiempo variable y lento** | Comunicó unos 2:30 minutos en ciertos paneles y casi cinco en flores y grises. El informe original de grises midió 238,5 s de detector. Más tarde mencionó alrededor de 1:10, aceptable para ellos en ese momento. | Tres ejecuciones del original de grises y de la foto de flores disponible en su Windows, con versión y ajustes anotados. Comparar el tiempo desde el clic hasta los cortes y los tiempos del informe por fase. La mediana de 8,72 s de la 0.14.3 es de nuestra estación limitada a dos procesadores lógicos. |
| **Segundas pasadas distintas** | Alfabeto y Navidad mejoraron en la segunda prueba según el correo. Flores empeoró en el aviso posterior. | Usar los mismos bytes, versión y referencia de cama, anotar ajustes y confirmar si hubo nueva captura o guías manuales. Guardar el informe de cada pasada. |
| **Inspección y «Excluded»** | Preguntó qué significaba «Excluded» en Transporte y Cheeky Animals y pidió ampliar para ver el borde. | Comprobar con zoom y Navegador los cortes marcados y las razones de cruce. Un corte realmente fuera de cama se omite, un cruce de casilla se muestra como aviso y un corte desmarcado queda fuera del SVG. Verificar que zoom y cambio de selección actualicen la vista sin mover los cortes. |
| **Referencia vacía de cama** | Varias capturas informaban que la referencia no pudo aplicarse. El paquete de grises identifica la referencia usada en aquel intento. | Registrar si se aplica o se rechaza con una captura del mismo encuadre y posición. Medir la relación cámara/cama con puntos físicos conocidos. |
| **Desplazamiento en Epilog** | El correo de noviembre describe SVG → Edge → Imprimir → Epilog, con desplazamiento hacia abajo. Se reprodujeron errores de tamaño y orientación en ese recorrido. En la cola local, **4 Export to Epilog** conservó geometría y origen. | En su taller, revisar el patrón de cinco cuadrados y superponer los cortes del original de grises mediante **4 Export to Epilog** con la cámara y la tela en su sitio. Comprobar centro y cuatro esquinas. |

Fuentes: **Revisar error de instalación**, **Valorar si necesitan otro
ordenador** y los correos de detección y transferencia citados arriba.
[Actualización](ACTUALIZACION_2026-10-14.md), [mediciones de rendimiento](PERFORMANCE_0_13_4.md)
y [comprobación de escala y Epilog](ALIGNMENT_CHECKS.md).

## Cómo usar los 120 prompts

1. Generar **una imagen por prompt**. Copiar solo el párrafo bajo `PROMPT`.
   Usar `PER-01.png`, `PER-02.png`, etc., como nombres. Guardar el archivo
   generado en su resolución nativa. Si una comparación requiere una copia
   de 2340 × 1560, mantener el original y crear una copia documentada.
2. Antes de abrir Lalikul, inspeccionar cada imagen. Anotar filas, columnas,
   motivos completos, partes que van juntas y qué filas están cortadas.
   Marcar puntos testigo en ramos, accesorios, letras y alas. Cuando hay
   divisiones visuales, anotar las líneas o los vértices medidos. Si el
   resultado de generación incumple el caso, regenerarlo o usarlo como otro
   caso con su expectativa real. El recuento pedido al generador es un objetivo.
3. Guardar las imágenes `09` y `10` de cada familia para la comprobación final.
   Ajustar el detector, si hace falta, con las otras ocho y los originales
   históricos. Abrir las 24 de reserva una vez fijado el código candidato.
4. Para probar estabilidad, ejecutar el **mismo PNG tres veces** en Alfabeto,
   Navidad, Flores y el pastel ya reportado, con una de las pasadas en una
   sesión nueva. Registrar el estado de las guías. Usar copias del archivo
   para pruebas adicionales de reducción, giro y recorte conocidos, sin pedir
   al generador que vuelva a dibujar la escena para esas comparaciones.

## Criterios de entrega

| Comprobación | Se da por superada cuando… |
|---|---|
| **Detección** | Cada composición completa tiene un propietario, sin omisiones, duplicados o cortes inventados en márgenes y casillas vacías. Si una fila es parcial, quedan claras las filas completas que se pueden usar. |
| **Posición, dibujo y avisos** | Los centros y esquinas coinciden con las divisiones observadas. Los detalles del dibujo se comprueban por separado. A un tamaño que cabe se observa el margen esperado. Con un tamaño incompatible se muestra el aviso correspondiente, conservando la medida seleccionada. Probar 4″ y 5″ cuando aporten un caso distinto. |
| **SVG y Dashboard** | Las dimensiones de cama, el origen, el número de cortes marcados, sus coordenadas y el tamaño coinciden con Lalikul. Los descartados quedan fuera. La vista de Dashboard coincide con las marcas físicas medidas y con la tela en las esquinas y el centro. Acordar la tolerancia con el taller según el margen entre el corte y el dibujo. |
| **Estabilidad, instalación y tiempo** | Se repite la geometría con los mismos píxeles y ajustes, se ejecuta el paquete de entrega en el equipo previsto y el tiempo medido queda dentro del margen aceptado por Eugenio. |

Guardar por caso **ID de imagen, versión, tamaño de corte, resultado esperado,
resultado real, captura de revisión, informe y SVG**. Un caso pendiente de
medición física queda registrado como pendiente. La auditoría actual aporta
66 entradas y dos controles adicionales de la biblioteca. Los 120 prompts
de este documento son el plan de ampliación del corpus.

La prueba de taller se puede completar con un corte de muestra en un retal
con marcas medidas. Después de verificar la vista previa, el operador mide
dónde cayó el contorno real y comprueba su separación de las marcas. Así
quedan registradas tanto la vista de cámara como la posición del corte.
