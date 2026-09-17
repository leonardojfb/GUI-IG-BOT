# R13 ios-remote lectura

Fecha: 2026-09-17

## Alcance validado

- `read_snapshot()` carga un snapshot local y `sanitize_snapshot()` elimina
  recursivamente cookies, session IDs, tokens, passwords, CSRF, headers de
  autorizacion y claves equivalentes.
- `write_sanitized_snapshot()` escribe schema v1 con reemplazo atomico y no
  conserva secretos en el archivo exportado.
- `ios_remote_adapter.load_ios_remote_snapshot()` normaliza contenedores,
  cuentas y perfiles allowlisted para Forge y calcula un hash `sha256:` del
  snapshot normalizado.
- El adapter es sólo lectura y no acepta ni persiste cookies, tokens,
  contraseñas o sesiones.
- No se implementa login, captura de cookies, requests a Instagram ni
  publicacion automatica. El export es estrictamente read-only.
- Release/updater incluyen el modulo sin modificar el bootstrap.

## Verificacion

- `tests/test_ios_remote_read.py`: `3 passed`.
- Incluye prueba de fuente corrupta/estructura invalida y limpieza de temporales.

## Limites

El contrato actual recibe un snapshot JSON ya generado. La integración
automática con el servicio real de ios-remote y la selección de perfiles
sincronizados desde GUI requieren identificar un formato estable; se mantiene
separada de cualquier mecanismo de publicación.
