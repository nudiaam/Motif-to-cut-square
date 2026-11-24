# Lalikul 0.14.4 · Primera tanda de telas generadas

## Comprobación de la cama vacía y de los ramos

La imagen gris de Eugenio es la referencia de cama vacía. Al cargarla como entrada se obtienen cero cortes. Una copia oscurecida al 42 % del brillo original también da una máscara vacía. Con un rectángulo de tela simulado sobre esa copia se recupera el interior de la pieza. El ajuste de exposición exige coincidencias del panal en varias zonas. En la foto de la tela de `Analisis_Lalikul` sigue siendo insuficiente la coincidencia. La aplicación lo indica y obtiene 24 cortes usando el borde visible de la tela.

En el PNG de los 24 ramos sin divisiones impresas, el ajuste inicial acumulaba 11,55 px de desplazamiento horizontal entre la primera fila y la cuarta. Al comprobar las extensiones de los motivos por columna, la cuadrícula puede colocar los cuatro centros en la misma vertical. A 5 × 5 pulgadas se obtienen 24 cortes, cero cruces y cero solapes. Los avisos de dibujo fuera del corte bajan de cuatro a tres.

Los tres avisos de los ramos se concentran en las columnas segunda, cuarta y quinta de la última fila. En la cuarta columna, los extremos detectados en las distintas filas van de x = 771 a x = 994. Para cubrirlos todos con el mismo centro horizontal hacen falta 223 px. El corte de 5 pulgadas mide 213,33 px en esta imagen.

La comparación con la versión inmediatamente anterior a este ajuste conserva los centros, la geometría exportada y los avisos geométricos de los 68 casos históricos y de los otros 12 originales de la tanda. En pantalla se distingue ahora entre un cruce que excede la incertidumbre de la guía y un cruce posible dentro de ese margen. A 5 pulgadas el abecedario beige muestra cinco posibles, el azul muestra dos que exceden el margen y ocho posibles, y la Navidad roja, verde y crema muestra seis posibles.

## Resultado tras la corrección del 24 de noviembre

Con la detección iniciada a **5 × 5 pulgadas**, los perros con sombra pasan de 16 a 24 y conservan exactamente los 16 centros anteriores. Las mariposas moradas pasan de 7 a 24 y las rosas de 6 a 24. La cuadrícula medida del abecedario coloca la A en x = 183,2 px frente a los 242 px anteriores. En cada original hay un centro dentro de cada una de las 24 casillas. Los otros nueve originales y los 68 casos históricos conservan la geometría, los avisos y los resultados de exportación a 4 y 5 pulgadas.

A 5 pulgadas permanecen 18 avisos de cruce en las mariposas moradas, 24 en las rosas y 24 en el abecedario negro. Los perros tienen cero cruces y diez avisos de dibujo recortado. La colocación física requiere verificación en la máquina. Los apartados siguientes documentan la situación previa y el diagnóstico que motivó la corrección.

El panel navideño con una franja inferior de tela blanca tiene 24 dibujos. El detector prolongaba las divisiones impresas hasta el borde de la tela y colocaba seis cortes en esa franja. Con el PNG original de 1536 × 1024 y cortes de 4 pulgadas, la corrección da 24 cortes. Los 24 centros anteriores se conservan, con un desplazamiento máximo de **0 píxeles**. Los 24 rectángulos exportados coinciden con sus rectángulos anteriores tanto a 4 como a 5 pulgadas.

La detección automática comprueba si la última línea impresa cierra el dibujo y si el margen está vacío en toda su anchura. Cuando la trama de la tela produce variaciones de brillo, exige además que las líneas verticales terminen en ese borde. La aplicación mide las casillas antes de retirar la franja para conservar sus posiciones.

## Reproducción con los PNG

Se utilizaron 13 originales distintos generados con IA, con la misma imagen y los mismos ajustes en cada comparación. «Antes» reproduce la ruta anterior desactivando la comprobación del margen. Se cargó cada PNG en la ventana de la aplicación y se compararon los cortes, sus centros, los avisos y los rectángulos del SVG. La columna de cruces cuenta las casillas en las que la aplicación señala que el corte atraviesa un límite. Un cero en esa columna puede coexistir con dibujos omitidos o recortados.

