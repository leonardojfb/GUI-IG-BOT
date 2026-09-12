# R02 - Matriz de interrupciones U01-U24

Fecha: 2026-09-12

Branch: `feature/r00-reproducible-baseline`

Esta matriz define los cortes que deben permanecer validados antes de publicar
una release por updater. El criterio base es conservar datos locales, no seguir
con una instalacion ambigua y no bloquear la GUI salvo cuando exista
`RECOVERY_REQUIRED`.

| ID | Punto de interrupcion | Comportamiento esperado | Evidencia actual |
| --- | --- | --- | --- |
| U01 | `manifest_url` ausente | No descarga nada; abre version local. | `tests/test_updater.py::test_hash_mismatch_does_not_change_installation` cubre no mutacion; falta test dedicado de mensaje. |
| U02 | red no disponible | No muta instalacion; abre version local. | Cubierto por manejo no fatal de `check_and_apply`; falta test dedicado con `URLError`. |
| U03 | GitHub 401/403/404 | Error accionable sobre token/permisos; abre version local. | Cubierto parcialmente por `_request_bytes`; falta test dedicado. |
| U04 | manifiesto no es JSON valido | No descarga paquete; abre version local. | Falta test dedicado. |
| U05 | manifiesto JSON no es objeto | No descarga paquete; abre version local. | Falta test dedicado. |
| U06 | version remota invalida | No aplica paquete; conserva version local. | Cubierto por `_version_tuple`; falta test dedicado en `check_and_apply`. |
| U07 | version remota igual o menor | No descarga paquete; reporta que ya esta instalada. | Cubierto por `check_and_apply`; falta assert dedicado de no descarga. |
| U08 | URL o SHA-256 ausente/invalido | No descarga paquete; abre version local. | Falta test dedicado. |
| U09 | SHA-256 del ZIP no coincide | No aplica paquete; conserva version local. | `tests/test_updater.py::test_hash_mismatch_does_not_change_installation`. |
| U10 | `package_kind` invalido | Rechaza antes de escribir. | Cubierto por `_validated_package_files`; falta test dedicado. |
| U11 | `files` ausente o invalido | Rechaza antes de escribir. | `tests/test_updater.py::test_apply_package_requires_explicit_manifest_files`. |
| U12 | manifiesto pide archivo no permitido | Rechaza antes de escribir datos locales. | `tests/test_updater.py::test_apply_package_rejects_operational_data_even_when_manifest_requests_it`. |
| U13 | `files` no incluye `version.json` | Rechaza antes de escribir. | Cubierto por `_validated_package_files`; falta test dedicado. |
| U14 | paquete `application` incompleto | Rechaza antes de escribir. | `tests/test_updater.py::test_application_package_cannot_advance_version_with_only_version_file`. |
| U15 | ZIP con path traversal | Rechaza antes de escribir fuera del app dir. | `tests/test_updater.py::test_zip_path_traversal_is_rejected`. |
| U16 | ZIP con symlink | Rechaza antes de extraer. | Cubierto por `_archive_files`; falta test dedicado. |
| U17 | ZIP con rutas duplicadas por mayusculas/minusculas | Rechaza colision antes de escribir. | Cubierto por `_archive_files`; falta test dedicado. |
| U18 | ZIP contiene archivo no declarado | Rechaza antes de escribir. | Cubierto por `apply_package`; falta test dedicado. |
| U19 | ZIP no contiene archivo declarado | Rechaza antes de escribir. | `tests/test_updater.py::test_apply_package_rejects_missing_manifest_file_before_writes`. |
| U20 | version del ZIP distinta al manifiesto | Rechaza y restaura si corresponde. | Cubierto por `apply_package`; falta test dedicado. |
| U21 | falla una copia, rollback verificable | Restaura archivos, limpia journal y conserva version local. | `tests/test_updater.py::test_rollback_restores_files_after_copy_failure`. |
| U22 | falla una copia y rollback no verificable | Marca `RECOVERY_REQUIRED`, conserva backup y bloquea proximos arranques. | `tests/test_updater.py::test_rollback_failure_reports_recovery_required`. |
| U23 | existe `.update_status.json` con recovery | Bloquea antes de red. | `tests/test_updater.py::test_existing_recovery_marker_blocks_update_before_network`. |
| U24 | existe `.update_journal.json` huerfano | Bloquea antes de red como actualizacion interrumpida. | `tests/test_updater.py::test_incomplete_update_journal_blocks_update_before_network`. |

## Cierre de matriz

La matriz queda completa como contrato de R02, pero no todos los cortes tienen
test dedicado todavia. Antes de publicar una release final, los IDs marcados
como "falta test dedicado" deben convertirse en pruebas automatizadas o quedar
justificados por una prueba equivalente con nombre explicito.
