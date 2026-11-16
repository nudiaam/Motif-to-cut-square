# Reglas de detección, colocación y exportación

Contrato vigente de la versión **0.13.4**, actualizado el 16 de noviembre
de 2026 con la guía de colores solicitada por el usuario. Los informes de rc2,
rc3 y 0.13.3 conservan sus criterios históricos; no son el contrato actual.
Las comprobaciones y sus límites están en [la ficha de versión](RELEASE_0_13_4.md).

## Casillas y composición

La unidad de trabajo es la casilla física de tela, con un fondo y una composición
propios. Un animal y sus accesorios no crean casillas diferentes. La textura,
los marcos, las sombras y la decoración del fondo no prueban otro dibujo.

La cuadrícula es una hipótesis que se debe contrastar con las divisiones impresas.
La rectificación sirve para proponerla; también se contrastan localmente las
separaciones proyectadas sobre los píxeles originales. Los vértices compartidos
mantienen coherentes las casillas vecinas y sus centros individuales.
No se sustituye una cuadrícula desigual por un paso medio para centrar cortes.

El final del estampado no es el final de la tela. Un marco de cierre observado,
con las divisiones perpendiculares terminando en él, puede descartar una extensión
estimada hacia un margen vacío. Un espaciado regular no basta para añadir filas.
Las filas parciales no autorizan repartir de nuevo las filas completas.

Una posición sin dibujo detectado queda como propuesta, sin corte automático ni
rectángulo en el SVG. Si una lectura local recupera tinta coherente respaldada
por dos lecturas, puede recuperar una composición tenue real. La posición de la
cuadrícula solo define dónde buscar; no demuestra por sí sola que exista un dibujo.
Los fragmentos pequeños dispersos de tejido no justifican un corte de relleno.

## Centro y dimensiones

El centro automático es el centro geométrico de su casilla. En una sección
proyectada cuadrangular se usa la intersección de las diagonales. No es el centro
del animal ni de su caja. Los tamaños elegidos no desplazan los centros ni se
reducen automáticamente para encajar. Un dibujo descentrado no arrastra el corte.

Los cuatro lados del rectángulo deben respetar su propia sección para considerarlo
contenido. Si el tamaño no cabe, se conserva y se señala el cruce. La edición
manual es una decisión explícita, con su geometría y sus avisos correspondientes.
Las guías manuales y proyectivas del usuario no se sustituyen por el afinado automático.

Una estimación de borde no se certifica como observación. Las respuestas del
límite de una copia de análisis, sin píxeles a ambos lados, no prueban un marco.
La incertidumbre se conserva en la evidencia y los detalles, sin añadir un margen
fijo de 1,3 mm a los límites reales del corte.

## Color del corte final

- **Verde, READY:** no se detecta cruce del rectángulo con su sección medida.
  No certifica la silueta completa, la precisión de una guía estimada o la máquina.
- **Morado, SECTION CROSSING:** el rectángulo cruza el límite de su sección.
  El motivo aparece en la lista y en el detalle, incluso si el cruce está dentro
  de la incertidumbre de la medición.
- **Rojo, IMPOSSIBLE:** geometría de rectángulo imposible, no finita o fuera de cama.
  Los cortes fuera de cama se omiten por la regla de cama, por lo que normalmente
  no llegan a mostrarse como rectángulos rojos.
- **Gris, EXCLUDED:** exclusión manual.

La duda de contorno, el posible recorte de un dibujo, la asignación incierta y
los solapes se conservan como notas del corte. No tiñen automáticamente toda la
colección. El recorte comprobado de un dibujo también sigue indicado en sus
notas; el color se reserva al criterio geométrico anterior. Tocar un borde sin
cruzarlo no produce morado por una banda adicional de incertidumbre.

El lienzo, la miniatura, la lista, los recuentos y el resumen previo a exportación
usan la misma presentación. Las cajas de análisis son detalles opcionales: se
muestran al seleccionar un corte o activar los detalles de la malla.

## SVG y omisiones

Un corte marcado dentro de cama puede exportarse con aviso. Por ejemplo, un corte
de 5 × 5 pulgadas en una sección de 4 × 4 permanece morado y exportable. La app
conserva exactamente las dimensiones y la posición mostradas. Esa excepción fue
solicitada por el usuario y no convierte el corte en contenido dentro de su sección.

Los rectángulos fuera de cama desaparecen del lienzo, la lista, la miniatura y el
SVG. Refrescar, cambiar el tamaño o deshacer no recrea posiciones sin dibujo como
cortes automáticos. Los cortes añadidos o movidos manualmente se conservan como
una elección del usuario; desmarcar un corte impide exportarlo.

El SVG mantiene origen, coordenadas y medidas físicas. La página declara la cama
de 36 × 24 pulgadas y margen cero. Zoom, Navegador, unidades y deshacer no deben
cambiar la geometría física exportada. La verificación de archivo no sustituye
la calibración cámara/máquina ni una prueba física de la Epilog.

## Comprobaciones de aceptación

Comprobar originales y variantes realistas: fondos diferentes, contraste bajo,
sombras, perspectiva, dibujos descentrados y accesorios, marcos finos, margen
sin imprimir y fotos parciales. La IA no garantiza pulgadas, casillas idénticas
ni el recuento pedido; comprobar el original antes de usarlo como referencia.

Separar estos criterios: propiedad y recuento de composiciones; centro y límites
de cada sección; esquinas y tamaño del corte; evidencia de composición frente
a textura; inclusión y coordenadas del SVG; invariancia de zoom/unidades/deshacer.
Las referencias manuales aproximadas llevan tolerancia declarada; la comprobación
de serialización y de los polígonos medidos mantiene precisión de subpíxel.

Un cambio de recuento exige revisar el original: conservar el número anterior
no justifica conservar un falso positivo, ni retirarlo justifica perder una
figura tenue. Los puntos de contraste y las referencias nunca entran como datos
del detector de producción.
