# Análisis de las colecciones remitidas por Eugenio

**Actualización posterior al análisis:** se han implementado mejoras de diagnóstico,
revisión y respuesta de la interfaz, y generado Alfabeto/Navidad para pruebas.
Consultar [cambios, verificación y límites](qa/customer-improvements/README.md).
El texto siguiente conserva el diagnóstico previo a esa implementación.

12 de octubre de 2026. Código local: commit `e1849af`; detector
`2026-09-23-accessory-ownership-corroboration`.

## Conclusión

Hay margen para mejoras generales. Las capturas no justifican mantener un
algoritmo independiente por colección. Sí conviene usar cada colección como
prueba de una dificultad reutilizable: fondos repetidos, paneles de fondos
distintos, composiciones de varias partes, márgenes y filas parcialmente visibles.

El análisis previo adaptativo ya está implementado y activo por defecto. La
siguiente etapa debe reforzar su selección y validación, no añadir otro paso
equivalente ni asumir que repetir la detección entrena el programa.

Este documento es un diagnóstico y una propuesta; no se ha modificado la
aplicación. Las once capturas permiten observar sus resultados, pero no reproducir
con fidelidad las entradas: incluyen cuadrados, etiquetas y, en ocasiones, parte
del panel fuera de la vista. No se han procesado como fotografías de prueba.
Tampoco está confirmada la revisión instalada en el ordenador de Eugenio.

## 1. Qué muestran las capturas

Numeración según el orden de los once adjuntos. «Listos» y «problemas» son los
contadores de la interfaz, no una evaluación manual de exactitud.

| Colección / captura | Observación | Interpretación y límite |
| --- | --- | --- |
| Perros, 1 | 30 cortes, 30 problemas; cuadrícula 6×5; solapes y quinta fila parcialmente visible. | Separar la geometría, el encaje de cuadrados de 5 pulgadas y el tratamiento de filas parciales. No afirmar que sobran seis motivos: parte de la quinta fila contiene impresión real. |
| Pájaros, 2 | 28 cortes; 24 sobre una cuadrícula 6×4 y cuatro adicionales arriba; 14 listos. | La propia interfaz señala cuatro regiones exteriores/duplicadas. Revisar márgenes y asignación de fragmentos; conservar ramas y accesorios que sí pertenezcan a un motivo. |
| Mariposas, 3 | 24 cortes, cuadrícula visualmente bien distribuida; 14 listos y 10 problemas. | La colocación parece buena; los avisos morados requieren conocer sus motivos concretos. No prueban diez errores geométricos. |
| Alfabeto, 4 y 5 | 24 cortes en ambos. La primera cuadrícula está desplazada respecto al conjunto letra+dibujo; la segunda lo encuadra mejor. Los 24 siguen morados. | Hipótesis: compiten las posiciones de letras, dibujos y paneles. Hay que validar la composición completa y el origen de la cuadrícula, además del recuento. No se ha demostrado que ambas entradas fueran idénticas. |
| Flores, 6 | 26 cortes frente a 24 posiciones centrales; un corte adicional a la izquierda y otro abajo a la derecha. | Revisar regiones del borde, duplicados y propiedad de componentes. Un recuento alto no demuestra mejor detección. |
| Navidad, 7 y 8 | De 30 cortes con 30 problemas a 24 con 10 listos y 14 problemas. La segunda cuadrícula sigue mucho mejor los paneles. | Cambio importante de interpretación de la distribución. Verificar entrada, ajustes y ruta de detección antes de atribuirlo a una segunda pasada beneficiosa. |
| Corazones, 9 | 30 cortes, 13 listos; quinta fila parcialmente visible y cortes rojos inferiores. | Comprobar qué parte se quiere cortar y qué queda dentro de la cama. No confundir límite de la vista, de la fotografía, de la tela y de la cama. |
| Gatos, 10 | 24 cortes; distribución visualmente coherente, todos morados. | Prioridad: obtener razones de revisión y comprobar la extensión completa. Posible exceso de avisos, todavía no confirmado. |
| Transportes, 11 | 30 cortes, ninguno listo; cuarta fila completa y quinta parcial, con cortes inferiores rojos. | Separar fondo de estrellas, composición, filas parciales y viabilidad física. No basta con reducir el número de cortes a 24. |

