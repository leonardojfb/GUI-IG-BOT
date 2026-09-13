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

## Compatibilidad de actualizacion

- Los usuarios actuales siguen escribiendo manifest v1.
- Leer un manifest v2 no reescribe ni degrada el archivo.
- Telegram conserva su filtro por `publication_target`; las entradas no Telegram no se envian por accidente.
- La sustitucion v2 esta separada de `replace_entries()` para evitar cambiar Logistica actual antes de migrarla.

## Pruebas agregadas

- `tests/test_calendar_manifest.py::test_load_entries_accepts_manifest_v2_without_rewriting`
- `tests/test_calendar_manifest.py::test_build_entry_v2_stores_lane_dimensions_and_manual_target`
- `tests/test_calendar_manifest.py::test_replace_entries_v2_replaces_only_target_lane_and_window`

## Pendiente R07

- Lock de escritor y journal de reconciliacion entre manifest y SQLite.
- Revision/diff de manifest antes de aplicar cambios.
- Migracion formal de v1 a v2 con preview.
- Snapshots de horarios por carril.
- Politica Trial y fixtures historicos bajo carriles.
