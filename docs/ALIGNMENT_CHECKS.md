# Alineación de casillas y comprobación física

## Panel infantil pastel del 23 de noviembre

En la imagen limpia de 1536 × 1024, con cortes de 4 pulgadas, la detección
anterior generó 23 cortes sueltos y una cuadrícula geométrica de 5 × 4 sin
confianza suficiente. La 0.14.2 comprueba transiciones repetidas entre fondos
impresos en ambas direcciones antes de recurrir a los centros de fragmentos.
Dos cargas de la misma imagen dieron 24 cortes en 6 × 4, con centros idénticos,
sin solapes ni cruces a 4 pulgadas. El resultado se conserva al reducir la foto
a la mitad o inclinarla un grado. El tamaño y la posición se conservaron en el
SVG. Con 5 pulgadas, quince contornos cruzan al menos un límite de casilla.
El encaje del dibujo y la calibración de cámara se comprueban por separado.

Las pruebas de calibración y de Epilog descritas a continuación corresponden al
trabajo local de la 0.14.1, del 22 de noviembre de 2026.

## Qué corrige el ajuste local

Una cuadrícula obtenida del espaciado de dibujos es una estimación. Para las rutas
`local_contrast` y `observations`, el programa contrasta separaciones internas con
transiciones sostenidas en los píxeles. Compara luminancia, color y distribuciones
locales de fondos estampados, mediante franjas independientes y dos suavizados.
Exige apoyo en varios segmentos y en ambos ejes; una figura aislada o franjas de
un solo eje no bastan. Las casillas vecinas comparten vértices.

Se mantienen el número de filas y columnas, la asignación de dibujos, los límites
exteriores no medidos, las guías explícitas y las dimensiones del corte. Los
centros se obtienen de las secciones refinadas. Cuando sigue habiendo límites
estimados, se conserva una nota de revisión. El ajuste no rellena casillas vacías.
Las fotografías grandes reciben una segunda comprobación sobre el original.

El mensaje de cuadrícula muestra figuras y casillas, sin afirmar que no queda
nada que revisar por tener el mismo número. Un corte verde sigue significando
ausencia de cruce medido, según el contrato vigente; no certifica calibración.

## Localizar el desajuste de la máquina

El paso **4 Export to Epilog** de Lalikul abre una vista previa de los cortes
marcados a través del controlador local **Epilog Engraver** de Windows. El
controlador y **Epilog Dashboard** forman parte de **Epilog Software Suite**.
El panel de revisión permite guardar un archivo con **Save SVG…**.
Usa el tamaño de cama seleccionado como tamaño de página del trabajo y comprueba
el formato aceptado por el controlador antes de enviar un solo contorno. Elige en
Dashboard el perfil de la máquina correspondiente y comprueba los contornos
sobre la imagen de cámara antes de enviar el trabajo al láser.

La prueba local con Dashboard 2.2.18.2 reprodujo el fallo con la impresión del
SVG desde Chrome. La selección rondaba las 100 × 100 pulgadas y solo aparecían
dos cuadrados, desplazados unas 16 pulgadas en X y 28 en Y. El controlador ofrecía
un papel predeterminado de 100 × 100 pulgadas.

Con el formato aplicado por Lalikul, Dashboard recibió cinco cuadrados vectoriales
en una cama de 36 × 24 pulgadas. Midió un conjunto de 34 × 22 pulgadas con centro
en X = 18, Y = 12. Se repitió con el original de grises desde **4 Export to Epilog**.
La ventana de Dashboard estaba oculta y apareció al recibir 24 cortes dentro de
la cama. El centro (17,838, 12,441) y el
tamaño del conjunto (31,370 × 21,078 pulgadas) coincidieron con las coordenadas
de Lalikul a la precisión mostrada por Dashboard. Los dos avisos de límite de
casilla se mantienen. Las pruebas usaron un perfil local sin láser conectado.

También se probó el SVG de grises guardado desde Lalikul en Dashboard y
Job Manager 2.2.18.2. Se comprobó que contenía 24 cuadrados de 5 × 5 pulgadas
dentro de una página de 36 × 24. Copiar el archivo desde el Explorador y pegarlo
con Ctrl+V en Dashboard no creó un trabajo. Ctrl+O no abrió un selector en
ninguna de las dos aplicaciones y el botón de importación de Dashboard abrió una
biblioteca de ajustes. Al arrastrar el archivo sobre la cama, Windows mostró el
cursor de prohibido.

