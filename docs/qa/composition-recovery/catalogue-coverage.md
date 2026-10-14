# Cobertura del catálogo LaLiKuL

Revisión: 14/10/2026. Fuente: [catálogo de productos](https://lalikul.com/collections/all-products), que muestra 29 productos. Se ha revisado el inventario y las fichas accesibles, no una fotografía de producción de cada colección. Las imágenes generadas y sus transformaciones sirven como regresión; no certifican todas las telas reales.

| Colección o familia | Evidencia disponible / pendiente |
|---|---|
| Alphabet & Numbers | Original de prueba aportado: 24 pares letra/dibujo, nueve variantes fotográficas. Las cifras y composiciones nuevas requieren más originales. |
| Alphabet & Numbers (Spanish) | Misma tipología, pendiente de original con Ñ, tildes y cifras. |
| Animals, Baby Animals, Cheeky Animals | Pruebas de grupos y animales con accesorios separados. No equivalen a validar los tres productos reales. |
| Birds | Original aportado con última fila incompleta: excluir seis, conservar 18 completos. |
| Butterflies | Captura de Eugenio; falta original de esa colección para prueba automática exacta. |
| Cats | Captura de Eugenio; falta original exacto. |
| Dogs | Captura de Eugenio y control sintético de paneles; falta original exacto. |
| Christmas | Capturas y control generado; falta la imagen limpia de la última captura problemática. |
| Flowers, Folk Art | Controles florales generados, incluyendo una composición que cruza celdas; no validación de cada producto. |
| Hearts & Flowers | Captura y control sintético; falta original exacto. |
| Transport & Vehicles | Controles con sombras, fondos estampados y figuras que ocupan más de una celda. |
| Autumn & Fall, Cocktails, Dinosaurs, Fairies, Farm | Pendientes de originales. Los nuevos prompts ejercitan detalles separados, trazos finos y figuras anchas. |
| Flower Power, Modern Flowers | Pendientes de originales; riesgo de confundir decoración repetida y composición principal. |
| Happy Quotes, Sunshine Quotes | Pendientes. La aplicación no interpreta el significado del texto; debe conservar la composición completa. El catálogo los enumera como charm packs. |
| Sweet Dreams (Beige & Cream), Sweet Dreams (Grey), Yellow | Pendientes de originales de poco contraste. Las pruebas genéricas de bajo contraste no certifican estas colecciones. |
| USA | Pendiente de original; estrellas y rayas pueden competir con las divisiones del panel. |
| Rainbow mini-charms Panel | Formato pendiente de validar con medida real y fotografía. No aplicar automáticamente 5 pulgadas. |
| Hexagons Panel | Fuera del exportador actual de rectángulos: necesita geometría hexagonal. |

La [ficha de Hexagons Panel](https://lalikul.com/products/hexagons-panel) especifica 81 hexágonos de 3,5 pulgadas de alto. Esto es una diferencia de formato, no una variación de umbral de detección.

## Criterios de aceptación

- Cada composición completa tiene un único propietario; letras, accesorios y detalles no crean cortes extra.
- Las filas y columnas siguen una única geometría respaldada por la imagen. Una tela fotografiada inclinada no se fuerza a los ejes de la pantalla.
- Los dibujos incompletos y los cortes que salen del área de trabajo no se exportan.
- Una cuadrícula discutida no se rellena automáticamente con cortes inventados.
- El tamaño físico de corte y la calibración se verifican aparte. Una imagen generada no garantiza una escala real de pulgadas.
- Cada imagen generada debe inspeccionarse antes de usar el número solicitado como resultado esperado: el generador puede producir otra cantidad o dibujos partidos.