En todas se lee que la referencia de cama vacía no pudo hacerse coincidir con
la cama visible y se utilizó el borde de tela. Es un dato común útil; no demuestra
que sea la causa de todos los fallos. El rechazo de una referencia incompatible
es una protección correcta. Conviene obtener una referencia del mismo encuadre
y configuración antes de cambiar los criterios de registro.

El oscurecimiento inferior de una captura tampoco demuestra por sí solo una
sombra de cámara: puede intervenir la previsualización o el límite visible.

## 2. Qué hace realmente el paso que «piensa»

Código principal: `app/imaging/detector.py`, `scene_profile.py`,
`detection_plan.py`, `region_analysis.py` y `extent_review.py`.

1. `detect_with_layout` obtiene un perfil global, intenta registrar la referencia
   de cama y busca soporte de tela. Cuando corresponde, construye una vista
   alternativa de iluminación conservando el original.
2. `_detect_layout` reúne propuestas por divisiones impresas, repetición de
   dibujos, cámara, distribución geométrica y cambios de color. `choose_grid`
   compara ocupación, alineación, divisiones y evidencia fuera de la propuesta,
   con comprobaciones entre rutas.
3. `plan_zones` mide fondo local, detalle y apoyo para compensación de iluminación.
   `detect_in_grid` intenta segmentación por paleta local; si no funciona, prueba
   varias sensibilidades. Hay una ruta adicional de fondo compartido.
4. `_coordinate_appearance` permite contrastar la interpretación inicial con
   otras evidencias y reanalizar zonas necesarias. Parte de los resultados locales
   ya se reutiliza: no todo se calcula siempre desde cero.
5. `finalize_compositions` agrupa componentes y `review_extents` revisa toda la
   casilla y contexto, para buscar contenido que la caja inicial podría omitir.
6. La interfaz ajusta los cortes a la distribución, añade posiciones inferidas
   donde faltan detecciones y comprueba encaje, solapes y límites físicos.

Esto es adaptación por evidencia visual, mediante OpenCV y reglas; no identifica
el nombre de la colección ni aprende al volver a cargarla. El perfil global
actual también tiene una función de diagnóstico: no es un clasificador semántico
que elija por sí solo toda la estrategia.

## 3. La segunda pasada

En el código revisado, cargar una imagen reinicia detecciones, cuadrícula y
confirmaciones. Detectar de nuevo normalmente vuelve al análisis automático.
Hay una excepción deliberada: con guías confirmadas se entra en
`detect_in_current_grid`, que puede usar otra ruta. Modificar escala, área mínima,
sensibilidad, unión de partes o referencia también cambia el problema.

Se han ejecutado tres pasadas por cada una de tres imágenes limpias existentes:
dos en la misma instancia y una en una instancia nueva, con ajustes fijos y la
referencia incluida. Los resultados completos y los diagnósticos han sido
idénticos en las tres pasadas de cada caso; las imágenes no se modificaron.

| Imagen de control | Resultado en cada pasada | Candidatos con aviso de extensión |
| --- | --- | ---: |
| Perros rectos generados | 24, cuadrícula 6×4 | 4 |
| Floral recuperado | 24, cuadrícula 6×4 | 0 |
| Transportes con fondo compartido | 24, cuadrícula 6×4 | 1 |

Evidencia: [resultados y hashes](qa/customer-review-20261012/repeatability.json) y
[script reproducible](qa/customer-review-20261012/repeatability_probe.py).
Los controles no son las fotografías de este correo; no descartan un fallo de
estado o de estabilidad específico de Alfabeto/Navidad ni cubren el flujo completo
de interacción del cliente. Los contadores de esta tabla son del detector, no
los «listos» de la interfaz.

Para resolver el incidente hacen falta la fotografía original y el informe JSON
de cada pasada, junto con los pasos entre ambas. La primera comparación debe
ser identidad de píxeles, ajustes, versión, referencia y guías confirmadas.

## 4. Mejoras generales priorizadas

