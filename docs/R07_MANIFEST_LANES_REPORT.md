# R07 manifest v2 y carriles

Fecha: 2026-09-13

## Alcance implementado

- `calendar_manifest.py` ahora acepta lectura de manifest `version: 1` y `version: 2`.
- La escritura legacy sigue usando `MANIFEST_VERSION = 1`; no cambia el formato que generan los flujos actuales.
- `build_entry_v2()` crea entradas explicitas con:
  - `manifest_entry_version`
  - `lane`
  - `placement`
  - `media_class`
  - `method`
  - `policy_snapshot`
  - `display_filename`
- `replace_entries_v2()` reemplaza solo por `username + lane + ventana de dias` y conserva otros carriles de la misma cuenta.
- Los destinos manuales siguen desactivados para `build_entry()` v1; solo `build_entry_v2()` puede construirlos como contrato preparatorio.
- Toda escritura del manifest pasa por un lock local `.calendar_manifest.lock` para bloquear escritores concurrentes.
- Toda escritura crea `.calendar_manifest_journal.json` antes del reemplazo atomico; si el reemplazo termina bien se limpia, y si falla queda como evidencia para reconciliacion.
- `preview_replace_entries_v2()` calcula el diff sin escribir: entradas agregadas, removidas, conservadas, total final, selector y revision base.
- `apply_manifest_preview()` aplica solo si la revision base sigue vigente; si otro proceso cambio el manifest entre preview y apply, rechaza la escritura.

## Compatibilidad de actualizacion

- Los usuarios actuales siguen escribiendo manifest v1.
- Leer un manifest v2 no reescribe ni degrada el archivo.
- Telegram conserva su filtro por `publication_target`; las entradas no Telegram no se envian por accidente.
- La sustitucion v2 esta separada de `replace_entries()` para evitar cambiar Logistica actual antes de migrarla.
- Si queda un journal pendiente o un lock activo, las escrituras nuevas se bloquean antes de modificar el archivo principal.
- El preview no modifica `calendar_manifest.json`, por lo que la UI futura podra mostrar cambios antes de confirmar.
- El apply protegido evita aplicar una revision obsoleta sobre cambios externos.

## Pruebas agregadas

- `tests/test_calendar_manifest.py::test_load_entries_accepts_manifest_v2_without_rewriting`
- `tests/test_calendar_manifest.py::test_build_entry_v2_stores_lane_dimensions_and_manual_target`
- `tests/test_calendar_manifest.py::test_replace_entries_v2_replaces_only_target_lane_and_window`
- `tests/test_calendar_manifest.py::test_replace_entries_v2_blocks_when_manifest_lock_exists`
- `tests/test_calendar_manifest.py::test_replace_entries_v2_writes_journal_and_cleans_after_success`
- `tests/test_calendar_manifest.py::test_failed_manifest_write_keeps_journal_and_releases_lock`
- `tests/test_calendar_manifest.py::test_preview_replace_entries_v2_returns_diff_without_writing`
- `tests/test_calendar_manifest.py::test_apply_manifest_preview_rejects_stale_revision`

## Pendiente R07

- Migracion formal de v1 a v2 con preview.
- Snapshots de horarios por carril.
- Politica Trial y fixtures historicos bajo carriles.
- Reconciliacion asistida del journal contra SQLite cuando una escritura queda interrumpida.