El correo de Lalikul London compartido el 14 de noviembre en el chat
**Aclara cortes de borde y navegador** sí describe la transferencia: exportan
el archivo, Windows lo abre en el navegador de Microsoft y desde ahí pulsan
**Imprimir** para enviarlo a Epilog. En ese correo las líneas aparecían
desplazadas hacia abajo. El 16 de noviembre se resumió el flujo como
«exportar y pegar en Epilog», aclarando que no editan el SVG. Las pruebas de
pegado y arrastre literal no reproducen la ruta descrita en el correo.
El 23 de noviembre se repitió con Microsoft Edge 157.0.4341.60 y el mismo SVG
de cinco cuadrados. El trabajo llegó a Dashboard 2.2.18.2 con la zona de cama
de 36 × 24 vacía. **To Fit** mostró dos cuadrados vectoriales fuera de la cama;
el centro del primero se leía cerca de X = 33,97, Y = 39,98 pulgadas, frente a
X = 18, Y = 12 en el patrón. La selección del trabajo medía 99,640 × 99,790
pulgadas, coherente con el papel predeterminado de 100 × 100 del controlador.
Al repetir con el formato personalizado de 36 × 24 en horizontal configurado
en las preferencias del controlador, Edge envió los cinco cuadrados. Dashboard
mostró el conjunto en vertical, de 22 × 34 pulgadas con centro en X = 12,
Y = 18. Dos cuadrados quedaron fuera de la cama. Las dos pruebas reproducen
errores de posición en el recorrido del correo sin que intervenga la cámara.

En **Prepare image → Machine / work area → Save alignment check…**, guardar el
patrón para la máquina elegida. Se crean un SVG, una hoja CSV de medidas y unas
instrucciones en español e inglés. Usa el mismo exportador y las mismas unidades
de exportación que los cortes normales. No necesita una fotografía cargada y no
modifica los cortes actuales.

Para la cama Epilog de 36 × 24 pulgadas, el patrón tiene una página de
914,4 × 609,6 mm y cinco cuadrados de 50,8 mm de lado. Centros esperados desde
la esquina superior izquierda:

| Posición | X (mm) | Y (mm) |
|---|---:|---:|
| Superior izquierda | 50,8 | 50,8 |
| Superior derecha | 863,6 | 50,8 |
| Inferior izquierda | 50,8 | 558,8 |
| Inferior derecha | 863,6 | 558,8 |
| Centro | 457,2 | 304,8 |

1. Para comprobar una ruta externa de impresión, importar el SVG del patrón
   mediante ese mismo recorrido. Comprobar la página, el lado de cada cuadrado y
   sus posiciones en el programa receptor.
2. Conservar tamaño real al 100 %, el origen superior izquierdo y la posición de
   la página. Comprobar que el programa receptor no ajuste a página ni centre solo
   el conjunto de rectángulos.
3. Anotar las medidas reales en las columnas vacías del CSV, siempre en mm. Un
   desplazamiento constante orienta hacia el origen; un error creciente hacia los
   extremos, hacia escala; diferencias por zonas requieren estudiar giro o
   distorsión. Son indicios para diagnosticar, no correcciones automáticas.
4. Para comprobar la relación cámara/cama, fotografiar marcas físicas situadas en
   esas posiciones conocidas y comparar sus ubicaciones con las esperadas. Ajustar
   manualmente la foto hasta que encaje no demuestra una calibración correcta.

La comparación en el programa receptor y la comparación con marcas físicas
permiten distinguir importación/impresión de transformación de cámara. Una
referencia de cama vacía ayuda a separar tela y fondo; no es una calibración de
coordenadas físicas.

## Qué falta por comprobar

La coincidencia de los vectores en Dashboard queda comprobada en el perfil local.
Para cerrar el fallo comunicado por el taller, repetir con el panel de grises
en la máquina real y abrir los cortes con **4 Export to Epilog**. Sin mover
la tela entre la captura y la vista previa, guardar una captura de Dashboard
que muestre la cama completa, las reglas, el nombre del trabajo y los contornos
sobre la imagen de cámara. Comparar la vista en el centro y cerca de las cuatro
esquinas. Una captura de Lalikul por sí sola no muestra esta comprobación.

Si el fallo persiste, conservar también el **Save diagnostic package…** de esa
misma ejecución. El diagnóstico disponible asigna los 2340 × 1560 píxeles a toda
la cama de 36 × 24 pulgadas. No contiene puntos físicos medidos para verificar
esa asignación. Si el tamaño y el origen del trabajo ya coinciden, usar el patrón
y sus marcas medidas para cuantificar la diferencia cámara/cama antes de
aplicar una corrección de escala o posición.

- El original y el paquete de diagnóstico de la nueva prueba de flores. Las
  capturas con cuadrados y etiquetas no son entradas válidas para reproducir su
  detección. Una imagen generada tampoco demuestra que el fallo esté corregido.
- Medidas en la máquina real. No se han aplicado desplazamientos o escalas
  compensatorios sin esas medidas.
- Los cortes siguen siendo rectángulos paralelos a la cama. El refinado local
  mejora sus centros y la comprobación de cabida; no añade giro ni deforma un
  cuadrado de 127 × 127 mm para copiar una casilla irregular.

La verificación interna del SVG relee las coordenadas y dimensiones formateadas
que se serializan, y contrasta sus cuatro esquinas con los cortes. Esa prueba
no valida el comportamiento del programa receptor, el controlador ni la cámara.
