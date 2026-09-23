# Actualización de Lalikul Cut Prep — 23 de septiembre de 2026

## Cómo instalar esta versión

1. Cierra la aplicación.
2. En GitHub, pulsa **Code → Download ZIP**. Extrae todo el contenido en una
   carpeta nueva con una ruta corta, por ejemplo **Escritorio\Lalikul**.
   No ejecutes la aplicación dentro del ZIP.
3. Ejecuta **setup.bat** en esa carpeta. Necesita conexión a Internet para
   instalar las dependencias. Espera al mensaje **Setup complete**.
4. Abre el acceso directo **Lalikul Cut Prep.lnk** que se acaba de crear allí.
   Un acceso directo antiguo puede abrir la versión anterior.

No copies la carpeta `.venv` de la instalación anterior. Los perfiles de máquina
y las fotos de referencia personales se guardan fuera de la carpeta del programa
y se conservan al actualizar con el mismo usuario de Windows.

Si necesitas instalar Python, recomendamos **Python 3.12 de 64 bits**, con
**Add python.exe to PATH** activado. La instalación detecta rutas demasiado
largas antes de descargar paquetes y explica cómo mover la carpeta. Si aparece
un error, conserva el mensaje; no continúes como si la instalación hubiera acabado.
Si después de completar la instalación la ventana no abre, ejecuta
**run_console.bat** para ver el error.

## Si no se detecta ningún dibujo

**Adjust panel grid** sigue disponible con una imagen cargada, aunque el resultado
sea cero. Permite volver a estimar la cuadrícula o introducir filas y columnas,
ajustarlas y pulsar **Use this grid and detect again**. No es necesario cargar
otra imagen para salir de esa situación.

## Referencia de la cama

La foto de la cama vacía sigue asociada al perfil de máquina. Cuando coincide
con la foto actual, ayuda a localizar la tela, filtrar el exterior y delimitar
la distribución de sus dibujos. La aplicación indica si la referencia se ha
aplicado en la última detección. Que aparezca como disponible en el perfil no
significa que haya podido coincidir con todas las fotografías.

La referencia incluida de Epilog sigue en el paquete. Las fotos tomadas desde
otro encuadre pueden necesitar una referencia nueva de esa misma cámara.

## Limitaciones que se mantienen

La detección sobre fondos negros u oscuros todavía puede fallar; no se considera
resuelta para todas las colecciones. Revisa los dibujos, sus accesorios y los
cortes antes de exportar. Los avisos morados de dibujo recortado pueden ser
correctos si el tamaño de corte configurado es menor que la composición.
