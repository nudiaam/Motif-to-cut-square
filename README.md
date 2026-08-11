# Lalikul Cut Prep

<p align="center">
  <img src="app/assets/lalikul-cut-prep.png" alt="Logotipo de Lalikul Cut Prep" width="180">
</p>

Demo local para Windows que convierte una imagen de la cama de una cortadora láser en centros de motivo y cuadrados o rectángulos de corte exportables como SVG.

La configuración inicial utiliza **Epilog Fusion Maker 36**, una cama de **36 × 24 in** y cortes globales de **5 × 5 in**. También permite crear máquinas personalizadas, cambiar unidades y modificar el tamaño de corte.

> **Estado del proyecto:** prototipo funcional para validación. No controla la máquina, no inicia cortes y no configura potencia, velocidad, frecuencia, enfoque ni materiales.

## Documentación para dos públicos

La documentación está dividida para no obligar a un usuario normal a leer detalles de programación:

- Este `README.md` explica qué hace la app, cómo instalarla y cómo usarla. Es también la portada del proyecto en GitHub.
- El [manual completo de usuario](docs/Manual_de_usuario_Lalikul_Cut_Prep.docx) contiene instrucciones detalladas, capturas, estados, parámetros y resolución de problemas.
- La [guía para desarrollo](docs/DEVELOPER_GUIDE.md) describe la arquitectura, el entorno virtual, las pruebas y las decisiones técnicas.

## Inicio rápido para usuarios de Windows

### 1. Descargar y descomprimir

En GitHub, pulsa **Code → Download ZIP**. Extrae todo el ZIP a una carpeta normal antes de continuar. No ejecutes la aplicación directamente dentro del ZIP.

### 2. Instalar Python