| Imagen | Cortes antes → 0.14.4 | Cruces a 4″ / 5″ en 0.14.4 | Qué se observa |
|---|---:|---:|---|
| Navidad con margen inferior blanco | 30 → 24 | 0 / 24 | Desaparecen los seis cortes en blanco. A 4″, siete dibujos conservan el aviso de que sobresalen del corte. |
| Navidad roja y marfil, cinco filas impresas | 30 → 30 | 0 / 30 | Se conservan los 30 centros y sus contornos. |
| Navidad roja, verde y crema, cuatro filas | 24 → 24 | 0 / 6 | Se reproducen los seis avisos de la captura a 5″. |
| Perros claros con sombra a la derecha | 16 → 16 | 0 / 0 | El contraste local acepta una cuadrícula de 4 × 4. Quedan fuera las dos columnas derechas. |
| Segundo panel de perros | 24 → 24 | 0 / 24 | La aplicación calcula una cuadrícula de 6 × 5 y presenta 24 cortes. |
| Mariposas de tamaños alternos con cenefa morada | 10 → 10 | 0 / 0 | El detector devuelve diez observaciones sueltas. La propuesta de 12 × 4 se descarta. |
| Mariposas con cenefa rosa, seis columnas | 6 → 6 | 0 / 0 | La cuadrícula aceptada es de 3 × 2. El estampado tiene 6 × 4. |
| Mariposas con borde morado, siete columnas | 21 → 21 | 0 / 16 | Se detectan las 7 × 3. Es un estampado distinto al de la captura con seis cortes. |
| Abecedario de letras negras | 24 → 24 | 0 / 24 | Los centros inferidos por contraste local están desplazados. Los 24 cortes de 5″ también se solapan. |
| Abecedario de letras beige | 24 → 24 | 0 / 5 | La detección de líneas impresas cuenta las 24 casillas. A 5″ aparecen cinco cruces. |
| Abecedario de letras de colores y líneas azules | 24 → 24 | 0 / 10 | Diez cruces a 5″, con ocho cortes en solape. |
| Ramos del detalle ampliado | 24 → 24 | 0 / 0 | Los centros de esta cuadrícula proceden del contraste local. Las diferencias de alineación visibles en la captura siguen pendientes. |
| Flores que la usuaria identifica como control | 24 → 24 | 0 / 0 | La aplicación utiliza otra cuadrícula, obtenida por la ruta visual. Se conservan los centros. |

Los originales de los dos casos con cenefa rosa y con ramos ampliados se identificaron cotejando el dibujo con la captura de la aplicación. En 12 de los 13 originales coinciden las detecciones, geometrías y avisos con la corrección activada y desactivada. El único cambio de resultado es el panel navideño con margen blanco.

El archivo histórico de 0.14.3 permite una segunda comparación independiente. En sus **68 casos**, coinciden el recuento, la geometría de detección, las dimensiones de la cuadrícula, los avisos y la geometría de salida a 4″ y 5″. Pasaron las **360 pruebas automáticas** del proyecto, incluidas las de margen superior e inferior, conservación de los centros y protección de una marca pequeña en la última fila.

En el abecedario negro se pueden distinguir dos efectos en la propia imagen. En la primera fila, el centro que propone la aplicación para la A está en x ≈ 242 px. Las líneas laterales visibles de esa casilla sitúan su centro en x ≈ 181 px. Además, con la cama configurada a 36 × 24 pulgadas, 5 pulgadas equivalen a unos 213 px en este PNG. La altura visible de la primera casilla ronda los 195 px. Corregir el desplazamiento horizontal seguiría dejando un corte de 5″ demasiado alto para esa casilla.

## Qué queda por medir en la máquina

Los perros y las dos mariposas muestran fallos de recuento reproducibles en píxeles. El abecedario de letras negras muestra que contar bien tampoco garantiza que el centro esté bien situado. Para evaluar la precisión física conviene usar una imagen original de la cámara de la Epilog, una referencia de la cama vacía con el mismo encuadre y la medida real de una casilla de la tela. Eso permite comparar el desplazamiento en la imagen con el observado en milímetros.

## Diagnóstico causal del 24 de noviembre

Las pruebas partieron de los originales, con la aplicación configurada a 5 × 5 pulgadas. Las modificaciones de imagen descritas se aplicaron únicamente a copias de diagnóstico.

