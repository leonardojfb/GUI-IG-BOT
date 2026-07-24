# Lote cartesiano de fotos y videos

## Objetivo

Generar una salida independiente por cada pareja foto-video. La regla aplica
si hay más de un elemento en cualquiera de los dos grupos:

- 1 video x N fotos genera N videos.
- N videos x 1 foto genera N videos.
- N videos x M fotos genera N x M videos.
- 1 video x 1 foto conserva una única salida.

Cada salida contiene solo la foto correspondiente, no una composición de
todas las fotos seleccionadas.

## Configuración

La configuración global de fotos permanece como predeterminada para todas las
salidas: frame/timeline, duración, tamaño, posición, transparencia y relación.
Una foto marcada como `Editar individual` puede cambiar sus valores propios.

Cuando se seleccionan varias fotos y varios videos, el timeline se limita a
los primeros cinco segundos y el frame elegido se sincroniza en todas las
fotos. La excepción individual conserva tamaño, posición, transparencia,
duración y relación, pero no modifica ese frame común de lote.

## Render y nombres

El orden de ejecución es foto exterior y video interior: primero Foto 1 sobre
todos los videos, después Foto 2 sobre todos los videos, y así sucesivamente.
Los archivos se guardan como `<video>_fotoNN_editado.mp4`; si ya existe un
nombre, se añade un sufijo numérico para no sobrescribirlo.

## Preview y validación

En modo de lote, el preview muestra únicamente la foto elegida en el selector
de timeline, porque representa el archivo que se va a producir para esa foto.

La validación automatizada cubrirá los tres tamaños de lote (1xN, Nx1 y NxM),
el conteo de trabajos y el orden foto-video. También se mantendrán las pruebas
de geometría y un smoke test de FFmpeg para una combinación real.