Instala [Python para Windows](https://www.python.org/downloads/windows/) 3.10 o posterior. Durante la instalación activa **Add python.exe to PATH**.

### 3. Preparar la aplicación una sola vez

Haz doble clic en `setup.bat` y espera a que aparezca `Setup complete`.

El instalador crea `.venv`, un entorno de Python privado para esta aplicación, e instala PySide6, OpenCV y NumPy. No instala Node.js ni crea un servidor web.

### 4. Abrir con el icono de la app y sin terminal

Haz doble clic en **`Lalikul Cut Prep.lnk`**, que `setup.bat` crea automáticamente en la carpeta principal.

Este es el acceso recomendado: muestra el logotipo de Lalikul Cut Prep y abre la interfaz mediante `pythonw.exe`, sin dejar una terminal visible ni utilizar el icono genérico de Python.

También existen dos alternativas:

- `Lalikul Cut Prep.vbs`: inicia la app sin terminal si el acceso directo no está disponible, aunque el archivo VBS conserva el icono genérico de Windows en el Explorador.
- `run.bat`: delega en el mismo lanzador oculto y se cierra inmediatamente. Windows puede mostrar un destello breve de consola porque los archivos `.bat` se ejecutan mediante `cmd`.
- `run_console.bat`: mantiene la terminal abierta deliberadamente para mostrar errores técnicos. Úsalo solo para diagnóstico.

## Flujo de trabajo habitual

1. Selecciona la máquina y confirma **Work Area** y **Working units**.
2. Carga una imagen mediante **Paste Image**, `Ctrl+V`, **Open Image** o **Demo Image**.
3. Si es necesario, desmarca **Lock image placement** para mover o escalar la imagen desde las esquinas sin deformarla. Vuelve a bloquearla al terminar.
4. Pulsa **Detect**.
5. Revisa los centros y los cuadrados. Muévelos, añade centros manuales o desactiva detecciones cuando sea necesario.
6. Resuelve todos los cortes rojos y naranjas.
7. Pulsa **Verify Export**.
8. Pulsa **Export SVG** y confirma el tamaño físico al importarlo en el software receptor.

## Moverse y hacer zoom como en Illustrator

El canvas no es una vista fija. Puedes ampliar una zona de trabajo y desplazarte manteniendo intactas las coordenadas físicas:

| Acción | Control en Windows |
|---|---|
| Mano temporal | Mantén `Espacio` y arrastra |
| Herramienta Mano | Pulsa `H` y arrastra |
| Desplazamiento alternativo | Arrastra con el botón central del ratón |
| Herramienta Zoom | Pulsa `Z` y haz clic |
| Alejar con Zoom | `Alt + clic` con la herramienta Zoom |
| Zoom bajo el cursor | `Ctrl + rueda del ratón` |
| Acercar / alejar | `Ctrl + =` / `Ctrl + -` |
| Encajar toda la cama | `Ctrl + 0` |
| Volver a edición normal | `V` o `Esc` |

La rueda sin `Ctrl` desplaza la vista verticalmente; `Shift + rueda` la desplaza horizontalmente. El zoom se centra en la posición del cursor para no perder el punto que estabas inspeccionando.

Estos controles siguen los atajos principales de visualización de [Adobe Illustrator](https://helpx.adobe.com/illustrator/using/default-keyboard-shortcuts.html), adaptados a la cama física de esta aplicación.

## Copy Background Image de Epilog

La demo **no se conecta directamente a las cámaras de Epilog**. Está preparada para reutilizar la imagen que Epilog Dashboard copia al portapapeles:

**Epilog Dashboard → Copy Background Image → portapapeles de Windows → Lalikul Cut Prep → Ctrl+V → detección → cuadrados → SVG**

Epilog explica que **Copy Background Image** utiliza el sistema IRIS para obtener una captura de la cama y después pegarla en otra aplicación. En este proyecto, Lalikul Cut Prep ocupa el lugar de esa aplicación receptora. Consulta la [explicación oficial de Epilog](https://support.epiloglaser.com/laser-machine/fusion-galvo/usage-and-operation/how-and-when-to-use-the-copy-background-image-feature/).

## Significado de los colores

| Color | Estado | Qué hacer |
|---|---|---|
| Verde | Corte válido | Puede exportarse. |
| Amarillo | Detección seleccionada | Puedes inspeccionarla o moverla. |
| Naranja | Colisión | Separa los cortes o desactiva uno. |
| Rojo | Fuera de la cama | Mueve el centro o reduce el tamaño de corte. |
| Gris | Desactivado | No se exporta mientras siga desactivado. |

Dos cortes activos se consideran en colisión si se superponen o si sus bordes se tocan exactamente. Ambos pasan a `COLLISION` y se excluyen del SVG hasta resolver el problema.

## Controles principales

### Machine / Work Area

- **Machine** selecciona la máquina que define la cama física.
- **Add machine...** guarda perfiles personalizados con nombre, anchura, altura y unidad.
- **Working units** cambia las medidas visibles entre pulgadas, centímetros y milímetros.
- El origen está en la esquina superior izquierda. X crece hacia la derecha e Y hacia abajo.

### Bed / Image

- La imagen se carga centrada y contenida en la cama, manteniendo su proporción.
- **Lock image placement** protege la imagen mientras editas cuadrados.
- Al desbloquearla, arrastra el interior para moverla y las esquinas para escalarla.
- **IMAGE SCALE** muestra cuántos píxeles representan una unidad física horizontal y verticalmente.

### Global Cut Size

- El valor inicial es **5 × 5 in**.
- Con **Keep cut square** activo puedes editar Width o Height; la otra medida se sincroniza automáticamente.
- Al desactivarlo puedes crear rectángulos libres.

### Detection Settings

| Parámetro | Predeterminado | Función |
|---|---:|---|
| Sensitivity | 65 | Detecta diferencias respecto al fondo. |
| Minimum area | 500 px² | Descarta grupos demasiado pequeños. |
| Cleanup | 25% | Reduce ruido y cierra huecos cortos. |
| Merge distance | 0.35 in | Agrupa fragmentos próximos de un mismo motivo. |

Haz doble clic sobre cualquiera de estos controles para restaurar su valor predeterminado. Después de cambiar un ajuste, vuelve a pulsar **Detect**.

## Edición manual

- Haz clic en un centro o cuadrado para seleccionarlo y arrástralo para moverlo.
- Activa **Add Center** y haz clic en la cama para crear una detección manual.
- Pulsa **Delete** para borrar la selección.
- Usa **Clear Detections** para borrar todas las detecciones.
- Usa **Include in export** para desactivar un corte sin eliminarlo.

## Exportación y verificación

El SVG contiene únicamente cortes que estén:

- activados;
- completamente dentro de la cama;
- libres de colisiones.

No incluye la fotografía, textos, centros, etiquetas ni bounding boxes.

Por defecto, **Export units** utiliza la misma unidad que **Working units**. Si eliges otra unidad, la app muestra una advertencia. Comprueba siempre el tamaño de cama en el programa receptor.

**Verify Export** reconstruye la geometría SVG en píxeles y muestra el error máximo del recorrido imagen → coordenadas físicas → SVG → imagen. El contorno púrpura permite comparar el resultado.

La opción **Write debug JSON beside SVG** genera un archivo adicional con coordenadas, escalas y estados para diagnóstico.

## Ayuda dentro de la aplicación

- Pulsa los pequeños iconos circulares de información para abrir explicaciones en inglés.
- Mantén el cursor quieto sobre un botón de la barra superior durante aproximadamente 1,3 segundos para ver su ayuda.

## Problemas frecuentes

### La aplicación dice que falta o está roto el entorno

Ejecuta `setup.bat` otra vez. Si Python fue desinstalado, reinstálalo primero.

### Ctrl+V no carga la imagen

Vuelve a Epilog Dashboard, pulsa **Copy Background Image** y pega inmediatamente. También puedes probar **Open Image** con un PNG, JPG, JPEG o BMP.

### La aplicación no abre y el lanzador oculto no muestra el motivo

Ejecuta `run_console.bat`. La terminal permanecerá abierta y mostrará el error técnico.

### El SVG llega con tamaño incorrecto

Haz coincidir **Export units** con **Working units** y comprueba el tamaño de página al importar.

## Límites actuales

- No hay conexión directa con cámaras, Epilog Dashboard, PrintAPI ni la cortadora.
- El detector utiliza OpenCV, no YOLO ni un modelo entrenado.
- No hay corrección de perspectiva u homografía.
- La relación imagen ↔ cama, el origen y el SVG deben validarse físicamente antes de producción.
- El perfil predeterminado es Epilog Fusion Maker 36, pero pueden añadirse otras máquinas.

## Desarrollo y pruebas

La información técnica se mantiene fuera de la guía principal para que esta página siga siendo útil a usuarios no programadores. Consulta [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) para preparar el entorno desde PowerShell, conocer la estructura del código y ejecutar las pruebas.

## Estado de publicación

Antes de distribuir públicamente una versión de producción conviene añadir un instalador firmado, una licencia explícita, control de versiones y una sección de releases. Esta carpeta contiene actualmente una demo local validable, no un paquete de producción certificado.
