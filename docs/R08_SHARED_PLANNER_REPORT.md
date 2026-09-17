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
- Validacion focal: `20 passed` en planner, release e inventario.

## Pendiente R08

- Adaptador de candidatos desde Vault/archivos y cuentas desde catalogo/SQLite.
- Integracion directa con Vault/catalogo real; el checkpoint actual usa el filesystem de `videos_finales/` y el contrato `DatabaseManager.get_all_accounts()` sin mutaciones.
- Integracion del contexto `used_in` en previews por cuenta y resumen GUI de exclusiones.
- Politicas de elegibilidad, usos previos, Trial/carriles y disponibilidad real.
- Conexion del contexto de usos Vault con `preview_schedule_from_sources()` bajo una opcion explicita por cuenta.
- Integracion separada de Por Tandas y Por Cuentas sin cambiar sus algoritmos legacy.
- Integracion del preview por cuenta en la GUI, mostrando `account_summary`, exclusiones y `usage_context_loaded`.
- Preview visible en GUI con diff antes de escribir.
- Reservas de contenido/carril y revision de concurrencia.
- Aplicacion protegida a manifest v2 y pruebas historicas MAX/intercalado.
