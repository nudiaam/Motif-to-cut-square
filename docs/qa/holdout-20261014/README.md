# Validación de los cinco originales nuevos

## Comprobación previa a publicación en GitHub

El 14 de octubre se ejecutaron además 59 pruebas de interfaz, trabajador de
análisis, diagnósticos y exportación. Pasaron 58 en la primera ejecución;
la restante esperaba el identificador anterior `visual` para una imagen que
ahora utiliza la propuesta completa `ink_lattice`. Se actualizó esa expectativa
y se repitió la prueba completa, incluyendo 24 cortes válidos sin solapes,
alineación, cambio de tamaño, revisión y deshacer: pasó. No se modificó el
algoritmo durante esta comprobación ni se afirma haber repetido toda la batería.
Registros: [ejecución inicial](github-publication-checks.txt) y
[repetición completa del caso](github-camera-recheck.txt).

El usuario ha confirmado también que las nuevas imágenes generadas para su
comprobación han pasado. Esa comprobación visual no se presenta como una nueva
medición automática con originales y anotaciones guardados.

La revisión parte de originales recibidos después de la mejora anterior. Estos
ejemplos expusieron falta de generalización: las variantes de las imágenes
anteriores no representaban otras distribuciones de componentes. Una vez usados
para corregir el algoritmo, estos cinco casos son regresiones; no se presentan
como una evaluación independiente de imágenes todavía no vistas.

## Reproducción inicial y causas

| Imagen | Reproducción inicial | Grupos completos actuales |
|---|---:|---:|
| Letras y juguetes | 24, sin cuadrícula | 12, 4 × 3 |
| Números planos | 34, sin cuadrícula | 20, 5 × 4 |
| Frases y adornos | 20, cuadrícula 4 × 4 | 16, 4 × 4 |
| Números de fieltro | 20, con límites que mezclaban vecinos | 20, 5 × 4 |
| Animales en paneles | 27, sin cuadrícula | 12, 4 × 3 |

La captura de animales muestra 28; la reproducción con ajustes predeterminados
obtiene 27. Ambas son incorrectas frente a las doce composiciones visibles.
`baseline/*.json` conserva las trazas iniciales, incluidas las intervenciones
temporales que desactivan únicamente la ruta compuesta anterior. Los problemas
también ocurren sin esa ruta: no se atribuye una regresión al último cambio sin
evidencia de una comparación en la misma imagen.

Las causas verificadas son:

- Letras: propuestas de 4 × 3 y 8 × 3 se vetan mutuamente. La lectura acaba con
  veinticuatro fragmentos. La ruta compuesta anterior requiere una cuadrícula
  aceptada y no actúa aquí.
- Números planos: existe una lectura fina de diez columnas, pero no una propuesta
  admitida de todos los grupos. Seleccionar anclas por área/altura no cubre todas
  las relaciones entre símbolos y conjuntos de objetos.
- Frases: una cuadrícula de dieciséis posiciones coexiste con cuatro fragmentos
  adicionales. El conteo de casillas no garantiza consolidar el contenido.
- Fieltro: una caja del grupo nueve invade el número diez. La protección de esa
  caja habría preservado un error. Los grupos nueve, diez y diecinueve también
  necesitan ampliar sus límites para incluir tinta periférica.
- Animales: las divisiones de color tienen consenso de seis lecturas, pero el
  cálculo de cámara fracasa antes de utilizarlas. Las plantas pequeñas también
  pueden desaparecer durante la segmentación local.

## Cambio instalado

Se comparan propuestas de grupos completos inferidas de espacios entre la tinta,
a varios tamaños de unión y tres umbrales de primer plano. No se fijan nombres
de colecciones, letras, números, cantidades de grupos ni tamaños de corte.

La geometría se descubre antes de asignar todas las piezas originales. Dos
lecturas independientes deben conservar al menos el 98 % de la tinta de sus
componentes en propietarios completos. Una figura conectada no puede dividirse
solo para llenar más casillas. Las sombras y los cambios de exposición se
normalizan únicamente para el análisis; los píxeles mostrados permanecen intactos.
La compensación espacial requiere acuerdo entre dos estimaciones.

Los fragmentos sin geometría validada no se tratan como composiciones conocidas:
pueden contener ya varios grupos unidos por error. Las cajas con avisos de
pertenencia tampoco se usan para bloquear su corrección. Las regiones de una
geometría estable y sin esos avisos conservan la prueba de preservación anterior.

