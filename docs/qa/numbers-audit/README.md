# Diagnóstico de la tela de números — 14/10/2026

Análisis sin modificar el funcionamiento de la aplicación.

Entrada limpia: `C:/Users/daman/AppData/Local/Temp/codex-clipboard-8af8aaff-3e22-4103-9193-f88917134267.png`.
SHA-256 de píxeles: `fe96a5d058a82a361b2a7f9c9a91cb90188984bdd124e858ae4bf4b1f3806b30`.
Distribución esperada, inspeccionada en la imagen: cinco columnas y cuatro filas, veinte composiciones número + grupo de objetos. El número exacto de objetos dibujados por el generador no es el criterio de agrupación.

## Reproducción

Dos ejecuciones automáticas producen el mismo hash de resultado: 30 detecciones, sin cuadrícula final. Diez de los veinte conjuntos de puntos de control quedan contenidos en un único recuadro. Los otros diez se fragmentan. Se reproduce la cantidad de la captura del usuario.

## Cadena causal comprobada

1. La detección inicial obtiene 30 regiones y ninguna propuesta de cuadrícula aceptada (`stage=grid`, hipótesis vacías).
2. La recuperación de fondo compartido obtiene una propuesta de **10 × 3**, confianza 0,8939, seis lecturas concordantes y 37 regiones de evidencia. No equivale a una cuadrícula correcta.
3. El ajuste usa distancias entre componentes y vecinos próximos. En esta tela hay dos escalas de repetición: números y grupos a nivel de composición, y muchos objetos repetidos dentro de cada grupo. Las propuestas registradas incluyen 10 × 4, 10 × 3, 9 × 4, 8 × 4 y otras; ninguna propone 5 × 4. La propuesta elegida conserva 10, 13, 10 y 4 regiones respectivamente en las cuatro filas reales: la última está mucho peor representada.
4. El agrupador global recibe la cuadrícula equivocada, con paso mínimo de 136,31 píxeles. Encuentra 201 componentes y abandona esa ruta porque el grupo inferior de globos contiene un componente de 206 píxeles de alto, superior al límite de 1,5 veces ese paso. Es una protección para componentes grandes evaluada con una escala de casilla equivocada.
5. El análisis local alternativo conserva suficientemente solo 30 de las 37 regiones de evidencia: **81,08 %**, por debajo del 90 % exigido. La propuesta no se aplica (`accepted=false`, `corroborated=false`).
6. La aplicación mantiene las 30 regiones iniciales y avisa de falta de distribución fiable. No utiliza finalmente la cuadrícula 10 × 3, aunque el número de detecciones también sea 30. Sin cuadrícula común, los cuadrados siguen los centros de fragmentos distintos y se solapan.

## Experimento de aislamiento

Con una cuadrícula 5 × 4 proporcionada manualmente, límites aproximados `(40,80,1465,920)`, y el modelo de fondo compartido, el analizador devuelve **20 regiones y conserva los 20 conjuntos de puntos de control**. En este experimento la ruta global delega en el análisis local, y este consigue conservar los grupos. Es una prueba con la distribución suministrada, NO detección automática correcta.

Otro experimento excluye de la máscara de fondo las últimas cuatro columnas de píxeles. Con la misma cuadrícula manual, la ruta global también produce 20 grupos correctos. Revela una fragilidad secundaria: un fragmento diminuto del borde puede cancelar toda esa ruta. No explica por sí solo la propuesta automática errónea.

`oracle.json` conserva una primera cuadrícula manual menos ajustada y resultados inferiores (9/20 local y 18/20 con fondo compartido). `counterfactual.json` contiene el experimento final indicado arriba. No deben confundirse con resultados automáticos.

## Por qué no lo detectaron las pruebas anteriores

Las pruebas del alfabeto verificaban letras con una ilustración; las de animales verificaban accesorios separados. Este caso añade muchos objetos de tamaño similar, ordenados en pequeñas filas y columnas dentro de cada composición y con densidad creciente. La batería de 227 pruebas pasó para sus entradas, pero no acreditaba esta tipología nueva.

## Corrección que se necesita

- Proponer y comparar agrupaciones a distintas escalas, distinguiendo repetición interna de distribución de composiciones.
- Evaluar las cuatro filas y la conservación de números y objetos antes de elegir una cuadrícula; no premiar una cuadrícula densa que explica solo una parte del panel.
- No forzar un 5 × 4 ni limitar el resultado a veinte: las dimensiones deben proceder de evidencia de la imagen.
- Añadir esta imagen como regresión con veinte propietarios únicos y testigos sobre números y extremos de los grupos; el conteo de cajas por sí solo no basta.
- Revisar el abandono global por pequeños fragmentos del borde sin desactivar las protecciones de dibujos incompletos.

La medida de cinco pulgadas puede causar problemas de corte adicionales, pero no provoca las 30 detecciones: esa medida no interviene en esta inferencia de agrupaciones. No hace falta atribuir el fallo al ángulo de la foto.

Preferencia del usuario para futuras imágenes: vista cenital perpendicular, tela recta, sin giros ni perspectiva.

Evidencia: `auto.json`, `repeat.json`, `internal.json`, `route-trace.json`, `counterfactual.json`. `audit.py` reproduce el diagnóstico base sin editar código de producción.
