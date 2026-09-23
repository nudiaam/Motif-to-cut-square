# Composiciones con accesorios separados — 23 septiembre 2026

## Fallo reproducido

Original: `Imagen de Codex 23 sept 2026, 11_10_14-7.png`, conservado sin cambios
en `tests/fixtures/acceptance/animal_accessories_4x3.png`.

La imagen contiene 12 grupos en 4 columnas y 3 filas: cada grupo tiene un animal
y dos accesorios separados. El detector anterior devolvía 20 candidatos en una
cuadrícula de 5 × 4. La propuesta correcta de 4 × 3 ya existía y estaba respaldada
por 16 combinaciones de escala/umbral, pero no ganaba la decisión.

Dos factores lo explican:

1. La textura de algodón daba un apoyo de bordes de 0,923 a la partición errónea.
   Tener todas sus casillas ocupadas por extracciones locales no demostraba que
   esa partición respetase los grupos reales: solo el 45 % quedaba alineado.
2. La propuesta 4 × 3 aportaba 17 regiones, incluidas partes y accesorios.
   Comparar directamente esas regiones como si cada una necesitara su propio
   corte penalizaba la propiedad única y la alineación de la propuesta correcta.

Un análisis local sobre los píxeles originales recupera 12 grupos, alineados,
conservando las 17 regiones de partida. Sus límites contradicen la cuadrícula
5 × 4: esta corta composiciones y no tiene ningún grupo centrado correctamente.

## Corrección acotada

Se añade una comprobación de pertenencia para propuestas de apariencia repetida
que pierden frente a una partición todavía dudosa. Requiere ocupación y alineación
previas suficientes, acuerdo entre escalas y un número limitado de propietarios
duplicados. Una segunda distribución completa de figuras no se trata como accesorios.

La comprobación local debe recuperar grupos alineados y conservar las regiones
observadas independientemente. Se vuelve a presentar esta evidencia al mismo
coordinador; no se impone una cuadrícula por número esperado, por archivo o colección.
La extracción local se reutiliza si la propuesta gana.

Al ampliar el original apareció una propuesta cromática desplazada que conservaba
sus propios fragmentos, pero perdía el ovillo y otras partes. Por eso, en esta
situación dudosa se consulta también la evidencia del fondo compartido. Ambas
propuestas se contrastan con las regiones de todas las lecturas independientes.
Una propuesta que falla esa comprobación no puede ganar por una puntuación próxima
a la de la propuesta corroborada. No basta con que sus centros estén alineados.

## Pruebas

- El original, media resolución y resolución ×1,5 producen 12 grupos en 4 × 3.
- Se comprueban 36 puntos anotados sobre el original: animal y ambos accesorios
  deben pertenecer al mismo resultado, distinto del propietario de otros grupos.
- Un negativo devuelve centros perfectamente alineados pero cajas que descartan
  los accesorios: no se acepta la recuperación.
- Otro negativo introduce dos figuras distintas en cada casilla propuesta:
  no se activa la unión de accesorios.
- `comparison.json` compara número, cajas, centros y motivos de revisión contra
  el detector guardado antes del cambio. Incluye los 20 controles anteriores y
  las diez generaciones nuevas. Preservar un resultado previo no certifica por
  sí solo que ese resultado sea correcto; comprueba que no cambia con esta revisión.

La comparación final conserva exactamente cajas, centros y motivos de revisión
en los 29 controles (20 anteriores y las otras nueve generaciones nuevas).
Solo cambia el caso señalado: de 20 regiones erróneas a 12 grupos.
Las 202 pruebas automáticas terminan sin fallos; registro en `unittest.txt`.

Los originales de esta tanda se conservan en `tests/fixtures/acceptance/batch_20260923/`
con un manifiesto de procedencia y hashes. El caso 7 reutiliza el fixture principal.

```powershell
.venv/Scripts/python.exe -m unittest tests.test_accessory_ownership -v
.venv/Scripts/python.exe -m tests.evaluate_accessory_ownership
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Interfaz y límites

`ui.png` muestra 12 composiciones, sin solapamientos y sin posiciones inventadas.
Los cortes siguen midiendo 5 × 5 pulgadas: con la escala actual no abarcan la
extensión completa de los grupos, de modo que se mantienen los 12 avisos morados
`CLIPPED`. No se han cambiado tamaño físico, calibración ni criterios de colisión.

Los puntos verifican pertenencia de los accesorios, no una máscara exhaustiva de
cada contorno. La corrección utiliza separación, repetición y evidencia de color;
no reconoce semánticamente qué es un animal o un accesorio. Las composiciones cuya
agrupación visual sea ambigua siguen necesitando revisión.
