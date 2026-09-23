# Diagnóstico: fondo compartido y sombras irregulares

Fecha: 22 de septiembre de 2026. **Diagnóstico, no corrección incorporada al programa.**

## Conclusión

El fallo nuevo se reproduce: **15 regiones y ninguna cuadrícula aceptada**, para
una imagen con 24 composiciones en 6×4. No es específico de vehículos. Sombras
añadidas a perros y corazones que funcionaban también producen pérdidas y grids
incorrectos. Hay una cadena de fallos de iluminación, segmentación y selección
de geometría; cambiar un umbral o añadir un motor pesado no aborda esa cadena.

La corrección anterior sí resolvía otro fallo: el transporte anterior proporcionaba
24 regiones iniciales bien distribuidas, pero una propuesta geométrica incorrecta
las sustituía por 12 cortes. En este caso las regiones iniciales ya están mal.
La protección basada en centros estables no puede operar con esos centros.

## Diferencia visual y funcional

Los dos originales tienen fondo azul compartido, estrellas y marcos discontinuos.
El nuevo incorpora sombras irregulares que cruzan motivos y espacios entre ellos,
y más entorno oscuro visible. Las sombras cambian dentro de una misma fila.
Las estrellas, el borde deshilachado y las líneas impresas aportan señales ajenas
al dibujo que compiten con su contorno. Esta comparación visual sugiere causas;
las pruebas controladas siguientes permiten aislar el efecto de la iluminación.

Los originales son escenas distintas, no una pareja de píxeles idénticos antes y
después de sombrear. Por ello no se atribuye toda diferencia entre ellos únicamente
a la sombra. Las variantes controladas sí parten de los mismos píxeles.

## Cadena de fallos comprobada

1. **La delimitación de tela confunde luminosidad con continuidad física.**
   `locate_bright_fabric` umbraliza luminosidad mediante Otsu. En el nuevo original
   aparecen dos contornos claros grandes, con áreas equivalentes al 51,6 % y
   16,7 % de la imagen reducida. El segundo supera el límite del 2,5 % y el
   programa devuelve «Multiple pieces require an empty-bed reference», aunque
   visualmente es una sola tela. En el transporte anterior el mayor contorno
   ocupa aproximadamente el 95,8 %.
2. **La corrección de iluminación depende de esa delimitación.**
   `illumination_view` sale inmediatamente si no hay máscara de tela. Además,
   corrige por filas, exigiendo acuerdo de varias franjas verticales. Incluso
   suministrando una máscara aproximada correcta, en esta imagen devuelve `None`.
   No representa una sombra que cambia de posición e intensidad dentro de la fila.
3. **La sombra entra en la máscara de dibujos y conecta regiones.**
   `_detect_once` combina diferencias de luminosidad y color respecto al fondo.
   El fondo se estima con suavizado gaussiano y una referencia de color global.
   La máscara resultante contiene puentes y manchas grandes en lugar de separar
   los motivos. Antes de limpiar el entorno hay 709.865 píxeles de primer plano;
   después quedan 218.743. Un componente de 491.122 píxeles, conectado al marco,
   desaparece. Otro componente de 372×317 píxeles engloba varias zonas de dibujo.
   Las superposiciones permiten inspeccionar estas agrupaciones.
4. **Eliminar un filtro aislado no reconstruye lo perdido.**
   Desactivar la limpieza del entorno sigue dando 15 regiones. El componente
   gigante representa el 31,2 % de la imagen y también supera el máximo del
   30 % permitido por `_components`. Aceptarlo tampoco lo convertiría en dibujos
   separados. La separación debe mejorar antes de esos descartes.
5. **El análisis local depende de una cuadrícula que no llega a construirse.**
   Las pasadas a sensibilidades 55, 65 y 75 producen 19, 15 y 10 regiones.
   No hay acuerdo estable; tampoco se obtiene otra propuesta de grid. El
   planificador registra `selected_route: null` e `hypotheses: []`. Al proporcionar
   manualmente un grid aproximado 6×4, el análisis por casillas sí devuelve 24
   candidatos. Esto localiza un cuello de botella, pero no certifica sus contornos.
