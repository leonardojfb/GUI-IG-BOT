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
- `preview_migrate_manifest_v1_to_v2()` convierte entradas legacy v1 a contrato v2 sin escribir.
- La migracion v1->v2 preserva `id`, captions, filenames y campos existentes; agrega `manifest_entry_version`, `lane`, `placement`, `media_class`, `method`, `display_filename` y `policy_snapshot`.
- `build_entry_v2()` guarda `schedule_snapshot` normalizado con `day`, `slot`, `lane` y `placement`; rechaza snapshots cuyo carril/placement/dia/slot no coinciden con la entrada.
- La migracion v1->v2 agrega `schedule_snapshot` minimo por entrada para conservar dia, slot y carril aunque el manifest legacy no tenga hora exacta.
- La politica Trial queda fijada en v2: `delivery_kind=trial` solo puede usar `publication_target=instagram_trial_reel` y `lane=trial_reel`.
- Las entradas no Trial no pueden escribirse dentro de `lane=trial_reel`, y los previews por carril rechazan batches que no pertenecen al carril objetivo.
- `policy_snapshot` agrega `trial_policy`, `publication_target` y `lane` para dejar evidencia auditable de la politica aplicada.
- `manifest_migration_cli.py` permite ejecutar `preview` y `apply` de la migracion v1->v2 desde CLI con salida JSON.
- La CLI puede exigir confirmacion explicita con `apply --require-confirmation --yes`.
- `inspect_manifest_journal()` inspecciona si hay journal pendiente, verifica que el manifest siga legible y puede sumar un `PRAGMA integrity_check` read-only contra SQLite.
- `clear_manifest_journal()` limpia un journal pendiente solo con confirmacion explicita, manifest legible y SQLite integro cuando se provee `db_path`.
- `manifest_migration_cli.py` agrega `journal-inspect` y `journal-clear --yes` para diagnostico y limpieza operativa sin mutar `calendar_manifest.json` ni SQLite.
- `manifest_migration_cli.py` queda incluido en release normal y en `updater.DEFAULT_UPDATEABLE_FILES`, pero no en bootstrap.
- La pantalla `Actualizaciones` agrega una tarjeta `Manifest v2` con acciones para revisar y aplicar la migracion desde GUI.
- La accion GUI de aplicar recalcula el preview y exige confirmacion humana antes de llamar a `apply_manifest_preview()`.

## Compatibilidad de actualizacion

- Los usuarios actuales siguen escribiendo manifest v1.
- Leer un manifest v2 no reescribe ni degrada el archivo.
- Telegram conserva su filtro por `publication_target`; las entradas no Telegram no se envian por accidente.
- La sustitucion v2 esta separada de `replace_entries()` para evitar cambiar Logistica actual antes de migrarla.
- Si queda un journal pendiente o un lock activo, las escrituras nuevas se bloquean antes de modificar el archivo principal.
- El preview no modifica `calendar_manifest.json`, por lo que la UI futura podra mostrar cambios antes de confirmar.
- El apply protegido evita aplicar una revision obsoleta sobre cambios externos.
- La migracion formal v1->v2 se ejecuta mediante preview/apply; no degrada ni convierte automaticamente al leer.
- Los snapshots de horario son opt-in en v2 y no cambian la escritura legacy v1.
- Las reglas Trial/carril se aplican solo al contrato v2; la escritura legacy v1 conserva su comportamiento.
- La CLI de migracion no convierte al leer y mantiene preview/apply como pasos separados para updates revisables.
- El flujo GUI muestra el preview antes de aplicar y no toca `calendar_manifest.json` si la revision falla o el usuario cancela.
- La inspeccion/limpieza de journal no modifica el manifest ni la base SQLite; solo elimina `.calendar_manifest_journal.json` cuando el operador confirma y los checks basicos pasan.
- `journal-clear --db-path organizador.db --yes` rechaza la limpieza si SQLite no abre o `PRAGMA integrity_check` falla.

## Pruebas agregadas

- `tests/test_calendar_manifest.py::test_load_entries_accepts_manifest_v2_without_rewriting`
- `tests/test_calendar_manifest.py::test_build_entry_v2_stores_lane_dimensions_and_manual_target`
- `tests/test_calendar_manifest.py::test_replace_entries_v2_replaces_only_target_lane_and_window`
- `tests/test_calendar_manifest.py::test_replace_entries_v2_blocks_when_manifest_lock_exists`
- `tests/test_calendar_manifest.py::test_replace_entries_v2_writes_journal_and_cleans_after_success`
- `tests/test_calendar_manifest.py::test_failed_manifest_write_keeps_journal_and_releases_lock`
- `tests/test_calendar_manifest.py::test_preview_replace_entries_v2_returns_diff_without_writing`
- `tests/test_calendar_manifest.py::test_apply_manifest_preview_rejects_stale_revision`
- `tests/test_calendar_manifest.py::test_preview_migrate_manifest_v1_to_v2_returns_lane_contract_without_writing`
- `tests/test_calendar_manifest.py::test_apply_manifest_preview_migrates_v1_payload_to_v2`
- `tests/test_calendar_manifest.py::test_build_entry_v2_rejects_schedule_snapshot_for_wrong_lane`
- `tests/test_calendar_manifest.py::test_build_entry_v2_requires_trial_lane_for_trial_delivery`
- `tests/test_calendar_manifest.py::test_build_entry_v2_rejects_normal_delivery_in_trial_lane`
- `tests/test_calendar_manifest.py::test_preview_replace_entries_v2_rejects_entries_outside_target_lane`
- `tests/test_calendar_manifest.py::test_inspect_manifest_journal_reports_pending_manifest_and_sqlite`
- `tests/test_calendar_manifest.py::test_clear_manifest_journal_requires_confirmation_and_healthy_state`
- `tests/test_calendar_manifest.py::test_clear_manifest_journal_refuses_when_manifest_is_unreadable`
- `tests/test_manifest_migration_cli.py::test_manifest_migration_cli_preview_prints_json_without_writing`
- `tests/test_manifest_migration_cli.py::test_manifest_migration_cli_apply_converts_manifest_to_v2`
- `tests/test_manifest_migration_cli.py::test_manifest_migration_cli_rejects_apply_without_confirm`
- `tests/test_manifest_migration_cli.py::test_manifest_migration_cli_journal_inspect_reports_pending`
- `tests/test_manifest_migration_cli.py::test_manifest_migration_cli_journal_clear_requires_yes`
- `tests/test_manifest_migration_cli.py::test_manifest_migration_cli_journal_clear_removes_pending_journal`
- `tests/test_release_package_manifest.py::test_release_includes_manifest_migration_cli_but_bootstrap_does_not`
- `tests/test_manifest_migration_gui.py::test_manifest_migration_preview_text_summarizes_safe_review`
- `tests/test_manifest_migration_gui.py::test_updates_frame_exposes_manifest_migration_actions`
- `tests/test_manifest_migration_gui.py::test_manifest_migration_gui_methods_use_preview_before_apply`

## Pendiente R07

- UI para inspeccionar/limpiar journal desde `Actualizaciones` sin abrir consola.
- Reconstruccion automatica avanzada desde journal/SQLite cuando no baste con limpiar evidencia pendiente.
- Conexion del planificador real para poblar `schedule_snapshot` con hora local/zona cuando exista configuracion.
- Fixtures historicos completos bajo carriles contra casos reales de Trial MAX/intercalado.
