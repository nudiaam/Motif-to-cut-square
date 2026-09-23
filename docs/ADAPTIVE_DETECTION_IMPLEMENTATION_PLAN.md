# Plan de análisis previo y detección por zonas

Plan aprobado el 21 de septiembre de 2026. **Actualización del 22 de septiembre:
primera implementación activa**, con 176 pruebas correctas. Consultar el
[informe de implementación, resultados y límites](qa/adaptive-planning/README.md).
El resto de este documento conserva el diseño aprobado: no todas sus propuestas
experimentales están implementadas; el informe distingue las piezas activas de
las pendientes. Las referencias de resultados del día 21 son históricas.

## 1. Corrección del planteamiento

«Uniformidad del fondo» no basta para decidir cómo detectar. Deben medirse por
separado:

1. **Diferencia entre fondos de casillas vecinas.** Puede revelar muy bien la
   cuadrícula, aunque todos los fondos sean estampados y diferentes.
2. **Separación entre dibujo y fondo dentro de cada casilla.** Puede ser débil
   incluso cuando los límites de la casilla son inequívocos.
3. **Variación de iluminación.** Una sombra puede oscurecer simultáneamente el
   fondo, el dibujo y varias casillas sin cambiar la distribución del panel.

Además, fondo compartido no significa fondo liso: transportes sobre estrellas es
un fondo compartido con textura. Fondos diferentes tampoco implican dificultad:
los corazones aprovechan precisamente sus diferencias entre casillas.

La política común será **una composición por corte**, admitiendo accesorios
desconectados y composiciones que ocupan varias casillas. Lo adaptable será la
forma de obtener evidencia, no el significado de una composición.

## 2. Casuísticas observadas

El [inventario y la galería](qa/image-audit/README.md) reúnen 55 imágenes de usuario
distintas por bytes recuperadas de conversaciones accesibles. Incluyen versiones
del mismo panel, capturas de controles y errores; no son 55 colecciones ni 55
fotografías limpias. Se revisan también las seis imágenes generadas ya existentes.

| Caso y evidencia | Qué ayuda | Qué puede fallar | Tratamiento previsto |
| --- | --- | --- | --- |
| Corazones, I49/I51 | Cambio de color o patrón entre casillas | Textura del corazón confundida con fondo | Grid por límites; fondo y textura locales para revisar extensión |
| Animales con fondos distintos, I30/I44/I54 | Separaciones repetidas entre paneles | Grid parcial aceptado como completo; dibujos pequeños | Comparar hipótesis con toda la imagen, incluidas filas exteriores |
| Pastel tenue, I31/I32/I36–I39/I45 | Repetición espacial aunque el contraste sea bajo | Patas claras y dibujos enteros omitidos | Grid por varias señales; segmentación local conservadora; comprobar casillas enteras |
| Transportes sobre estrellas, I07/I40/I46/I50/I52/I55 | Repetición de centros, algunos contornos fuertes | Estrellas, borde y sombra inferior convertidos en cortes | Fondo compartido si se confirma; iluminación separada; propiedad por composición |
| Perros, I47 y fixture recta | Casillas de distintos fondos | Cuerpo y cabeza de contraste diferente; fondo del vecino contaminando el recorte | Semillas de fondo de la propia casilla; contexto vecino identificado, no asumido igual |
| Pájaros con ramas, I53 | Distribución regular y algunos núcleos fuertes | Patas, ramas, flores o cola separados del cuerpo | Agregar evidencia de toda la composición; preservar estructuras finas |
| Floral sobre crema, I05/I42/I48 y fixture generado | Repetición espacial | Hojas pequeñas, tinta tenue, manchas de fondo | Fondo local o compartido según evidencia; textura y escala de detalle |
| Siluetas rellenas de flores, I18/I19/I27 | Límites de panel y contorno exterior | Flores internas producen múltiples manchas | Agrupación de composición; no usar cada componente como corte |
| Patchwork denso, I23/I24 | Múltiples cambios de fondo | Casillas pequeñas, motivos pequeños, alta textura; tamaño físico del corte excesivo | Inferir dimensiones sin imponer 6×4; separar detección de viabilidad del cuadrado |
| Transporte con jirafa, I33–I35 y fixture generado | Regularidad de las demás composiciones | Un motivo ocupa dos posiciones del grid | Evidencia de continuidad y propiedad común; no duplicar corte |
| Márgenes, cama y pliegues, presentes en varias familias | Referencia de cama cuando esté registrada | Borde físico usado como límite impreso | Soporte de tela separado de extensión impresa; no extrapolar filas al margen vacío |