6. **En otras variantes sí aparece un grid, pero no siempre merece aceptarse.**
   En transporte con sombras por manchas y compensación experimental se acepta
   una propuesta de cámara 4×3: ocupación 100 %, alineación 8,3 % y asignación única
   50 %. La ocupación alta recompensa un grid demasiado grueso. `choose_grid`
   usa la confianza del productor como admisión y clasifica las alternativas;
   la protección contra agrupaciones erróneas necesita otra propuesta estable
   que las contradiga. Falta una condición suficiente de rechazo cuando esa
   alternativa no existe. No basta con elegir la mejor de las disponibles.

## Pruebas controladas con el detector actual

Se aplican cuatro campos suaves de sombra, con intensidad mínima del 40 %, a
los mismos píxeles de cada control. No se cambian sensibilidad ni otros parámetros.
Las cifras son **candidatos devueltos**, no cortes completos certificados.

| Colección | Control | Banda horizontal interior | Banda vertical | Diagonal | Manchas |
|---|---:|---:|---:|---:|---:|
| Transporte anterior | 24 · 6×4 | 15 · 5×3 | 24 · sin grid | 20 · 5×4 | 11 · 4×3 |
| Perros | 24 · 6×4 | 23 · sin grid | 16 · 4×4 | 20 · 5×4 | 23 · 6×4 |
| Corazones | 24 · 6×4 | 18 · 6×3 | 12 · 3×4 | 20 · 5×4 | 23 · 6×4 |

Las pruebas anteriores de sombra inferior no cubrían estas distribuciones.
También falla una banda horizontal interior que divide la zona clara de la tela;
el problema no se limita a la orientación diagonal.

## Aislamiento de causas en el nuevo original

| Experimento | Candidatos | Grid | Lectura |
|---|---:|---|---|
| Detector actual | 15 | Ninguno | Reproduce el fallo |
| Recortar gran parte del entorno exterior | 16 | Ninguno | El exterior no explica todo |
| Desactivar limpieza conectada al marco | 15 | Ninguno | Persisten fusión y filtro de área |
| Ignorar luminosidad en las dos distancias de color | 22 | Ninguno | Ayuda, pero pierde evidencia útil y no resuelve |
| Aportar máscara de tela manual | 15 | Ninguno | Delimitar tela no basta; no activa corrección por filas |
| Aportar grid manual aproximado | 24 | Manual 6×4 | El análisis local puede recuperar los motivos |
| Compensar luminosidad en 2D antes del detector | 24 | Automático 6×4 | Vía prometedora; quedan 11 avisos de extensión |

En la compensación 2D el productor de paneles consigue proponer 6×4 y se habilita
el análisis local. No demuestra que toda la segmentación global previa se haya
arreglado. Los avisos se calculan sobre la entrada compensada en este experimento,
por lo que **no sustituyen la validación independiente contra el original**.

Barrido de sensibilidad, solo detección inicial, sin sustituir el algoritmo:

| Sensibilidad | Transporte anterior | Nuevo original |
|---|---:|---:|
| 35 | 24 | 31 |
| 45 | 24 | 25 |
| 55 | 24 | 19 |
| 65, valor predeterminado | 24 | 15 |
| 75 | 24 | 10 |
| 85 | 25 | 4 |

Más sensibilidad reduce el umbral y puede unir dibujos mediante las sombras.
Por eso puede devolver menos objetos. Buscar un número próximo a 24 ajustando
este valor no equivale a encontrar correctamente cada composición.

## Comprobación cruzada de la compensación experimental

Se mantiene la misma receta: canal L de Lab, cierre morfológico 151×151,
suavizado sigma 15, referencia percentil 80 y ganancia máxima 1,6. La comparación
usa un soporte central del 90 % del ancho y alto; no emplea el grid conocido.
Son parámetros de una prueba a estas resoluciones, no parámetros aprobados para
producción ni una estimación robusta definitiva del campo de luz.

