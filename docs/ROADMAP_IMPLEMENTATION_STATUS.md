# Roadmap implementation status

Fecha: 2026-09-13
Branch auditado: `feature/r00-reproducible-baseline`
Base del plan: `ROADMAP_METODO_IG_LEGACY.md`, `ROADMAP_METODO_IG_LEGACY_FUNCIONES.md`, `ROADMAP_METODO_IG_LEGACY_ACTUALIZACIONES.md`, `ROADMAP_METODO_IG_LEGACY_VALIDACION.md` y prototipo `(3)`.

## Criterio

Este documento mide contra el roadmap documental, no contra la GUI historica.
Una funcion heredada puede existir y aun asi quedar como pendiente si no cumple
el contrato nuevo: datos versionados, migracion recuperable, evidencia, manifest
compatible, trazabilidad y actualizacion segura.

Estados usados:

- `Implementado validado`: el branch tiene codigo, tests y reporte.
- `Parcial validado`: existe una parte nueva validada, pero falta UI, contrato final o integracion.
- `Legacy existente`: la GUI actual ya hace algo parecido, pero falta migrarla al contrato del roadmap.
- `Pendiente`: no implementado en este branch.
- `Pospuesto`: el propio roadmap lo deja fuera del nucleo inmediato o requiere evidencia externa.

## Resumen ejecutivo

| Grupo | Estado |
| --- | --- |
| R00-R02 actualizacion segura | Implementado validado en este branch. |
| R03 catalogo/cuentas | Parcial validado; backend y guards listos, cierre completo depende de flujos UI/evidencia operativa. |
| R04 Vault | Parcial validado; storage, consultas, thumbnails e inspector backend listos, UI operativa completa pendiente. |
| R05 captions | Parcial alto validado; snapshots y migracion conservadora listos, UI de edicion/diff completa pendiente. |
| R06 linaje/firmas/reutilizacion | Parcial validado; backend auditable listo, leases/reservas y UI pendiente. |
| R07-R20 | Contratos backend incrementales implementados; R07, R11-R20 conservan pendientes explícitos de UI, servicios externos y certificación operativa. |

Estimacion conservadora del prototipo final: `20-25%`.
Estimacion por paquetes tocados: `R00-R06 de R00-R20`, pero R04-R06 no estan cerrados al 100%.

## Estado por entrega R00-R20

