# R08 contrato inicial del planificador compartido

Fecha: 2026-09-16

## Alcance implementado

- `shared_planner.py` define `preview_shared_schedule()` como funcion pura y sin efectos laterales.
- `shared_planner_sources.py` define `load_planner_accounts()` y `collect_tanda_candidates()` como lectores read-only para alimentar el preview con datos concretos.
- `preview_schedule_from_sources()` compone ambos lectores y conserva un reporte de tandas inexistentes, vacias y archivos ignorados.
- `load_candidate_usage_rows()` enriquece candidatos por ruta usando `vault_locations` y `vault_asset_usages`, sin insertar ni actualizar registros.
- Los usos conservan cuenta, carril, tipo y referencia externa; si el carril no esta guardado, se deriva de `publication_target` conocido.
- `preview_shared_schedule_by_account()` mantiene un pool elegible independiente por cuenta, evitando que el uso previo de una cuenta bloquee material valido para otra.
- `preview_schedule_by_account_from_sources()` compone cuentas, tandas, usos opcionales y planner; `include_usage_context` es opt-in durante la transicion.
- El preview recibe cuentas e inventario de candidatos concretos; exige usernames unicos y `source_id` unicos.
- Cada asignacion conserva `source_id`, `source_path`, `tanda` y cualquier metadata del candidato, y agrega cuenta, dia, slot, carril, placement y metodo.
- `MAX` calcula la menor cantidad de dias necesaria para exponer todos los candidatos; los dias fijos respetan `days * accounts * daily_quota`.
- `seed` produce un orden repetible para mezclar una o varias tandas sin perder la identidad de origen.
- `partial` devuelve las asignaciones posibles y un faltante explicito por cuenta, dia, slot y motivo.
- `strict` devuelve `blocked` y no expone asignaciones aplicables cuando el inventario no alcanza.
- La funcion no abre SQLite, no lee/escribe carpetas, no modifica `calendar_manifest.json` y no envia a Telegram/Meta.
- El modulo queda incluido en release normal y updater, pero fuera del paquete bootstrap para preservar el puente de instalaciones antiguas.
- `shared_planner_sources.py` tambien queda incluido en release normal y updater, fuera de bootstrap.

## Compatibilidad de actualizacion

- No se cambia el comportamiento legacy de `Organizador.py` ni de los metodos actuales Por Tandas/Por Cuentas.
- El modulo puede llegar mediante una release normal sin migrar datos ni reordenar calendarios existentes.
- La GUI actual no importa el modulo todavia; por eso esta version no altera el arranque de usuarios existentes.
- Los siguientes consumidores deberan convertir el preview a `build_entry_v2()` solo despues de una confirmacion y una revision de base.

## Pruebas

- `tests/test_shared_planner.py::test_preview_shared_schedule_is_deterministic_and_preserves_sources`
- `tests/test_shared_planner.py::test_preview_shared_schedule_reports_partial_inventory_by_account_and_source`
- `tests/test_shared_planner.py::test_preview_shared_schedule_strict_mode_blocks_partial_plan_without_side_effects`
- `tests/test_shared_planner.py::test_preview_shared_schedule_rejects_invalid_scope`
- `tests/test_release_package_manifest.py::test_release_includes_shared_planner_but_bootstrap_does_not`
- Validacion focal R08/release: `32 passed`; suite completa del branch: `459 passed, 7 subtests passed`.

## Fuera de R08

- Horarios historicos exactos y adaptacion de los productores Tandas/Forge/Edicion al contrato de jobs.
- Carriles manuales `story` y `post` en la tarjeta R08; el contrato de manifest v2 ya los valida, pero requieren su propio formulario y payload.
- Publicacion real en Instagram/Meta o Telegram: R08 solo deja el manifest planificado y sus reservas.
- Ejecuciones duraderas, reintentos y recuperacion despues del cierre de la aplicacion, que corresponden a R09.
## Cierre R08

El branch incluye una tarjeta opt-in en Logistica para `Previsualizar R08`, `Reservar fuentes` y `Aplicar al manifest`. La reserva usa SQLite con TTL y conflicto atomico por fuente, cuenta y carril; la aplicacion convierte assignments a manifest v2 y pasa por `preview_replace_entries_v2()` mas `apply_manifest_preview()`, por lo que no hay escritura sin confirmacion ni revision vigente.

El flujo actual soporta `reel` y `trial_reel`. Los carriles manuales `story` y `post`, horarios historicos exactos y publicacion real en Instagram no se declaran terminados por este checkpoint.
