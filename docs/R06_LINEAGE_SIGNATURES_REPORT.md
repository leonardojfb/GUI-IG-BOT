# R06 linaje, firmas y reutilizacion

Fecha: 2026-09-13

## Alcance implementado

- Nuevo modulo import-safe `vault/lineage.py` con `VaultLineage`.
- SQLite agrega tablas no destructivas:
  - `vault_asset_lineage`
  - `vault_asset_usages`
- `VaultLineage.record_derivation()` registra relaciones padre -> hijo entre assets existentes.
- Las derivaciones son idempotentes por `(child_asset_id, parent_asset_id, relation_kind)`.
- El servicio rechaza:
  - Assets inexistentes.
  - Linaje de un asset hacia si mismo.
  - Ciclos directos o transitivos.
- `VaultLineage.record_usage()` agrega eventos append-only de uso por asset, tipo y referencia externa.
- `VaultLineage.parents_for_asset()`, `children_for_asset()` y `usages_for_asset()` exponen auditoria para UI/servicios futuros.
- `VaultQuery.inspect_asset()` ahora incluye `parents`, `children` y `usages` junto al asset, ubicaciones, familias, colecciones, transform logs y thumbnail.
- `build_release.ps1`, `updater.DEFAULT_UPDATEABLE_FILES` y el inventario R00 incluyen `vault/lineage.py`.

## Compatibilidad de actualizacion

- Importar `vault.lineage` no abre SQLite, no lee archivos y no crea carpetas.
- La creacion de tablas ocurre solo al instanciar `VaultLineage` o al crear `DatabaseManager()`, siguiendo el patron existente de migraciones SQLite locales.
- No se cambian rutas de archivos, nombres de calendarios, manifest existente ni formato de tandas.
- No se activa reutilizacion automatica; R06 deja solo la base auditable para decidir reutilizacion en fases posteriores.
- Los eventos de uso son append-only para no borrar historial operativo durante updates.

## Pruebas agregadas

- `tests/test_vault_lineage.py::test_lineage_records_multiple_parents_without_duplicates`
- `tests/test_vault_lineage.py::test_lineage_rejects_self_and_direct_cycles`
- `tests/test_vault_lineage.py::test_usage_events_are_append_only_and_queryable`
- `tests/test_vault_lineage.py::test_vault_inspector_includes_lineage_and_usage`

## Pendiente R06

- Registrar linaje automaticamente desde productores concretos como Forge, editor, Trials y futuros pipelines.
- Registrar usos al crear entradas reales de calendario/Telegram cuando el planificador compartido R08 exista.
- Agregar firmas perceptuales o tecnicas adicionales para detectar reutilizacion visual aunque cambie el hash exacto.
- Exponer linaje y uso en la UI del Vault con estados claros antes de bloquear o sugerir reutilizacion.
- Definir reglas de reutilizacion por cuenta/categoria cuando haya suficiente evidencia de linaje y uso.
