# Reparacion v1.0.49 de actualizacion y Preview Forge

## Objetivo

Evitar que una actualizacion deje `forge_iphone_profile.py` nuevo junto a un
`console_encoding.py` viejo, y hacer visible cualquier fallo al cargar Preview
SDR/HLG.

## Causa confirmada

El ZIP v1.0.48 contiene `console_encoding.py` con `ffmpeg_tool_command`, pero
`updater.py::DEFAULT_UPDATEABLE_FILES` no permite instalarlo. El actualizador
puede avanzar `version.json` a 1.0.48 mientras conserva el helper viejo. Al
seleccionar SDR o HLG, el import de `forge_iphone_profile` falla antes del
bloque que muestra errores, por lo que Tkinter solo escribe el traceback en la
consola.

## Diseno aprobado

1. Incluir `console_encoding.py` en la allowlist del actualizador y verificar
   con una prueba de paquete que se copie junto a `version.json`.
2. Dar a `forge_iphone_profile.py` un fallback local, limitado a resolver
   `ffmpeg` y `ffprobe`, si el helper antiguo no exporta
   `ffmpeg_tool_command`. Asi una instalacion afectada puede ejecutar Preview
   al aplicar v1.0.49 aunque su actualizador anterior siga omitiendo el helper.
3. Mover el import de perfil iPhone dentro del manejo de errores de Preview y
   de Procesar, para que un import fallido se muestre como `Preflight iPhone`
   en vez de quedar silencioso.
4. Aumentar `version.json` a `1.0.49` y regenerar el manifiesto y ZIP
   code-only. No incluir DB, calendarios, configuracion, videos ni historiales.

## Compatibilidad y limites

- La salida sigue usando CPU (`libx265`); no se agrega ni se requiere GPU.
- El fallback no oculta una ausencia real de FFmpeg: devuelve el nombre de la
  herramienta para que el preflight muestre el error existente.
- La reparacion no modifica datos operativos ni reescribe manifiestos de
  tandas.
- Las pruebas de FFmpeg en este entorno estan bloqueadas por `WinError 50` al
  iniciar subprocesos. La publicacion requerira pruebas unitarias, compilacion,
  inspeccion del ZIP y, en una maquina compatible, prueba real de Preview SDR.

## Criterios de aceptacion

- Un paquete que lista `console_encoding.py` lo instala atomically.
- Importar `forge_iphone_profile` funciona si el helper instalado carece de
  `ffmpeg_tool_command`.
- Un fallo de import de perfil aparece en un popup de Preflight, no solo en la
  consola Tkinter.
- El release v1.0.49 incluye todos los archivos code-only esperados y su hash
  coincide con el manifiesto publicado.