Las capturas con superposiciones sirven para identificar problemas y resultados
históricos. No son entradas válidas para medir precisión del detector: sus líneas,
etiquetas y oscurecimiento de previsualización alteran los píxeles. En particular,
el negro de la previsualización fuera del corte no demuestra una sombra de cámara.

## 3. Qué existe y qué falta

`app/imaging/detector.py` ya reúne varios procedimientos: segmentación global,
grid visual, repetición de dibujos y análisis del panel fotografiado. Sin embargo,
`_detect_layout` los acepta mediante condiciones y retornos sucesivos. No existe
un perfil común que compare la calidad de todas las hipótesis antes de elegir.

`detect_with_layout` calcula soporte de tela antes del análisis del layout. Puede
recortar el área de análisis o sustituir píxeles exteriores. El plan nuevo debe
conservar también la imagen completa y la incertidumbre del soporte: una máscara
dudosa bajo sombra no puede borrar la evidencia que después necesita el grid.

Los problemas reproducidos en el diagnóstico anterior siguen pendientes:

- En el caso de perros rectos, 13 de 24 llamadas locales abandonan GrabCut por no
  encontrar fondo seguro en el borde del contexto ampliado. Un fondo diferente
  en la casilla vecina puede desencadenar esa condición.
- Retirar esa condición en una prueba controlada recupera puntos de cuerpo y
  patas, pero también puede incorporar fondo vecino. No es una solución completa.
- La revisión de extensión parte de la caja ya detectada. Ocho de nueve puntos
  testigo omitidos quedaban fuera de su ventana de revisión.
- Un dibujo completo sobre rayas dispara un aviso que no aparece para la misma
  geometría sobre fondo liso: la validación también necesita entender el fondo.

Fuentes: `tests/diagnose_remaining_detection.py` y
`docs/qa/remaining-diagnosis/diagnosis.json`. No se infiere de estos casos que todas
las omisiones de todas las capturas tengan exactamente la misma causa.

## 4. Proceso propuesto al pulsar Detectar

### A. Apariencia global, sin eliminar información

Crear una copia reducida para medir color, textura, bordes y variación luminosa;
conservar la imagen original y las transformaciones de coordenadas. Obtener un
soporte probable de tela, otro incierto y evidencias de fondo de máquina. La
ausencia de evidencia no equivale a fondo seguro.

Extraer perfiles de cambio horizontal y vertical en varias franjas. Los cambios
de fondo entre casillas deben mantenerse en distintas franjas; las rayas finas
del estampado y las flores internas deben contrastarse con la escala del panel
y con la distribución de composiciones. También recoger centros repetidos cuando
no haya separaciones visibles.

### B. Grid: comparar propuestas antes de elegir

Reutilizar `visual_grid`, `pattern_grid`, `camera_panel` y `logical_layout` como
productores de propuestas. Compararlas mediante evidencias comunes: apoyo de
divisiones en distintas franjas, regularidad, ocupación, motivos alineados fuera
del límite propuesto y contradicciones con los bordes impresos.

No comparar ciegamente sus actuales valores de confianza: son puntuaciones
heurísticas de procedimientos distintos, no probabilidades calibradas.

El contraste entre fondos tiene aquí prioridad cuando explica bien el panel.
Con fondo compartido, gana importancia la repetición de composiciones. Un caso
mixto combina ambas evidencias. Ninguna propuesta se valida únicamente porque
se ajusta al perímetro de la tela o porque produce el recuento más alto.

Si no hay diferencia clara entre propuestas, conservar incertidumbre y resolver
solo las regiones necesarias para discriminarlas. La falta de una división no
justifica inventarla. Las guías confirmadas por el usuario siguen siendo una
restricción explícita.

### C. Características por zona

Con un grid provisional, medir cada casilla con contexto alrededor:

- Distribución de colores de fondo: puede haber varios colores, no solo una media.
- Parecido de esos fondos entre casillas, para compartir información solo cuando
  realmente corresponda. Una casilla distinta conserva su propio modelo.
- Contraste del posible dibujo respecto al fondo local y estabilidad al variar
  moderadamente el umbral.
- Textura repetida de fondo frente a estructura del dibujo, en más de una escala.
- Detalles finos, fragmentación, contacto con límites y posible continuación en
  una casilla vecina.
- Iluminación y fiabilidad de las muestras utilizadas.