### A. Reproducibilidad y diagnóstico

La aplicación ya tiene `Show advanced detection settings` →
`Save detection report…`, también antes de confirmar la detección.
El informe incluye revisión, ajustes, hipótesis, referencia, cajas y posiciones.
Ampliarlo con hash del original y de la referencia, versiones de bibliotecas,
estado automático/guías confirmadas y tiempos por fase. Un paquete de diagnóstico
con original más JSON reduciría mucho el intercambio de pantallazos.

Criterio: una misma entrada y configuración producen el mismo resultado;
cualquier cambio de ruta queda identificado. La prueba debe incluir la interfaz,
no solo llamadas directas al detector.

### B. Estabilidad de cuadrícula y composición

Reforzar la comparación del origen y del paso de las cuadrículas, no solo sus
filas/columnas y ocupación. Alfabeto puede tener 24 posiciones regulares sobre
letras y seguir recortando mal los dibujos. Validar conjuntamente letra y dibujo,
o varios personajes, como componentes de la misma composición cuando lo apoye
la evidencia de panel y contenido.

`choose_grid` actualmente acepta la primera propuesta que queda a menos de 0,06
del máximo, según el orden de las rutas. Es una política de desempate, no una
prueba de incertidumbre resuelta. Para alternativas con geometrías distintas y
puntuaciones próximas, conviene conservar la duda, comprobar solo las zonas que
las diferencian y registrar el motivo final. Evaluar también pequeñas variaciones
de resolución y encuadre para detectar saltos de fase.

Esto amplía el coordinador existente; no requiere una regla «si Alfabeto…».

### C. Márgenes y filas parciales

Separar soporte físico de tela, área impresa, composición completa y área
seleccionada para cortar. Ya se preservan regiones exteriores para no perder
dibujos legítimos; añadir evidencia para clasificarlas como margen, fragmento,
composición adicional o caso incierto, en vez de borrar todo lo exterior.

Una fila parcialmente visible debe quedar claramente identificada. No inventar
su contenido completo ni excluirla silenciosamente. Si el original contiene la
fila completa pero el cuadrado queda fuera de cama, el problema es físico.
No imponer 6×4 a estas colecciones: puede existir una quinta fila real.

### D. Validación y comunicación de avisos

Separar en el resumen: solape, fuera de cama, posible recorte del dibujo,
composición dudosa y posición inferida sin dibujo detectado. El morado actual
agrupa recorte, razones de revisión y problemas de asignación
(`app/ui/cut_status.py`). Un porcentaje alto de confianza de cuadrícula no
equivale al porcentaje de dibujos completos ni a cortes listos.

La revisión de extensión ya conoce la paleta del fondo, pero sigue basándose
en contraste y conectividad. Fondos de puntos, estrellas o rayas pueden seguir
siendo ambiguos. Mejorar el modelo de textura y compartir evidencia solo entre
casillas con fondos comparables; medir si bajan falsas alarmas sin aumentar
omisiones. No eliminar los avisos para obtener más verdes.

### E. Escala física y referencia

Los cuadrados son de 5×5 pulgadas en todas las capturas. Si la separación física
entre centros es menor, habrá solape aunque se hayan encontrado bien los dibujos.
`CoordinateMapper` coloca por defecto la imagen conservando proporciones dentro
de la cama: no es una calibración física obtenida de la tela. La rectificación
interna de cámara para detectar no sustituye la conversión física de exportación.

Comprobar encuadre completo, dimensiones de máquina, colocación de imagen y una
medida conocida. Mostrar la separación estimada frente al tamaño solicitado.
No reducir automáticamente los cuadrados para mejorar los contadores.

### F. Rendimiento

La mayor complejidad añade trabajo, pero no obliga a aceptar cualquier demora.
La ruta de contraste compara hasta seis escalas y cinco umbrales por canal;
la alternativa local puede probar cinco sensibilidades por zona. La detección
se ejecuta de forma síncrona desde la ventana y mantiene ocupada la interfaz.

