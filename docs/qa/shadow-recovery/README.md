# Recuperación de cuadrículas bajo sombras irregulares

Implementado el 22 de septiembre de 2026. Revisión del detector:
`2026-09-22-local-contrast-consensus`.

## Resultado comprobado

- El original nuevo pasa de 15 regiones sin cuadrícula a **24 composiciones en 6×4**.
- Las doce variantes controladas de sombras (horizontal, vertical, diagonal y
  manchas sobre transporte, perros y corazones) devuelven **24 composiciones en 6×4**.
- Las once imágenes anteriores conservan sus recuentos. Incluyen motivos que
  ocupan varias casillas, fondos compartidos, patchwork y colores pastel.
- El original nuevo reducido al 50 % y ampliado al 150 % conserva 24 composiciones.
- Pasan **188 pruebas automatizadas**, incluidas interfaz, geometría, exportación,
  referencias de cama, imágenes anteriores y los nuevos casos.
- Se comprobaron 72 puntos de tinta anotados manualmente en los 24 vehículos:
  todos están dentro de su caja correspondiente. Se incluyen ruedas, antenas,
  banderas, hélices y escaleras. Los puntos también quedan incluidos al redimensionar.

No se equipara el recuento con precisión completa: no hay máscaras anotadas de
todas las siluetas. El programa conserva ocho avisos de extensión en el nuevo
original, en lugar de convertirlos artificialmente en resultados verdes.

## Cambio de lógica

La nueva propuesta geométrica mide **contraste relativo local en dos dimensiones**:
estima luminosidad de fondo a varias escalas y compara los detalles respecto a ese
entorno. Puede así aprovechar contornos bajo sombras sin necesitar primero una
máscara perfecta de tela ni una segmentación global completa.

Esta señal se usa para proponer posiciones y separación. **No sustituye los
píxeles originales ni proporciona los contornos finales.** Una propuesta necesita
coincidencia de dimensiones, fase y separación en varias escalas y umbrales. Debe
existir una hipótesis densa; otras pasadas parcialmente fragmentadas solo pueden
corroborarla. No se conoce ni se introduce el número esperado de filas o columnas.

Cuando aporta una geometría nueva o identifica composiciones que la máscara de
tela iba a descartar, se vuelve a analizar cada casilla sobre el original, con
contexto alrededor. Se exige recuperar al menos el 85 % de sus casillas para
aceptar esa sustitución. La máscara brillante anterior deja de poder eliminar
las composiciones recuperadas por estar en sombra. Las geometrías anteriores que
coinciden y están completas se conservan; las composiciones estables existentes
también se protegen, incluidos dibujos que abarcan varias casillas.

La selección de cuadrícula puede ahora rechazar una propuesta que agrupa centros
mal alineados aunque no haya otra propuesta que la contradiga. Se corrigieron
además rutas posteriores que podían volver a utilizar una propuesta rechazada.
La revisión de extensión sigue consultando el original completo.

## Parámetros y coste acotado

| Medida | Valor y función |
|---|---|
| Resolución de propuesta | Lado mayor de 960 px; la imagen original no cambia |
| Escalas de fondo | Seis escalas geométricas, entre 2,5 % y 14,1 % del lado menor |
| Umbrales relativos | 35, 45, 55, 65 y 75; máximo de 30 máscaras de propuesta |
| Tamaño mínimo de fragmento | Máximo entre 25 px y 0,03 % de la vista; independiente de la resolución del archivo |
| Complejidad | Se rechazan máscaras con más de 150 componentes elegibles antes de combinarlos |
| Hipótesis principal | Confianza ≥0,80, ocupación ≥85 %, soporte ≥70 % |
| Corroboración parcial | Confianza ≥0,70, ocupación ≥75 %, soporte ≥60 % |
| Concordancia espacial | Desviación de esquinas <10 % de la separación entre casillas |
| Acuerdo requerido | Al menos dos escalas y dos umbrales; dos hipótesis fuertes, o una fuerte corroborada por al menos otras dos |

En esta máquina, la propuesta nueva tarda aproximadamente **0,45 s** en cada uno
de los dos originales de transporte. El proceso completo del nuevo original
tardó **3,23 s**; a mitad de resolución, 1,18 s; ampliado al 150 %, 12,13 s.
Los tiempos completos incluyen también las rutas previas, segmentación y revisión.
Son mediciones locales, no una garantía para todos los ordenadores o imágenes.

No se incorporan modelos, servicios de red, GPU ni dependencias nuevas. El pico
del proceso de evaluación completo fue 482,5 MiB, incluyendo OpenCV, datos de
diagnóstico y las variantes ampliadas; no es una medida aislada de memoria de la
nueva etapa ni de la interfaz.

## Comparación con imágenes anteriores

| Imagen | Antes | Después |
|---|---:|---:|
| Folk floral | 24 | 24 |
| Animales pastel | 24 | 24 |
| Perros rectos | 24 | 24 |
| Corazones rectos | 24 | 24 |
| Panel pastel recto | 24 | 24 |
| Transporte con dibujo que abarca casillas | 19 | 19 |
| Fotografía pastel | 24 | 24 |
| Fotografía patchwork tenue | 22 | 22 |
| Fotografía de transporte | 19 | 19 |
| Panel de vehículos anterior | 24 | 24 |
| Panel floral recuperado | 24 | 24 |

El caso patchwork conserva su limitación anterior: dos figuras muy tenues siguen
sin detección confirmada. Las propuestas de casillas de la interfaz no se cuentan
aquí como figuras detectadas. No se presenta como una regresión ni como resuelto.

## Detección y tamaño físico del corte

En la comprobación de interfaz se mantiene la colocación de imagen de 36×24 pulgadas.
La separación vertical inferida es aproximadamente **4,74 pulgadas**. Por tanto:

| Tamaño del cuadrado | Composiciones | Cortes con solapamiento | Dibujo detectado recortado | Avisos de extensión |
|---|---:|---:|---:|---:|
| 5×5 pulgadas | 24 | 24 | 0 | 8 |
| 4,5×4,5 pulgadas, prueba | 24 | 0 | 0 | 8 |

El naranja a 5 pulgadas es correcto: los cuadrados se cruzan entre filas. A
4,5 pulgadas se ven 16 verdes y ocho violetas. Se conserva el tamaño predeterminado
de 5 pulgadas; 4,5 se utilizó solo en una instancia de prueba. Una imagen generada
no determina por sí misma las dimensiones físicas reales de una tela.

Capturas verificadas: `new-original-ui.png` (5 pulgadas) y
`new-original-ui-4_5in.png` (prueba a 4,5 pulgadas). Los archivos `*-bounds.png`
muestran cajas de detección, no cuadrados de corte físico.

## Reproducción

Desde la raíz del proyecto:

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m tests.evaluate_shadow_recovery
.venv/Scripts/python.exe -m tests.evaluate_shadow_recovery --ui
```

Resultados completos en `evaluation.json`, `ui-verification.json` y `unittest.txt`.
Los originales permanecen intactos y el evaluador comprueba sus píxeles antes y
después de cada detección. El diagnóstico previo se conserva en
`../irregular-shadows/` para comparar el fallo y las intervenciones exploratorias.
