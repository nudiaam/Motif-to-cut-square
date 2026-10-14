# Actualización del 14 de octubre de 2026

Esta versión mejora la detección de composiciones con varias partes: letras o
números con dibujos, frases con adornos, cócteles con ingredientes y animales
con accesorios. Contrasta el contenido completo y la distribución de los grupos
antes de aceptar una cuadrícula. Los dibujos incompletos en la fotografía y los
cortes fuera de la cama quedan excluidos de la exportación.

La barra de análisis está integrada en la parte inferior y permite cancelar.
La revisión de cortes y la comprobación de salida comparten una pantalla.
Los límites del dibujo detectado aparecen en cian discontinuo; los contornos
continuos corresponden al corte solicitado.

## Cómo actualizar

1. Cierra la aplicación.
2. En [GitHub](https://github.com/nudiaam/Motif-to-cut-square), elige
   **Code → Download ZIP**.
3. Extrae el ZIP completo en una carpeta nueva y corta, por ejemplo
   **Escritorio\Lalikul**.
4. Ejecuta **setup.bat** y espera a que indique **Setup complete**.
5. Abre **Lalikul Cut Prep.lnk** de esa carpeta nueva. No reutilices el acceso
   directo ni la carpeta `.venv` de la instalación anterior.

Los perfiles de máquina y las referencias de cama del usuario se conservan
fuera de la carpeta de instalación. La referencia predeterminada está incluida.

## Qué comprobar al probarla

Comprueba que cada grupo incluye todas sus partes y que no hay cortes duplicados.
Revisa la escala de la imagen y el tamaño de corte: un grupo bien detectado puede
seguir siendo demasiado grande para el cuadrado elegido. La aplicación mantiene
ese aviso y no cambia el tamaño automáticamente.

Se han verificado los originales de regresión y sus variaciones; el usuario
también ha confirmado que las nuevas imágenes de prueba han pasado. Esto no
establece una tasa de acierto para todas las telas posibles. Sigue siendo
necesario revisar cada resultado antes de exportar. Los fondos oscuros conservan
las limitaciones ya documentadas.

La evidencia de la corrección más reciente está en el
[informe de validación](qa/holdout-20261014/README.md), disponible en GitHub.