| Colección | Control | Horizontal | Vertical | Diagonal | Manchas |
|---|---:|---:|---:|---:|---:|
| Transporte anterior | 24 · 6×4 | 23 · sin grid | 24 · 6×4 | 24 · 6×4 | **12 · 4×3** |
| Perros | 24 · 6×4 | 24 · 6×4 | **22 · sin grid** | 24 · 6×4 | 24 · 6×4 |
| Corazones | 24 · 6×4 | 24 · 6×4 | 24 · 6×4 | 24 · 6×4 | 24 · 6×4 |

El nuevo original también devuelve 24 · 6×4 con ese soporte central. Total:
13 de 16 entradas cumplen simultáneamente cantidad y dimensiones esperadas;
**eso no es una tasa de precisión de contornos**. Los tres fallos restantes
impiden presentar esta normalización como solución general. No se ha medido aún
su coste en una implementación acotada ni validado telas oscuras con esta receta.

## Implementación que se desprende del diagnóstico

1. **Separar soporte físico e iluminación.** Un fallo al delimitar tela no debe
   desactivar todo análisis de luz. Mantener límites inciertos sin recortar
   dibujos prematuramente. Tratar «varias zonas claras» como evidencia ambigua,
   no como prueba de varias telas.
2. **Proponer una vista alternativa de iluminación 2D, acotada y conservadora.**
   Estimarla a resolución reducida, apoyándose en fondos localmente compatibles.
   Distinguir cambios de color impresos de variaciones de luz; preservar el
   original y comparar ambas vistas. No aclarar automáticamente toda zona oscura
   ni convertir la receta experimental en un preprocesado obligatorio.
3. **Obtener geometría por vías independientes de una máscara global perfecta.**
   Contrastar repetición, divisiones impresas y agrupaciones de figuras. En un
   fondo compartido con marcos discontinuos, aprovechar su continuidad espacial
   aunque parte de la señal esté sombreada. Los fondos por casilla requieren
   evidencia local diferente. No introducir el supuesto fijo de seis columnas.
4. **Evaluar una propuesta por lo que explica y por lo que contradice.** Penalizar
   casillas que contienen varios centros independientes o líneas que atraviesan
   composiciones; comprobar zonas periféricas sin explicar y estabilidad entre
   vistas. Permitir rechazar la única propuesta. Los centros degradados tampoco
   deben convertirse en verdad absoluta: contrastarlos con evidencia de imagen.
5. **Analizar por casilla con contexto y validar contra el original completo.**
   Comprobar tanto fragmentos omitidos como varias figuras agrupadas, cajas que
   cruzan el dibujo y restos fuera de la propuesta. Mantener el aviso de revisión
   cuando no haya evidencia suficiente. No declarar éxito por contar 24.

No hace falta introducir SAM/YOLO para probar estas correcciones. Tampoco puede
prometerse funcionamiento universal: la aceptación requiere comprobar contornos,
geometría y coste en casos variados, no solo los dos transportes conocidos.

## Alcance, reproducción y archivos

Se ejecutaron 22 casos de diagnóstico (cuatro controles, doce sombras controladas,
cinco intervenciones y un grid manual), doce pasadas de sensibilidad y dieciséis
comprobaciones cruzadas de compensación. Las intervenciones se aplican solo en
memoria. Los SHA-256 de `app/**/*.py` se conservaron durante el diagnóstico.
Los cambios de producción previos a esta investigación permanecen sin alterar.

Desde la raíz del proyecto:

```powershell
.venv/Scripts/python.exe -m tests.diagnose_irregular_shadows
.venv/Scripts/python.exe -m tests.diagnose_irregular_shadows --cross-check
```

- `diagnosis.json`: resultados, candidatos, planes y huellas de los archivos.
- `compensation-cross-check.json`: las dieciséis comprobaciones adicionales.
- `transport_irregular-bounds.png`: regiones originales incorrectas.
- `foreground-before-camera-cleanup.png`: máscara que muestra las conexiones.
- `oracle_grid-bounds.png`: análisis local con geometría aportada manualmente.
- `experimental_2d_compensation-bounds.png`: recuperación experimental del original.
- `transport_clean_patches_2d-bounds.png`: contraejemplo donde sigue fallando.

Las imágenes `*-bounds.png` muestran rectángulos de regiones detectadas, **no los
cuadrados finales de corte físico ni una certificación de que las figuras caben**.
