# R06 linaje, firmas y reutilizacion

Fecha: 2026-09-13

## Alcance implementado

- Nuevo modulo import-safe `vault/lineage.py` con `VaultLineage`.
- Nuevo modulo import-safe `vault/reuse.py` con `VaultReuseAudit`.
- Nuevo modulo import-safe `vault/signatures.py` con `VaultSignatures`.
- SQLite agrega tablas no destructivas:
  - `vault_asset_lineage`
  - `vault_asset_usages`
  - `vault_asset_signatures`
- `VaultLineage.record_derivation()` registra relaciones padre -> hijo entre assets existentes.
- Las derivaciones son idempotentes por `(child_asset_id, parent_asset_id, relation_kind)`.
- El servicio rechaza:
  - Assets inexistentes.
  - Linaje de un asset hacia si mismo.
  - Ciclos directos o transitivos.
- `VaultLineage.record_usage()` agrega eventos append-only de uso por asset, tipo y referencia externa.
- `VaultLineage.parents_for_asset()`, `children_for_asset()` y `usages_for_asset()` exponen auditoria para UI/servicios futuros.
- `VaultSignatures.ensure_file_signatures()` guarda firmas tecnicas reproducibles: `sha256`, `size_bytes`, `extension` y `media_type`.
- `VaultSignatures.record_signature()` permite guardar firmas futuras o manuales sin cambiar el schema.
- `VaultSignatures.find_assets_by_signature()` consulta candidatos por firma y puede excluir el asset actual para auditorias de similitud.
- `VaultReuseAudit.candidates_for_asset()` cruza firmas compartidas con usos registrados para reportar posibles reutilizaciones sin tomar decisiones automaticas.
- `VaultQuery.inspect_asset()` ahora incluye `parents`, `children` y `usages` junto al asset, ubicaciones, familias, colecciones, transform logs y thumbnail.
- `VaultQuery.inspect_asset()` tambien incluye `signatures`.
- `VaultQuery.inspect_asset()` tambien incluye `reuse_candidates`.
- `build_release.ps1`, `updater.DEFAULT_UPDATEABLE_FILES` y el inventario R00 incluyen `vault/lineage.py`, `vault/reuse.py` y `vault/signatures.py`.

## Compatibilidad de actualizacion

- Importar `vault.lineage` no abre SQLite, no lee archivos y no crea carpetas.
- Importar `vault.reuse` no abre SQLite, no lee archivos y no crea carpetas.
- Importar `vault.signatures` no abre SQLite, no lee archivos y no crea carpetas.
- La creacion de tablas ocurre solo al instanciar `VaultLineage` o al crear `DatabaseManager()`, siguiendo el patron existente de migraciones SQLite locales.
- No se cambian rutas de archivos, nombres de calendarios, manifest existente ni formato de tandas.
- No se activa reutilizacion automatica; R06 deja solo la base auditable para decidir reutilizacion en fases posteriores.
- Los eventos de uso son append-only para no borrar historial operativo durante updates.
- Las firmas tecnicas se generan solo por llamada explicita y validan que el `sha256` del archivo coincida con el asset antes de persistir.
- La auditoria de reutilizacion es read-only y por defecto solo devuelve candidatos que ya tienen usos registrados.

## Pruebas agregadas

- `tests/test_vault_lineage.py::test_lineage_records_multiple_parents_without_duplicates`
- `tests/test_vault_lineage.py::test_lineage_rejects_self_and_direct_cycles`
- `tests/test_vault_lineage.py::test_usage_events_are_append_only_and_queryable`
- `tests/test_vault_lineage.py::test_vault_inspector_includes_lineage_and_usage`
- `tests/test_vault_signatures.py::test_file_signatures_are_idempotent_and_queryable`
- `tests/test_vault_signatures.py::test_signature_search_can_exclude_current_asset`
- `tests/test_vault_signatures.py::test_vault_inspector_includes_signatures`
- `tests/test_vault_reuse.py::test_reuse_candidates_match_signatures_and_include_usage`
- `tests/test_vault_reuse.py::test_reuse_candidates_can_include_unused_matches`
- `tests/test_vault_reuse.py::test_vault_inspector_includes_reuse_candidates`

## Pendiente R06

- Registrar linaje automaticamente desde productores concretos como Forge, editor, Trials y futuros pipelines.
- Registrar usos al crear entradas reales de calendario/Telegram cuando el planificador compartido R08 exista.
- Agregar firmas perceptuales adicionales para detectar reutilizacion visual aunque cambie el hash exacto.
- Exponer linaje, firmas, usos y candidatos en la UI del Vault con estados claros antes de bloquear o sugerir reutilizacion.
- Definir reglas de reutilizacion por cuenta/categoria cuando haya suficiente evidencia de linaje y uso.
