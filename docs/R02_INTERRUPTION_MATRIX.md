# R02 - Matriz de interrupciones U01-U24

Fecha: 2026-09-12

Branch: `feature/r00-reproducible-baseline`

Esta matriz define los cortes que deben permanecer validados antes de publicar
una release por updater. El criterio base es conservar datos locales, no seguir
con una instalacion ambigua y no bloquear la GUI salvo cuando exista
`RECOVERY_REQUIRED`.

| ID | Punto de interrupcion | Comportamiento esperado | Evidencia actual |
| --- | --- | --- | --- |
| U01 | `manifest_url` ausente | No descarga nada; abre version local. | `tests/test_updater.py::test_u01_missing_manifest_url_does_not_download_or_mutate_installation`. |
| U02 | red no disponible | No muta instalacion; abre version local. | `tests/test_updater.py::test_u02_network_error_does_not_mutate_installation`. |
| U03 | GitHub 401/403/404 | Error accionable sobre token/permisos; abre version local. | `tests/test_updater.py::test_u03_github_auth_errors_are_actionable_and_non_mutating`. |
| U04 | manifiesto no es JSON valido | No descarga paquete; abre version local. | `tests/test_updater.py::test_u04_invalid_manifest_json_does_not_download_or_mutate_installation`. |
| U05 | manifiesto JSON no es objeto | No descarga paquete; abre version local. | `tests/test_updater.py::test_u05_manifest_json_must_be_object_before_package_download`. |
| U06 | version remota invalida | No aplica paquete; conserva version local. | `tests/test_updater.py::test_u06_invalid_remote_version_does_not_download_or_mutate_installation`. |
| U07 | version remota igual o menor | No descarga paquete; reporta que ya esta instalada. | `tests/test_updater.py::test_u07_same_or_older_remote_version_does_not_download_package`. |
| U08 | URL o SHA-256 ausente/invalido | No descarga paquete; abre version local. | `tests/test_updater.py::test_u08_missing_or_invalid_package_url_and_hash_do_not_download`. |
| U09 | SHA-256 del ZIP no coincide | No aplica paquete; conserva version local. | `tests/test_updater.py::test_hash_mismatch_does_not_change_installation`. |
| U10 | `package_kind` invalido | Rechaza antes de escribir. | `tests/test_updater.py::test_u10_invalid_package_kind_is_rejected_before_writes`. |
| U11 | `files` ausente o invalido | Rechaza antes de escribir. | `tests/test_updater.py::test_apply_package_requires_explicit_manifest_files`. |
| U12 | manifiesto pide archivo no permitido | Rechaza antes de escribir datos locales. | `tests/test_updater.py::test_apply_package_rejects_operational_data_even_when_manifest_requests_it`. |
| U13 | `files` no incluye `version.json` | Rechaza antes de escribir. | `tests/test_updater.py::test_u13_manifest_files_must_include_version_json`. |
| U14 | paquete `application` incompleto | Rechaza antes de escribir. | `tests/test_updater.py::test_application_package_cannot_advance_version_with_only_version_file`. |
| U15 | ZIP con path traversal | Rechaza antes de escribir fuera del app dir. | `tests/test_updater.py::test_zip_path_traversal_is_rejected`. |
| U16 | ZIP con symlink | Rechaza antes de extraer. | `tests/test_updater.py::test_u16_zip_symlink_is_rejected_before_extraction`. |
| U17 | ZIP con rutas duplicadas por mayusculas/minusculas | Rechaza colision antes de escribir. | `tests/test_updater.py::test_u17_zip_case_collision_is_rejected_before_writes`. |
| U18 | ZIP contiene archivo no declarado | Rechaza antes de escribir. | `tests/test_updater.py::test_u18_zip_undeclared_file_is_rejected_before_writes`. |
| U19 | ZIP no contiene archivo declarado | Rechaza antes de escribir. | `tests/test_updater.py::test_apply_package_rejects_missing_manifest_file_before_writes`. |
| U20 | version del ZIP distinta al manifiesto | Rechaza y restaura si corresponde. | `tests/test_updater.py::test_u20_packaged_version_must_match_manifest_version`. |
| U21 | falla una copia, rollback verificable | Restaura archivos, limpia journal y conserva version local. | `tests/test_updater.py::test_rollback_restores_files_after_copy_failure`. |
| U22 | falla una copia y rollback no verificable | Marca `RECOVERY_REQUIRED`, conserva backup y bloquea proximos arranques. | `tests/test_updater.py::test_rollback_failure_reports_recovery_required`. |
| U23 | existe `.update_status.json` con recovery | Bloquea antes de red. | `tests/test_updater.py::test_existing_recovery_marker_blocks_update_before_network`. |
| U24 | existe `.update_journal.json` huerfano | Bloquea antes de red como actualizacion interrumpida. | `tests/test_updater.py::test_incomplete_update_journal_blocks_update_before_network`. |

## Cierre de matriz

La matriz queda completa como contrato de R02 y cada corte U01-U24 tiene una
prueba automatizada o una prueba equivalente con nombre explicito.
