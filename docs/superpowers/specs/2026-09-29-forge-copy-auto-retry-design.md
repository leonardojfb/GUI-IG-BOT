# Reintento automático de copias Forge

## Objetivo

Evitar que una tanda iPhone quede incompleta por un fallo transitorio de una
copia, sin publicar, registrar ni reutilizar una salida que no haya superado
todas las validaciones.

## Diseño aprobado

Cada copia iPhone se procesará en un máximo de cinco intentos dentro de la
misma ejecución de Forge. Cada intento invoca el render actual sobre un archivo
temporal nuevo; `render_validated_copy` sólo publica el resultado cuando han
pasado el contrato del contenedor, la decodificación y el QC visual.

Se reintentan los fallos que ocurren al renderizar o validar una copia, incluido
el QC visual. No se reintentan errores previos a una copia: fuente ausente o
cambiada, perfil inválido, preflight bloqueado, manifiesto inválido o conflicto
de identidad. Esos errores no pueden arreglarse simplemente reintentando.

Si un intento pasa, se devuelve la misma tupla de copia existente con la
cantidad de intentos en los parámetros de transformación y se sigue usando el
registro normal. Si los cinco fallan, la copia permanece `pending`, se guarda el
diagnóstico del último fallo junto con el historial resumido de intentos y la
tanda sigue `incomplete`. Las copias que ya validaron nunca se reprocesan.

## Límites y seguridad

- El límite es exactamente cinco intentos por copia y ejecución; no hay bucle
  infinito ni cambios silenciosos de perfil, metadata, fuente o efectos.
- Las copias se conservan solamente tras pasar la validación completa actual.
- Un reintento de una tanda pendiente conserva número de copia, hash de fuente
  y metadata; una salida publicada existente se valida para recuperación y no
  se sobreescribe.
- El resultado para el usuario indicará cuántos reintentos se agotaron cuando
  aún quede una copia pendiente.

## Pruebas

Probar una función pequeña de reintento sin FFmpeg: que un fallo seguido de
éxito complete en el segundo intento y registre el número; que cinco fallos
propaguen un error que incluya el contador y el último diagnóstico. Probar que
errores de preflight/identidad no pasan por el helper. Mantener los tests de
validación visual existentes para demostrar que un resultado no conforme sigue
rechazado si agota los cinco intentos.
