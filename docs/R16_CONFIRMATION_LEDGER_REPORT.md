# R16 Confirmacion persistente

Fecha: 2026-09-17

## Alcance validado

- `build_callback()` y `parse_callback()` usan formato `v1|action|entity_id`
  con IDs restringidos y rechazo de versiones desconocidas.
- `ingest_callback()` guarda una inbox persistente y deduplica por
  `external_id`, evitando doble aplicación de un callback externo.
- Puede recibir `authorize_fn` y rechazar el callback antes de insertar nada;
  el resultado `unauthorized` no deja evento pendiente.
- `undo_confirmation()` ejecuta la acción inversa antes de marcar el evento
  como `undone`; una segunda llamada no vuelve a ejecutar la acción.
- El ledger conserva usuario, payload, entidad, estado y timestamps.
- Release/updater incluyen el módulo sin tocar el bootstrap.
- El webhook acepta callbacks versionados cuando recibe una conexión SQLite
  opt-in, persiste el evento antes de editar el mensaje y responde como
  duplicado sin repetir la mutación.
- El despliegue HTTP activa esa persistencia sólo con `CONFIRMATION_DB_PATH`;
  sin la variable conserva el callback legacy `pub`.
- Cuando la persistencia está activa, el webhook construye una política
  deny-by-default desde `TELEGRAM_ALLOWED_USER_IDS` (IDs separados por coma) y
  no inserta confirmaciones de usuarios ausentes de la allowlist.

## Limites

Falta desplegarlo en Railway con la variable de allowlist configurada y
conectar acciones de limpieza por IDs/carriles.