Las muestras de fondo no serán automáticamente todos los píxeles del borde. Se
buscará consenso entre varias bandas y zonas de baja variación, excluyendo
posibles trazos. Si no hay muestras fiables se marcará esa limitación; no se
forzará una estimación inventada.

### D. Sombras: corrección condicionada, no aclarado general

Estimar variaciones amplias de luminancia a partir de muestras de fondo fiables,
comparando casillas con fondo parecido. Buscar coherencia espacial: una sombra
inferior puede atravesar varios motivos y fondos sin crear una nueva fila.

El oscurecimiento aislado de un panel azul o de un corazón negro no basta. La
luminancia, la cromaticidad, los bordes y el patrón aportan indicios conjuntos;
ninguno por sí solo distingue siempre tinta y sombra. Se deben contemplar tanto
gradientes suaves como franjas con borde duro.

Solo donde exista evidencia suficiente, producir una segunda vista con
compensación luminosa limitada. Comparar sus resultados con el original. El grid
no debe moverse por haber aclarado la imagen. No se cambiarán los colores del
archivo del usuario. Si una sombra elimina información por saturación negra,
ningún ajuste clásico puede reconstruir con certeza lo que no está registrado.

### E. Ejecutar un plan local con límites de trabajo

Una casilla puede usar diferencia de color local; otra necesitar conservar más
detalle o combinar contornos con color. Una sombra puede activar la segunda
vista únicamente en una banda inferior. Se reutilizan OpenCV y NumPy.

Los umbrales partirán de la distribución de fondo y su dispersión robusta. La
limpieza morfológica se reducirá cuando borre trazos finos. El área mínima y la
distancia de agrupación deben expresarse también respecto a la escala de la
casilla y transformarse a píxeles en cada vista de análisis.

Conservar como máximo dos propuestas locales en zonas ambiguas es un límite de
trabajo inicial, no una garantía de exactitud. Las zonas claras no necesitan
repetir la segmentación. Agrupar accesorios bajo el mismo contrato de composición
en todas las rutas. Dos composiciones vecinas no se fusionan solo por proximidad.

### F. Colocar cuadrados y validar con otra evidencia

Un grid fiable fija los centros de corte. Una máscara parcial del perro no debe
desplazar el cuadrado hacia su cabeza. El tamaño físico elegido permanece separado
de la estimación de las casillas y de la extensión de la ilustración.

Revisar **toda la casilla y su contexto**, en píxeles originales, en lugar de ampliar
solo la caja detectada. Comprobar evidencia no explicada, continuidad fuera del
corte, discrepancias entre propuestas, detalles conservados y correspondencia
entre cortes y composiciones. La evidencia no explicada tampoco es automáticamente
parte del dibujo: debe contrastarse con el modelo de fondo.

Mantener separadas la fiabilidad del grid, de la composición y de la extensión.
Una buena puntuación del grid no compensa una silueta incompleta. Una casilla
inferida no equivale a una detección confirmada. Sin incertidumbre suficientemente
resuelta no se debe afirmar que la composición está completa.

## 5. Parámetros: actuales frente a propuestos

No hay un modelo neuronal entrenado cuyos pesos sean estos valores. Son ajustes
y reglas de procesamiento de imagen.

| Parámetro actual en `DetectorSettings` | Valor predeterminado del código | Uso |
| --- | ---: | --- |
| Sensibilidad | 65 | Se transforma en umbrales de segmentación |
| Área mínima | 500 px² | Filtra regiones pequeñas; depende de resolución |
| Limpieza morfológica | 0,25 | Modifica apertura/cierre para limpiar o unir regiones |
| Distancias de agrupación X/Y | 14/14 px | Agrupa componentes próximos |
| Modo | auto | Permite las distintas rutas de detección |

Una sesión de la interfaz puede tener otros ajustes guardados o convertir unidades
físicas a píxeles. Estos son valores del código, no una transcripción de todas las
capturas. Además existen constantes internas: por ejemplo, confianza de grid
0,78 y umbrales percentiles en la segmentación local. No representan un 78 % de
probabilidad real de acierto.

Los valores mencionados durante la planificación —análisis a 960 px, contexto de
15–30 %, compensación luminosa máxima 1,6, etc.— eran **propuestas nuevas para
experimentar**, no valores validados ni todos presentes en el programa. No se
introducirán juntos como un nuevo ajuste universal.

Para implementar, centralizar los parámetros nuevos en una configuración interna
versionada, con unidades y motivo. Priorizar medidas relativas a escala, ruido y
contraste local. Calibrar sus límites con grupos de imágenes, sin tablas de
excepciones por colección o nombre de archivo. No trasladar esta calibración al
usuario mediante más deslizadores.

