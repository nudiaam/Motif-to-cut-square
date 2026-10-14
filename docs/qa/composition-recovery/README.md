# Recuperación de composiciones completas

## Problema reproducido

El alfabeto sin recuadros impresos generaba 34 detecciones y un corte inferido en la interfaz. Se aceptaba una partición de 7 × 5 con poca correspondencia con los dibujos. La alternativa de 6 × 4 existía, pero el análisis local perdía letras separadas y no superaba la comprobación de conservación de contenido. La auditoría anterior queda intacta en `../alphabet-audit`.

## Cambio

La ruta de fondo compartido recoge primero componentes de tinta en toda la imagen y después los asigna a una geometría corroborada. Conserva los límites completos de cada componente; no recorta el dibujo para hacerlo encajar en una casilla. El encuadre alrededor de la tela deja de determinar por sí solo el modelo de fondo. Si hay evidencia independiente de sombra, dos estimaciones espaciales de iluminación deben concordar antes de admitir una vista normalizada para el análisis.

Los campos conectados grandes y los fragmentos dudosos del borde vuelven al análisis local. Esto conserva el tratamiento de fondos complejos y dibujos que abarcan varias casillas. Una cuadrícula todavía discutida no genera cortes adicionales en sus huecos. La pertenencia de los componentes se calcula en las coordenadas de la cuadrícula, incluyendo giro y perspectiva.

## Comprobaciones

Resultado final: **227 pruebas correctas**, 451,073 segundos, sin fallos ni errores
de prueba. Incluye las nueve variantes del alfabeto y las nueve de animales con
accesorios. Los mensajes de OpenCL del equipo se resuelven con ejecución en CPU.

- Original del alfabeto: 24 detecciones, 24 pares letra/ilustración con propietarios únicos, cero cortes inferidos.
- Nueve variantes del original: dos resoluciones menores, menor luminosidad, sombra diagonal, cambio de temperatura de color, giro, perspectiva, marco añadido y original. Cada variante exige conservar los 24 pares, no solamente contar 24 cajas. Los píxeles de entrada permanecen intactos.
- Se mantienen los controles de animales con dos accesorios y de dibujos que ocupan dos celdas, además de los límites de imagen/cama y la exportación.
- `tests-final.txt` contiene la ejecución completa final; los archivos `tests.txt` y `recheck*.txt` conservan también los fallos intermedios y sus comprobaciones posteriores.
- `alphabet-ui.png` y `review-ui.png` muestran la interfaz real, con la revisión y el resumen de salida juntos.

## Lo que no demuestra esta prueba

La captura del alfabeto sigue mostrando avisos con el perfil supuesto de cama de 36 × 24 pulgadas y cuadrados de 5 pulgadas: el paso estimado entre centros es 5,16 × 4,85 pulgadas, hay 24 cortes con solapamientos y diez dibujos exceden su cuadrado. Son problemas de tamaño/posición de corte respecto a la imagen, distintos del desdoblamiento de letras. No se ha reducido automáticamente el corte ni alterado la calibración para ocultarlos. No es una salida aprobada para cortar.

Los centros siguen una geometría común de la tela; si la fotografía está inclinada, las filas no son horizontales en pantalla. El ajuste visual no calibra la cámara respecto a la máquina. Una fotografía generada tampoco acredita medidas físicas reales.

La última imagen navideña fue una captura con superposiciones. Sin su entrada limpia no se ha reproducido ese caso exacto. Tampoco se han validado todas las colecciones reales del catálogo. Véanse `catalogue-coverage.md` y `10-prompts.md`.

## Reproducir

Desde la raíz, con el entorno del proyecto:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_alphabet_compositions -v
.venv\Scripts\python.exe -m tests.evaluate_alphabet --output docs/qa/composition-recovery/alphabet-final.json
```