| Entrega | Estado | Evidencia en branch | Falta para cerrar segun MD |
| --- | --- | --- | --- |
| R00. Reconciliar base real | Implementado validado | `docs/R00_BASELINE_REPORT.md`, `docs/R00_LAUNCH_IMPORT_INVENTORY.md`, smokes `smoke_clean_runtime`, `smoke_ui_visual`, `smoke_e2e_pipeline`. | Publicacion real por canal estable y auditoria de instalaciones de terceros. |
| R01. Puente clientes antiguos | Parcial validado | Commits de bootstrap/updater, `tests/test_update_staging.py`, `tests/test_updater.py`, `docs/R01_UPDATER_COMPAT_REPORT.md`. | Probar salto contra cada cohorte real antigua, no solo fixtures locales. |
| R02. Actualizador recuperable | Implementado validado a nivel local | `docs/R02_INTERRUPTION_MATRIX.md`, tests Uxx de updater, journal, staging, rollback y healthcheck. | Backup/restauracion operativa con UI/preview y ejecucion contra paquetes remotos reales. |
| R03. Cuentas y sincronizacion | Parcial validado | `catalog/service.py`, `airtable_sync.py`, `tests/test_catalog_identity.py`, `docs/R03_CATALOG_IDENTITY_REPORT.md`. | Flujo completo UI de revision, aliases historicos, Trial por red/capacidad y ciclo Airtable operacional. |
| R04. Vault conserva originales | Parcial validado | `vault/storage.py`, `vault/query.py`, `vault/backfill.py`, `vault/migration.py`, `vault/thumbnails.py`, tests Vault y `docs/R04_VAULT_STORAGE_REPORT.md`. | Lista/inspector visibles y operables en GUI, migracion de bytes con progreso real y filtros grandes. |
| R05. Captions versionados | Parcial alto validado | `captions/`, snapshots en manifest, migracion preview/apply, tests caption/Telegram y `docs/R05_CAPTIONS_VERSIONED_REPORT.md`. | UI de diff/versiones antes de guardar y cierre de fallback individual bajo planificador compartido. |
| R06. Linaje, firmas y reutilizacion | Parcial validado | `vault/lineage.py`, `vault/signatures.py`, `vault/reuse.py`, `vault/calendar_usage.py`, tests R06 y `docs/R06_LINEAGE_SIGNATURES_REPORT.md`. | Leases/reservas de firmas, UI visible, politica de reutilizacion y restricciones por destino. |
| R07. Carriles y manifest v2 | Parcial validado | `calendar_manifest.py` lee v1/v2, `build_entry_v2()`, `replace_entries_v2()`, `preview_replace_entries_v2()`, `preview_migrate_manifest_v1_to_v2()`, `apply_manifest_preview()`, `schedule_snapshot`, politica Trial/carril, lock/journal con snapshots base/destino, `inspect_manifest_journal()` con `recovery_available`, `clear_manifest_journal()`, `manifest_migration_cli.py`, comandos `journal-inspect`/`journal-clear`, tarjeta GUI `Manifest v2` con migracion e inspeccion/limpieza de journal, y `docs/R07_MANIFEST_LANES_REPORT.md`. | Aplicacion controlada de snapshots recuperables, conexion del planificador real a horarios exactos y fixtures historicos Trial MAX/intercalado. |
| R08. Planificador compartido | Validado en branch | `shared_planner.py` con elegibilidad Trial/carril y reutilizacion, `preview_shared_schedule()`, `preview_shared_schedule_by_account()`, `shared_planner_sources.py`, `load_planner_accounts()`, `collect_tanda_candidates()`, `load_candidate_usage_rows()`, `preview_schedule_from_sources()`, `preview_schedule_by_account_from_sources()`, `shared_planner_apply.py`, `preview_shared_manifest_apply()`, `planner_reservations.py` con reservas atomicas/TTL/release, seed determinista, preservacion de fuentes/tandas, modos `partial`/`strict`, `gui_premium_v7.py` con tarjeta opt-in de preview/reserva/aplicacion, packaging y tests R08. | La integracion productiva completa con horarios historicos, carriles manuales story/post y publicacion real de plataforma queda fuera de R08 y se valida en R09/R10; la tarjeta exige manifest v2 y mantiene los botones legacy como default. |
| R09. Ejecuciones duraderas | Validado en branch | `durable_jobs.py` con recipes versionadas, jobs/steps/eventos SQLite, dependencias, estados `blocked`, leases con token, checkpoints, retry/backoff, cancelacion y recuperacion; `job_runner.py` con handlers inyectados, ejecucion acotada y `recover_and_run()`; tests R09, packaging e inventario. | R10 debe conectar Tandas, Forge y Edicion como productores reales; R09 no declara ejecucion real FFmpeg ni integracion de plataforma. |
| R10. Productores a jobs | Validado en branch | `producer_jobs.py` genera recipes/steps v1 y `submit_tanda_job()`, `submit_forge_job()`, `submit_editor_job()`; handlers opt-in `make_tanda_handler()`, `make_forge_handler()`, `make_editor_handler()` reutilizan Tandas/Forge/Edicion, validan perfiles, preservan checkpoints/output existente y registran `video_transform_logs`; tests de adapters, runner, packaging e import inventory. | La GUI legacy conserva sus entrypoints por defecto; una siguiente iteracion puede exponer una cola visible para seleccionar estos jobs. FFmpeg real requiere binaries/medios disponibles y se valida en entorno operativo. |
| R11. Photo Forge | Parcial validado | `photo_forge.py` con recipes v1, variantes Pillow atomicas, preview, perfiles, handler R09, logs Vault/linaje; `gui_premium_v7.py` expone selección/preview/generación; packaging y tests. | Firmas perceptuales y reserva anti-repetición entre cuentas en R14/R17; lote real pendiente. |
| R12. Web local | Parcial validado | `local_web.py` implementa API loopback, shell navegable, token Bearer y endpoints de preview/import local con confirmación y raíz acotada; `gui_premium_v7.py` expone apertura opt-in y cierre limpio; packaging y tests. | Integrar más acciones controladas con auditoría; publicación de plataforma y mutaciones de cuentas siguen bloqueadas. |
| R13. ios-remote lectura | Parcial validado | `ios_remote_read.py` sanea snapshots y `ios_remote_adapter.py` normaliza contenedores, cuentas, perfiles allowlisted y hash; Forge permite cargar y visualizar el export; tests y packaging. | Conectar export/servicio real de ios-remote y selección de perfiles sincronizados para resolver destinos, siempre read-only y sin reutilizar cookies. |
| R14. Forge por destinos | Parcial validado | `destination_forge.py` crea previews, reservas atomicas R08 y jobs `forge.destination.v1`; la GUI expone filas manuales, preview y reserva confirmada; reconciliacion exacta, tests y packaging. | Sincronizar snapshots reales ios-remote y confirmar/reconciliar resultados individuales con historial visible. |
| R15. Telegram multiformato | Parcial validado | `telegram_ledger.py` enruta formatos nativos, Bot API sender y ledger idempotente; `organizadortg` escanea y entrega imágenes/documentos mediante `_send_media_to_topic()` y conserva `_send_video_to_topic()` para videos; tests y packaging. | Topic canónico por cuenta, migración de historiales existentes sin reenviar, limpieza UI y smoke externo controlado. |
| R16. Confirmacion persistente | Parcial validado | `confirmation_ledger.py` implementa callbacks v1, inbox SQLite, deduplicación y undo; el webhook los persiste de forma opt-in con `CONFIRMATION_DB_PATH` y evita mutaciones duplicadas; tests y packaging. | Desplegar en Railway, autorizar usuarios con política real y conectar limpieza por IDs/carriles. |
| R17. CRM ampliado | Parcial validado | `crm_insights.py` define identidades tipadas, engagement, viralidad, referencias hash y export CSV saneado; añade snapshots SQLite temporales deduplicados y saneados; tests y packaging. | Conectar fuentes reales con account/org context y exponer serie temporal en UI. |
| R18. Calendario manual/export | Parcial validado | `manual_calendar_export.py` genera y verifica ZIP schema v1 desde entries o manifest v2; añade preview de importación, conflictos y extracción confirmada sin sobrescritura; tests y packaging. | Modificar manifest operativo mediante UI de remapeo, comprobar capacidades reales y auditar importaciones. |
| R19. Meta adapters/crosspost | Parcial validado | `platform_adapters.py` define fases/capabilities, grupos de publicación con resultados independientes y detección de duplicados downstream; rechaza acciones no soportadas y exige resultado explícito; tests y packaging. | Implementar adapters Meta reales sólo tras matriz de permisos, rate limits, account/org context y pruebas externas. |
| R20. Certificacion final | Parcial validado | `release_certification.py` exige gates R11-R19, evidencia estructurada con pruebas pasadas y suite global; última suite: `533 passed, 0 skipped, 7 subtests passed`; declara explícitamente que media de producción/publicación real siguen sin validar. | Ejecutar matriz completa LEG-01..56, cohortes de updater, ciclo piloto y pruebas reales externas antes de certificar producción. |

