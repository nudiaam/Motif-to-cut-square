# Revisión unificada — 13/10/2026

Flujo: Prepare image → Detect + check → Review cuts → Export SVG.
Review cuts incluye edición, previsualización, resumen de salida y opciones de
exportación. El resumen se calcula al entrar y se actualiza tras cambios y
exclusiones. Exportar comprueba de nuevo la geometría y abre el diálogo de guardado
en una pulsación, conservando las confirmaciones de avisos y límites de exportación.

Validación: 61 pruebas de interfaz, diagnóstico, límites y exportación ejecutadas.
58 pasaron; tres esperaban el texto anterior de orientación. Se actualizaron esas
expectativas y se repitieron las tres, junto con la nueva prueba de exportación
en una pulsación: cuatro correctas. No se modificó el detector.

`review.png` muestra la interfaz real con la imagen demo. Se usa para verificar
distribución y visibilidad de controles, no como evidencia de detección correcta.
