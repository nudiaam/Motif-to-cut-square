# Corrección de las repeticiones internas — 14/10/2026

## Resultado comprobado

La entrada original que daba 30 fragmentos ahora produce automáticamente **20 composiciones en 5 × 4**. Los veinte conjuntos de puntos independientes sobre números y extremos de sus objetos tienen un único propietario. No se introduce el número veinte ni la distribución esperada en el detector.

Las nueve variantes de la fotografía conservan veinte grupos completos: original, dos resoluciones menores, menor luminosidad, sombra diagonal, cambio de temperatura de color, giro, transformación geométrica y margen añadido. Son pruebas internas de resistencia; los nuevos prompts del usuario piden fotografías rectas y perpendiculares.

## Funcionamiento

`hierarchical_compositions.py` aporta una recuperación limitada a escenas que las rutas anteriores dejan sin cuadrícula. Busca elementos principales repetidos en distintas lecturas de tamaño de componente y contraste. Compara la geometría que proponen esas lecturas antes de asignar los elementos pequeños.

La fase y el paso de la distribución se ajustan con el conjunto de la tinta. Los centros de los elementos principales no se consideran directamente centros de las composiciones: un número de dos cifras es más ancho que otro de una cifra. Una única geometría común se refina usando los grupos completos. Los componentes asignados conservan sus límites completos y las restricciones de imagen, cama y exportación siguen aplicándose.

Las sombras requieren evidencia independiente de iluminación y coincidencia entre dos estimaciones espaciales antes de admitir la recuperación; se conserva un aviso de revisión. Se rechazan propuestas que omiten tinta significativa fuera de su distribución. Solo se toleran fragmentos mínimos y estrechos del marco en el borde de la imagen.

## Evidencia

Resultado final: **231 pruebas correctas**, 595,337 segundos, sin fallos de prueba.

- `variants-final.json`: nueve ejecuciones con veinte propietarios únicos.
- `numbers-fixed-ui.png` y `.json`: interfaz real con veinte detecciones, veinte habilitadas, cero inferidas y cero composiciones incompletas.
- `tests/test_number_compositions.py`: fotografía con testigos independientes, píxeles intactos, ejemplos de 9, 12 y 18 composiciones, negativos con figuras independientes y verificación de la interfaz.
- `tests-final.txt`: batería completa que incluye los controles anteriores.

## Límites de corte observados

La interfaz conserva **20 avisos de solapamiento y 19 de contenido que excede el corte** con el perfil supuesto de 36 × 24 pulgadas y cuadrados de cinco pulgadas. El paso estimado es 6,50 × 4,75 pulgadas. La detección de veinte grupos está corregida; esa configuración aún no proporciona veinte cuadrados que contengan todos los objetos y se puedan cortar sin solapamiento.

No se ha reducido el tamaño de corte ni alterado la calibración para ocultar los avisos. Los nuevos prompts piden composiciones compactas y separación amplia. Una foto generada sigue necesitando comprobación visual y no acredita dimensiones físicas reales.

La auditoría anterior (`README.md`, `auto.json`, `repeat.json`) describe el fallo previo y se conserva como referencia. Los resultados nuevos se guardan en archivos distintos.
