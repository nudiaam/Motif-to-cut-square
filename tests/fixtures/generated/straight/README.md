# Paneles rectos de prueba

Tres imágenes nuevas generadas con la herramienta integrada `image_gen` el
21-09-2026, tras pedir el usuario telas rectas como las del correo. Se inspeccionó
que los paneles tuvieran filas y columnas rectas y sin perspectiva apreciable.
La generación no garantiza igualdad matemática de las dimensiones: las divisiones
aproximadas se anotaron sobre las imágenes obtenidas, no sobre lo solicitado en
el prompt. Cada imagen contiene 24 composiciones en 6 × 4.

- [Pastel](pastel_6x4.png): animales claros, fondos diferentes y accesorios.
- [Perros](dogs_6x4.png): figuras completas sobre fondos de rayas, puntos y corazones.
- [Corazones](hearts_6x4.png): siluetas florales sobre estampados variados.

Los prompts exactos y las anotaciones están en [manifest.json](manifest.json).
Los PNG se copiaron sin modificar la salida del generador. El detector no recibió
los recuentos ni las anotaciones como entrada. No se cambió el código de detección
para esta evaluación.

Resultados: pastel 25 candidatos y una casilla duplicada; perros 24; corazones 24.
En todos hay candidatos en las 24 posiciones esperadas. Esto solo mide cobertura
de casillas; no certifica que se capture la figura entera ni que el corte encaje.
El [informe visual](../../../../docs/qa/straight-panels/README.md) documenta los
desajustes y conserva los resultados completos y las capturas de la aplicación.

Repetir desde la raíz del proyecto:

```powershell
.venv/Scripts/python.exe -m tests.evaluate_straight_panels
```

El evaluador devuelve código 1 mientras exista una casilla omitida, duplicada o
una detección exterior. Actualmente falla pastel por la mariposa separada del
gato. No se convierte ese error en una expectativa de una prueba que pase.