## Estado por funciones LEG-01 a LEG-56

| LEG | Nombre | Entrega MD | Estado actual | Evidencia / nota |
| --- | --- | --- | --- | --- |
| LEG-01 | Catalogo de cuentas, categorias y VAs | R03 | Parcial validado | `catalog/service.py`, `tests/test_catalog_identity.py`; falta cierre UI/operativo completo. |
| LEG-02 | Edicion masiva de categoria y VA | R03 | Parcial validado | Bulk preview/guard en catalogo; falta flujo UI completo y evidencia de casos reales. |
| LEG-03 | Airtable hacia GUI | R03 | Parcial validado | `airtable_sync.py`; import manual/preview existe, pero falta ciclo operacional completo. |
| LEG-04 | GUI hacia Airtable | R03 | Parcial validado | Mirror/delete opt-in parcialmente cubierto; falta cierre UI y prueba con Airtable real. |
| LEG-05 | Tandas P1 x P2 | R10 | Legacy existente | Motor legacy funciona; falta contrato jobs R10. |
| LEG-06 | Forge generico y por destinos | R10/R14 | Parcial validado | R10 conserva Forge legacy y R14 añade preview/reserva/job por destino; UI y reconciliación con historial aún pendientes. |
| LEG-07 | Efectos y Fuerza independientes | R10 | Legacy existente | Hay pruebas historicas; falta versionarlo en jobs/perfiles. |
| LEG-08 | Custom y rangos | R10 | Legacy existente | Falta contrato nuevo, validacion min/max y snapshots de presets. |
| LEG-09 | Fingerprints y metadata | R06/R10/R11/R14 | Parcial validado | `vault/signatures.py`, `metadata_fingerprints`; faltan firmas perceptuales y jobs. |
| LEG-10 | Editor foto sobre video y preview | R10 | Legacy existente | Falta adaptar a jobs y preview coherente compartido. |
| LEG-11 | Lote cartesiano | R10 | Legacy existente | Falta trazabilidad por receta/job y reservas. |
| LEG-12 | Cache de overlays preparados | R10 | Legacy existente | Falta integrar al contrato de jobs/perfiles. |
| LEG-13 | Rendimiento global | R10 | Legacy existente | `render_performance.py`; falta perfiles versionados CPU/GPU y validacion final. |
| LEG-14 | CPU/GPU y vertical | R10 | Legacy existente | Falta fallback/perfil auditable en jobs. |
| LEG-15 | Limpieza metadata final | R10 | Legacy existente | Falta validacion ffprobe/Pillow integrada al cierre de jobs. |
| LEG-16 | Por Tandas y anticolision | R08 | Legacy existente / parcial | `Organizador.py`; preview puro y lectores reales listos, pero falta adaptar la ejecución y reservas. |
| LEG-17 | Por Cuentas | R08 | Legacy existente / parcial | `gui_premium_v7.py`; preview por cuenta con pools y usos aislados listo, integración UI y aplicación protegida pendientes. |
| LEG-18 | MAX equilibrado normal | R08 | Legacy existente | Falta contrato R08 con reservas y modo estricto/parcial. |
| LEG-19 | Mezclar dos tandas | R08 | Legacy existente | Falta planificador unico y politica versionada. |
| LEG-20 | Biblioteca captions y pools | R05 | Parcial alto validado | `captions/service.py`, `captions/importer.py`; UI final pendiente. |
| LEG-21 | Captions individuales | R05 | Parcial alto validado | Normal/Trial individuales versionados; falta diff UI. |
| LEG-22 | General/Individual por fuente | R05 | Parcial alto validado | Snapshots en manifest y Telegram; fallback final pendiente R08. |
| LEG-23 | Trial como capacidad | R03/R08 | Parcial validado bajo | Trial queda separado en contrato manifest v2 por `instagram_trial_reel` + `lane=trial_reel`; falta elegibilidad final por red/capacidad y planificador R08. |
| LEG-24 | Selector Trial individual | R05/R08/R12 | Legacy existente / parcial | Captions Trial y plan actual existen; selector final compartido pendiente. |
| LEG-25 | Trial MAX e intercalado | R08 | Legacy existente / parcial | Politica v2 separa carril Trial; faltan fixture historico completo, MAX/intercalado y planificador unico R08. |
| LEG-26 | Manifest comun | R07 | Parcial validado | Manifest v1/v2, snapshots, `build_entry_v2()`, `replace_entries_v2()`, preview/apply con revision, migracion v1->v2 por CLI/GUI, lock/journal de escritor con snapshots base/destino e inspeccion/limpieza por API/CLI/GUI; aplicacion de reconstruccion controlada pendiente. |
| LEG-27 | Horarios y zonas | R07 | Parcial validado bajo | `schedule_snapshot` v2 captura dia/slot/carril y puede guardar hora/zona; falta conectarlo al planificador real. |
| LEG-28 | Telegram como metodo | R15 | Parcial validado | Ledger idempotente y worker conectado para video, imagen y documento; faltan topics canónicos y migración de historiales. |
| LEG-29 | Limpieza selectiva | R15/R16 | Parcial validado | Inbox/callbacks versionados y undo one-shot; limpieza por IDs/carriles aún requiere integración UI. |
| LEG-30 | Express y paralelismo | R15 | Parcial validado | Paralelismo legacy y ledger nativo cubiertos por tests; falta recuperación operativa del worker. |
| LEG-31 | Entrega nativa archivos | R15 | Parcial validado | `sendPhoto`, `sendVideo` y `sendDocument` definidos con multipart; worker escanea y conecta foto/documento con tests fake; falta smoke externo real. |
| LEG-32 | Publicado y copiar caption/link | R16 | Parcial validado | Webhook conserva marcado/caption y callbacks versionados quedan persistidos de forma opt-in; publicación real y copia de caption/link siguen pendientes. |
| LEG-33 | Recuperacion y casos limite | R02/R15/R16 | Parcial validado | Updater recuperable validado; recuperacion Telegram/jobs pendiente. |
| LEG-34 | Originales persistentes | R04 | Parcial validado | `vault/storage.py`; UI/migracion operativa completa pendiente. |
| LEG-35 | Firmas sin capacidad teorica | R06 | Parcial validado | `vault/signatures.py`, `vault/reuse.py`; leases y politica pendiente. |
| LEG-36 | Biblioteca, familias y colecciones | R04/R12 | Parcial validado | `vault/query.py` y API local de lectura; UI web/GUI de biblioteca completa pendiente. |
| LEG-37 | Linaje e historial efectivo | R04/R06 | Parcial validado | `vault/lineage.py`, transform lineage, usages; visualizacion pendiente. |
| LEG-38 | CRM y reutilizacion | R06/R16/R17 | Parcial bajo validado | Reuse audit backend; CRM operativo pendiente. |
| LEG-39 | CRM en navegador | R12/R17 | Parcial bajo | API local y export CRM existen; vista CRM navegable y métricas reales pendientes. |
| LEG-40 | Calendario manual Instagram/Facebook | R07/R18/R19 | Parcial bajo | `build_entry_v2()` puede representar destinos manuales; UI, export y adapters pendientes. |
| LEG-41 | Links y anuncio Story | R05/R18 | Parcial bajo | Campos existen en manifest/DB, flujo manual final pendiente. |
| LEG-42 | Control web, roles, licencias y cloud | Backlog / R12+ | Pospuesto | No forma parte del nucleo local inmediato. |
| LEG-43 | CRM ampliado | R17 | Parcial validado | Identidades tipadas, engagement, viralidad y referencias hash; fuentes reales y persistencia histórica pendientes. |
| LEG-44 | Timeline recetas y cola | R09/R14 | Parcial validado | Jobs duraderos R09 y Forge por destino R14 existen; timeline UI y cola visible pendientes. |
| LEG-45 | Social Cards | Backlog | Pospuesto / legacy externo | No integrado en este roadmap branch. |
| LEG-46 | Rediseno GUI/web | R12 | Parcial bajo | Shell web local navegable; la GUI principal y vistas web completas siguen históricas/parciales. |
| LEG-47 | Launcher y panel herramientas | R00-R20 | Parcial validado | Launcher/updater validado; `Actualizaciones` incluye herramienta Manifest v2; panel herramientas completo pendiente. |
| LEG-48 | Actualizaciones, datos y backups | R00-R02 | Parcial alto validado | Updater seguro; backup/restauracion UI pendiente. |
| LEG-49 | Historial jobs, nombres y carpetas | R09 | Parcial bajo | `video_transform_logs`; job history/naming final pendiente. |
| LEG-50 | Subtitulos, barra y conversores | Backlog | Pospuesto | No implementado en este branch. |
| LEG-51 | Preview 9:16 e intro | R10 / backlog | Legacy parcial | Preview legacy existe en partes; contrato R10 pendiente. |
| LEG-52 | E2E y diagnostico | R00-R20 | Parcial validado | Smokes y suite local; matriz final/ciclos piloto pendiente. |
| LEG-53 | Photo Forge | R11 | Parcial validado | Pillow versionado, preview, jobs, logs Vault y tarjeta GUI visible; lote real y firma perceptual pendientes. |
| LEG-54 | Carriles y colisiones | R07/R19 | Parcial validado bajo | `replace_entries_v2()` conserva otros carriles, rechaza batches fuera del carril objetivo y el writer bloquea pisadas concurrentes; politicas de colision avanzadas pendientes. |
| LEG-55 | Multimetodo e identidades Meta | R17-R19 | Pendiente | No adapter Meta ni identidades completas. |
| LEG-56 | Forge por destinos e ios-remote | R13/R14 | Parcial validado | Snapshots iOS saneados, jobs/reservas y UI opt-in con fallback manual; driver real, snapshots sincronizados y confirmacion post-render pendientes. |

## Evidencia de validacion actual

Ultima suite completa observada en este branch:

```text
454 passed, 1 skipped, 7 subtests passed in 162.97s (0:02:42)
```

Smokes controlados de runtime/launcher/UI:

```text
tests\smoke_clean_runtime.py tests\smoke_ui_visual.py tests\smoke_execute_plan.py tests\test_launcher_dependencies.py
7 passed in 31.16s
```

## Siguiente orden recomendado

1. Completar R07 backend: reconstruccion avanzada, horarios exactos y fixtures Trial MAX/intercalado.
2. Cerrar R06 visible: panel de inspeccion Vault/linaje/usos/candidatos en GUI.
3. Completar R08: adaptadores reales, preview GUI, reservas y apply protegido.
4. R09 jobs duraderos, porque R10-R14 dependen de ese contrato.
5. Solo despues, productores nuevos/Photo Forge/web/ios-remote/Telegram ledger.

## Nota de trazabilidad

Los MD fuente `(2)`, `(3)` y `ROADMAP_*` fueron encontrados en el checkout
principal `docs/`, no dentro del worktree aislado. Este archivo queda dentro
del branch para que el avance futuro se mida contra una matriz explicita.