## 6. Encaje en el código

| Pieza | Responsabilidad propuesta |
| --- | --- |
| Nuevo `scene_profile.py` | `SceneProfile`: iluminación, soporte incierto, mapas de color/textura/bordes, escala; sin producir cortes |
| Nuevo `detection_plan.py` | `DetectionPlan` y `ZonePlan`: hipótesis de grid, evidencias, estrategia local, parámetros efectivos y motivos de elección |
| `detector.py` | Orquestar perfil → grid provisional → zonas → ejecución → reconciliación → revisión; sustituir retornos de prioridad fija gradualmente |
| `bed_reference.py` / `analysis_frame.py` | Preservar original, contexto y zonas inciertas; registrar transformaciones |
| Productores actuales de grid | Devolver propuestas evaluables y sus evidencias; reutilizar el trabajo existente |
| `extent_review.py` | Revisar casilla completa y contexto, usando evidencia adicional y modelos de fondo explícitos |
| `models.py` / exportación de diagnóstico | Distinguir confianza geométrica y extensión; registrar por qué se eligió una ruta |
| `main_window.py` | Mantener un clic para Detectar, centros del grid y revisión existente; sin cuestionario de tipología |

Evitar dependencias circulares: el perfil no llama al detector, el planificador no
crea elementos de interfaz y la revisión no modifica retroactivamente el original.
Una única revisión del grid, si la evidencia local lo contradice, limita ciclos.

## 7. Implementación y comprobación por fases

1. **Perfil en diagnóstico.** Calcular y exportar características y decisiones
   propuestas sin cambiar los cortes actuales. Revisar que distingue fondos
   distintos, fondos compartidos y sombras en el catálogo completo.
2. **Selección del grid.** Comparar propuestas mediante evidencia común; medir
   líneas, centros y cobertura exterior, no solo número de cortes.
3. **Ejecución por zonas.** Introducir fondo local/compartido y detalle fino;
   corregir la selección de semillas seguras sin aceptar indiscriminadamente
   fondo vecino. Activar compensación de sombra solo con evidencia suficiente.
4. **Validación de extensión.** Pasar de caja parcial a casilla completa; registrar
   máscara o evidencia equivalente para distinguir recuperación de contenido y
   contaminación de fondo. Mantener separados ubicación y tamaño del cuadrado.
5. **Activación conjunta.** Solo después de medir el conjunto de casos y nuevas
   imágenes reservadas, no después de hacer funcionar la última imagen recibida.

Evaluación necesaria:

- Anotaciones de líneas de grid, composiciones, accesorios y puntos extremos
  importantes (patas, colas, ramas). No basta con contar 24.
- Una misma imagen recta con márgenes y resoluciones distintos: mismos resultados
  en coordenadas equivalentes y sin pérdida de la última fila.
- Sombras suaves y de borde duro de distintas intensidades, incluidas inferiores;
  controles negativos con tinta oscura real que no debe corregirse como sombra.
- Fondos iguales/diferentes, lisos/estampados; contraste alto/bajo entre dibujo y
  fondo; mezcla de estas situaciones en un solo panel.
- No borrar accesorios, no duplicar composiciones y no convertir flores del
  estampado en cortes. Conservar el caso legítimo de dibujo entre dos casillas.
- Medir omisiones, cortes extra, error de centro, evidencia fuera del corte y
  falsos «completo». Registrar por separado avisos innecesarios.
- Reservar colecciones enteras para comprobación independiente; variantes de la
  misma imagen no cuentan como colecciones nuevas. Las imágenes sintéticas ayudan
  a aislar causas, pero no sustituyen fotos reales sin superposiciones.
- Medir tiempo por etapa y pico de memoria en CPU. La nueva planificación aún no
  tiene un coste medido. Que use OpenCV no garantiza por sí solo que sea barata.

La única ejecución nueva de esta revisión es el panel floral recuperado I19:
24 candidatos, grid 6×4, cuatro composiciones con motivos de revisión, 2,03 s en
este equipo. No se ha ajustado el algoritmo con esa imagen ni certificado su
extensión completa. Resultado guardado en
`qa/image-audit/recovered-floral-baseline.json`.

Las 166 pruebas comunicadas previamente corresponden al código anterior a este
plan, no validan un planificador que todavía no existe. Las capturas históricas
muestran versiones y ajustes distintos: tampoco permiten atribuir sus recuentos
al ejecutable actual sin reproducir la entrada y configuración.
