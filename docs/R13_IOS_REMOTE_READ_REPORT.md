# R13 ios-remote lectura

Fecha: 2026-09-17

## Alcance validado

- `read_snapshot()` carga un snapshot local y `sanitize_snapshot()` elimina
  recursivamente cookies, session IDs, tokens, passwords, CSRF, headers de
  autorizacion y claves equivalentes.
- `write_sanitized_snapshot()` escribe schema v1 con reemplazo atomico y no
  conserva secretos en el archivo exportado.
- No se implementa login, captura de cookies, requests a Instagram ni
  publicacion automatica. El export es estrictamente read-only.
- Release/updater incluyen el modulo sin modificar el bootstrap.

## Verificacion

- `tests/test_ios_remote_read.py`: `3 passed`.
- Incluye prueba de fuente corrupta/estructura invalida y limpieza de temporales.

## Limites

El contrato actual recibe un snapshot JSON ya generado. La integracion con un
driver concreto de ios-remote requiere identificar su formato estable y se
mantendra separada de cualquier mecanismo de publicacion.