El [perfil local](qa/customer-review-20261012/profile.txt), sobre transportes,
registró aproximadamente 3,35 s: 1,64 s en `_detect_layout`, 0,88 s en coordinación
de apariencia y 0,42 s en análisis de iluminación. Son tiempos inclusivos; no
deben sumarse con los de sus funciones hijas. Es una observación orientativa,
con otras pruebas ejecutándose durante parte de la sesión, no un benchmark
aislado ni una predicción para el ordenador del cliente.

Priorizar medidas por fase, reutilización de transformaciones/perfiles de imagen,
presupuesto de alternativas según incertidumbre y reanálisis de zonas dudosas.
Llevar el cálculo a un trabajador con progreso y cancelación mejora la respuesta
de la interfaz, aunque no reduzca por sí solo el tiempo de cálculo. Cualquier
salida anticipada debe conservar la capacidad de cuestionar una cuadrícula
aparentemente completa pero incorrecta.

## 5. Qué pedir a Eugenio y cómo continuar

Primera entrega de datos, centrada en los casos que más discriminan causas:

- Original limpio de Alfabeto y Navidad, más los informes de ambas pasadas.
  Aclarar si repitieron Detectar, volvieron a pegar, recapturaron en Epilog o
  ajustaron/confirmaron la cuadrícula.
- Originales de Pájaros y Flores para investigar detecciones del margen.
- Un caso con quinta fila y confirmación de qué filas quieren cortar.
- Una imagen de cama vacía del mismo equipo/encuadre; medidas reales de los
  paneles y tamaño deseado de corte. El JSON ayudará a comprobar la revisión.

El siguiente ciclo debería reproducir primero estos originales y fijar resultados
esperados: una composición por corte, centros correctos, letras/accesorios
incluidos, tratamiento explícito de filas parciales y viabilidad del corte de 5 pulgadas.
Después, aplicar mejoras comunes en selección, márgenes y validación, conservando
las colecciones anteriores como controles.

Medir por separado omisiones, duplicados, desplazamiento de centros, recorte de
partes del dibujo, falsas alarmas y tiempo. Un total de 24 no basta: 23 motivos
correctos más un falso positivo también suman 24. Reservar alguna colección o
nueva captura para validar sin ajustar sobre ella.

Los perfiles específicos de colección tienen sentido como opción posterior si
la producción repite paneles estables: guardar distribución y preferencias
confirmadas, verificar su correspondencia en cada fotografía y volver al modo
automático ante cambios. No guardar coordenadas fijas para una tela que se mueve,
ni introducir excepciones por nombre sin demostrar primero una necesidad real.

## 6. Alcance de las comprobaciones

La auditoría usa el código local y las once capturas suministradas. Se han añadido
este informe, un script de sondeo y su evidencia; no se han cambiado algoritmos,
ajustes por defecto, interfaz ni exportación.

El entorno local es Python 3.12.13, OpenCV 4.14.0 y NumPy 2.5.2. `requirements.txt`
solicita NumPy 2.5.3 para Python 3.12: esta diferencia queda registrada y no permite
suponer identidad con la instalación del cliente. Durante los ensayos OpenCV
emitió un mensaje de imposibilidad de crear la cola OpenCL; el sondeo completó
sus resultados. No se ha atribuido a ello el problema del cliente.

Han pasado **23 pruebas existentes**: 16 de análisis adaptativo/coordinación y
7 de diagnósticos de interfaz. Resultados en
[pruebas del detector](qa/customer-review-20261012/core-tests.txt) y
[pruebas de interfaz](qa/customer-review-20261012/ui-tests-workspace-temp.txt).
No se ha ejecutado toda la batería del repositorio ni estas pruebas certifican
las nuevas colecciones del correo.

La ejecución inicial de interfaz quedó esperando un diálogo de error al escribir
un informe en el directorio temporal restringido del entorno de ejecución.
El sondeo del error identificó `Permission denied`; el
[registro con límite de tiempo](qa/customer-review-20261012/ui-tests.txt)
sitúa la espera en `save_detection_report`. Al usar un directorio temporal
dentro de este proyecto, las siete pruebas terminaron correctamente sin cambiar
código de aplicación ni pruebas. Es una incidencia del entorno de la auditoría,
no evidencia de un error de detección en el equipo del cliente.