Las divisiones sostenidas del tejido se evalúan directamente, aunque no exista
una propuesta de cámara. En esa recuperación, la segmentación conserva tinta
tenue y adornos separados dentro de su panel, excluyendo trama pequeña y líneas
finas que recorren el panel. Las figuras que atraviesan casillas mantienen las
protecciones anteriores.

## Qué se comprueba

`tests/holdout_group_truth.py` contiene puntos anotados sobre letras, palabras,
figuras, ingredientes, pequeños adornos y plantas. Las expectativas proceden
de la inspección de los originales, no de las cajas calculadas por el detector.
Se exige un propietario único para todos los puntos de cada composición y se
rechaza que incluya el motivo principal de otra.

Se corrigieron tres puntos inicialmente colocados en espacio vacío, tras
inspeccionar sus coordenadas sobre los originales: el extremo derecho de flores
del grupo trece, el de corazones del diecisiete y una hoja de «Choose joy».
`*-witness-check.png` documenta la inspección. No se relajaron los recuentos ni
se eliminaron casos para conseguir resultados positivos.

Los cinco originales y veinte variantes de escala, iluminación y temperatura
de color pasan sus comprobaciones de pertenencia, vecinos y conservación de
píxeles. La prueba de la interfaz real añade alineación en la misma cuadrícula,
ausencia de cortes inferidos y explicación del tamaño físico seleccionado.

`verified/old-image-comparison.json` compara **16 imágenes anteriores** con la
comparación de tinta completa desactivada y activada: **16 cantidades conservadas
y 15 resultados completos idénticos**, incluidos límites, cuadrículas, estados y
motivos de revisión. El otro original de números compactos conserva veinte grupos,
con cambios de uno o dos píxeles en algunos límites y menos de un píxel en la fase
de la cuadrícula; sus nueve variantes conservan todos los testigos y los vecinos.
Las familias son números, alfabeto, cócteles, frases, animales, flores y transportes,
además de un mosaico y controles sintéticos de mariposas. No se afirma cobertura
fotográfica exclusiva de todas las colecciones.

Los registros de la ejecución definitiva están en `verified-tests.txt` y
`workflow-test.txt`. Incluyen los controles de independencia, otras cantidades,
guías confirmadas y composiciones incompletas. No se ejecutó la batería completa.
**Resultado definitivo: 34 pruebas dirigidas pasan** (33 en la ejecución principal
y una del flujo real de las cinco imágenes). La principal terminó en 609,955
segundos; la del flujo real, en 30,994 segundos. No quedan fallos de ese conjunto.

## Dibujos detectados y cortes físicos

La interfaz muestra el dibujo detectado en **cian discontinuo** y el corte físico
con **línea continua**. Cuando el dibujo no cabe, explica cuántos grupos exceden
el tamaño seleccionado y solicita ajustar la medida o comprobar la escala.
No modifica automáticamente esa medida ni elimina los avisos.

El flujo real de la aplicación, con los mismos cuadrados de cinco pulgadas de
las capturas, produce estos estados (`verified/ui-results.json`):

| Imagen | Grupos | Dibujo que excede el corte | Cortes que se solapan |
|---|---:|---:|---:|
| Letras | 12 | 12 | 0 |
| Números planos | 20 | 17 | 20 |
| Frases | 16 | 10 | 16 |
| Fieltro | 20 | 19 | 20 |
| Animales | 12 | 12 | 0 |

Estos avisos siguen siendo necesarios con la escala supuesta. Detectar veinte
grupos completos no implica que veinte cuadrados de cinco pulgadas puedan
contenerlos sin solapamiento. La imagen generada no acredita medidas reales.
Las capturas `verified/*-5in-ui.png` muestran ambos conceptos; los archivos
`verified/*-groups.png` muestran únicamente los límites de agrupación corregidos.

## Reproducción

Desde la raíz, con el entorno virtual y `QT_QPA_PLATFORM=offscreen`:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_holdout_groups -v
.venv\Scripts\python.exe -m unittest tests.test_number_compositions tests.test_alphabet_compositions tests.test_composition_content tests.test_accessory_columns tests.test_accessory_ownership tests.test_compound_grid tests.test_customer_cut_boundaries -v
```

`audit.py` reproduce las entradas sin alterar producción. `render_results.py`
guarda el flujo real de la interfaz. El resultado acredita las entradas guardadas
y sus controles; la pertenencia ambigua y la calibración física requieren revisión.