- **Perros con sombra.** La ruta de fondo compartido estima un único color de tela. En muestras de los huecos entre filas, el umbral utilizado para separar tinta y fondo marca aproximadamente el 0 % de los píxeles en la zona clara y el 89–100 % en dos muestras de la zona sombreada. Así se pierde la separación entre perros y tela. Once lecturas coinciden en una cuadrícula parcial de 4 × 4. La ocupación del 94 % se mide dentro de esa propuesta, por lo que omitir dos columnas exteriores apenas la penaliza. Al reflejar la imagen, las ocho omisiones siguen a la sombra. Una compensación simple de brillo también produjo detecciones adicionales erróneas.
- **Mariposas con cenefa morada.** Las dos lecturas de marcos encuentran seis columnas. En vertical predomina una repetición de dos filas, y la lectura de color puntúa las cuatro filas reales en 0,21, por debajo del mínimo de 0,26. La alternativa de contraste oscuro cuenta detalles repetidos y propone 12 × 4, que se descarta. Quedan 14 candidatos sueltos. Al centrar los cuadrados en ellos, cuatro quedarían fuera de la cama a 4″ y siete a 5″. Esto explica los 10 cortes de la captura y los 7 al iniciar a 5″. Al enmascarar los adornos de las esquinas de las casillas en una copia, se recuperan 24 cortes en 6 × 4.
- **Mariposas con cenefa rosa.** Las cuatro filas obtienen 0,244 y 0,264 en las dos escalas de color. Solo una supera 0,26. Al fallar esa comprobación, la alternativa calcula la cuadrícula a partir de los bordes y del número de candidatos iniciales, que en este caso son solo dos. La propuesta 3 × 2 obtiene 0,457 y la 6 × 4 obtiene −0,519. La comprobación posterior acepta 3 × 2 aunque los dos candidatos ocupen solo dos de sus seis casillas y ninguno esté alineado con un centro.
- **Abecedario negro.** La propuesta inicial 6 × 4 tiene apoyo en los bordes, pero queda fuera de la selección. Gana la lectura del color, que sigue a las ilustraciones situadas a la derecha de las letras. El centro de la A queda en x = 242 px. Al reflejar el contenido de cada casilla y conservar sus separadores, se elige otra lectura y el centro pasa a x = 192 px. La prueba distingue el sesgo hacia el dibujo del problema de tamaño: el lado de corte de 213 px sigue excediendo la altura de esa primera casilla.
- **Ramos ampliados.** La propuesta final se apoya en el fondo y la repetición de los 24 ramos. La geometría inicial de 6 × 4 tiene apoyo nulo en líneas de separación. La cuadrícula ajustada desplaza sus centros 3,85 px a la izquierda por fila, unos 11,55 px entre la primera y la cuarta. Esto explica el escalón que se ve al ampliar. La imagen por sí sola no establece dónde quería la usuaria el centro de cada ramo.
- **Avisos en casillas impresas.** El cruce se evalúa contra el polígono estimado de cada casilla. En la K beige, la esquina inferior derecha del polígono queda a y = 510 px y una lectura independiente del borde inferior visible lo sitúa cerca de y = 516 px. El cuadrado llega a y ≈ 511 px. La aplicación registra el cruce geométrico dentro de su incertidumbre de medida. La altura del abecedario negro, en cambio, es insuficiente incluso centrando el corte.
- **Al aplicar la incertidumbre de las guías a 5″**, ninguno de los cinco cruces del abecedario beige ni de los seis del panel navideño rojo, verde y crema supera ese margen. En el abecedario azul sí lo superan dos de los diez.
- **Referencia de Eugenio.** Al comparar la foto de la tela (`source.png`) con la foto gris de la cama vacía (`reference.png`), el emparejador encuentra tres correspondencias iniciales de textura. Necesita 16 para intentar estimar el movimiento. Aproximadamente el 0,002 % de los píxeles supera el criterio conjunto de textura y luminosidad, frente al 8 % requerido, y ninguna zona supera el mínimo local. La tela ocupa casi todo el encuadre y el panal visible es mucho más oscuro que en la referencia. Al igualar las resoluciones también falla el emparejamiento. Estos datos explican el rechazo, pero no permiten atribuirlo con certeza a un movimiento de cámara o a un cambio de iluminación.
