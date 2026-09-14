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
| R07-R20 | Mayormente pendiente o legacy existente sin contrato nuevo. |

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
| R07. Carriles y manifest v2 | Parcial validado | `calendar_manifest.py` lee v1/v2, `build_entry_v2()`, `replace_entries_v2()`, `preview_replace_entries_v2()`, `preview_migrate_manifest_v1_to_v2()`, `apply_manifest_preview()`, `schedule_snapshot`, politica Trial/carril, lock/journal, `manifest_migration_cli.py`, tarjeta GUI `Manifest v2` y `docs/R07_MANIFEST_LANES_REPORT.md`. | Reconciliacion asistida journal/SQLite, conexion del planificador real a horarios exactos y fixtures historicos Trial MAX/intercalado. |
| R08. Planificador compartido | Pendiente | Algoritmos legacy Por Tandas/Por Cuentas existen por separado. | Servicio unico, preview inmutable, reservas, modo parcial/estricto y confirmacion por revision. |
| R09. Ejecuciones duraderas | Pendiente | `video_transform_logs` existe, pero no jobs duraderos. | Recetas versionadas, jobs, dependencias, checkpoints, retry y recuperacion tras cierre. |
| R10. Productores a jobs | Pendiente / legacy existente | Tandas, Forge y Edicion existen en Legacy. | Adaptarlos al contrato de jobs sin cambiar composicion historica; validar ffprobe/perfiles. |
| R11. Photo Forge | Pendiente | No hay productor Photo Forge nuevo en este branch. | Operaciones Pillow versionadas, preview compartido, outputs imagen trazables y tests de corrupcion/espacio. |
| R12. Web local | Pendiente | No hay framework web fijado en branch. | API loopback, token local, vistas Contenido/Cuentas/Calendario/Historial y fallback GUI. |
| R13. ios-remote lectura | Pendiente | No se integro adapter ios-remote. | Export saneado/read-only, snapshots, perfiles y prueba sin secretos ni sesiones. |
| R14. Forge por destinos | Pendiente | Forge generico existe; destinos no estan conectados a reservas/perfiles. | Ordenes por cuenta/contenedor/perfil, reconciliacion de reservas y preview. |
| R15. Telegram multiformato | Parcial bajo / legacy existente | Telegram actual envia videos y ahora registra uso `telegram`; tests fake. | Ledger bot/chat/topic/message, media nativa por formato, topic canonico por cuenta y migracion sin reenviar. |
| R16. Confirmacion persistente | Pendiente / legacy parcial | Hay botones/flujo historico, no ledger nuevo. | Callbacks versionados, inbox externo, deduplicacion, undo y limpieza por IDs. |
| R17. CRM ampliado | Pendiente | Catalogo y usos Vault preparan datos base. | Metricas manuales/CSV, reglas de viralidad, historiales dispositivo/red Meta e identidades tipadas. |
| R18. Calendario manual/export | Pendiente | Contrato manual bloqueado en manifest v1. | Capacidades manuales comprobadas, paquete portable, checksums y remapeo. |
| R19. Meta adapters/crosspost | Pendiente / pospuesto por evidencia | No hay adapter Meta habilitado. | Matriz API real, permisos, rate limits, prepare/deliver/schedule/publish/verify. |
| R20. Certificacion final | Pendiente | Hay tests locales acumulados. | Recorrer 56 LEG, saltos por cohorte, ciclos piloto, QA, changelog y paquete inmutable. |

## Estado por funciones LEG-01 a LEG-56

| LEG | Nombre | Entrega MD | Estado actual | Evidencia / nota |
| --- | --- | --- | --- | --- |
| LEG-01 | Catalogo de cuentas, categorias y VAs | R03 | Parcial validado | `catalog/service.py`, `tests/test_catalog_identity.py`; falta cierre UI/operativo completo. |
| LEG-02 | Edicion masiva de categoria y VA | R03 | Parcial validado | Bulk preview/guard en catalogo; falta flujo UI completo y evidencia de casos reales. |
| LEG-03 | Airtable hacia GUI | R03 | Parcial validado | `airtable_sync.py`; import manual/preview existe, pero falta ciclo operacional completo. |
| LEG-04 | GUI hacia Airtable | R03 | Parcial validado | Mirror/delete opt-in parcialmente cubierto; falta cierre UI y prueba con Airtable real. |
| LEG-05 | Tandas P1 x P2 | R10 | Legacy existente | Motor legacy funciona; falta contrato jobs R10. |
| LEG-06 | Forge generico y por destinos | R10/R14 | Legacy existente / pendiente destinos | Forge generico existe; Forge por destinos pendiente. |
| LEG-07 | Efectos y Fuerza independientes | R10 | Legacy existente | Hay pruebas historicas; falta versionarlo en jobs/perfiles. |
| LEG-08 | Custom y rangos | R10 | Legacy existente | Falta contrato nuevo, validacion min/max y snapshots de presets. |
| LEG-09 | Fingerprints y metadata | R06/R10/R11/R14 | Parcial validado | `vault/signatures.py`, `metadata_fingerprints`; faltan firmas perceptuales y jobs. |
| LEG-10 | Editor foto sobre video y preview | R10 | Legacy existente | Falta adaptar a jobs y preview coherente compartido. |
| LEG-11 | Lote cartesiano | R10 | Legacy existente | Falta trazabilidad por receta/job y reservas. |
| LEG-12 | Cache de overlays preparados | R10 | Legacy existente | Falta integrar al contrato de jobs/perfiles. |
| LEG-13 | Rendimiento global | R10 | Legacy existente | `render_performance.py`; falta perfiles versionados CPU/GPU y validacion final. |
| LEG-14 | CPU/GPU y vertical | R10 | Legacy existente | Falta fallback/perfil auditable en jobs. |
| LEG-15 | Limpieza metadata final | R10 | Legacy existente | Falta validacion ffprobe/Pillow integrada al cierre de jobs. |
| LEG-16 | Por Tandas y anticolision | R08 | Legacy existente / parcial | `Organizador.py`; falta planificador unico/reservas. |
| LEG-17 | Por Cuentas | R08 | Legacy existente / parcial | `gui_premium_v7.py`; falta servicio compartido y preview inmutable. |
| LEG-18 | MAX equilibrado normal | R08 | Legacy existente | Falta contrato R08 con reservas y modo estricto/parcial. |
| LEG-19 | Mezclar dos tandas | R08 | Legacy existente | Falta planificador unico y politica versionada. |
| LEG-20 | Biblioteca captions y pools | R05 | Parcial alto validado | `captions/service.py`, `captions/importer.py`; UI final pendiente. |
| LEG-21 | Captions individuales | R05 | Parcial alto validado | Normal/Trial individuales versionados; falta diff UI. |
| LEG-22 | General/Individual por fuente | R05 | Parcial alto validado | Snapshots en manifest y Telegram; fallback final pendiente R08. |
| LEG-23 | Trial como capacidad | R03/R08 | Parcial validado bajo | Trial queda separado en contrato manifest v2 por `instagram_trial_reel` + `lane=trial_reel`; falta elegibilidad final por red/capacidad y planificador R08. |
| LEG-24 | Selector Trial individual | R05/R08/R12 | Legacy existente / parcial | Captions Trial y plan actual existen; selector final compartido pendiente. |
| LEG-25 | Trial MAX e intercalado | R08 | Legacy existente / parcial | Politica v2 separa carril Trial; faltan fixture historico completo, MAX/intercalado y planificador unico R08. |
| LEG-26 | Manifest comun | R07 | Parcial validado | Manifest v1/v2, snapshots, `build_entry_v2()`, `replace_entries_v2()`, preview/apply con revision, migracion v1->v2 por CLI/GUI y lock/journal de escritor; reconciliacion pendiente. |
| LEG-27 | Horarios y zonas | R07 | Parcial validado bajo | `schedule_snapshot` v2 captura dia/slot/carril y puede guardar hora/zona; falta conectarlo al planificador real. |
| LEG-28 | Telegram como metodo | R15 | Legacy existente / parcial | Envio fake validado y uso Vault; ledger/multiformato pendiente. |
| LEG-29 | Limpieza selectiva | R15/R16 | Legacy existente / parcial | Limpieza por cuentas/manifest existe; limpieza por IDs/carriles pendiente. |
| LEG-30 | Express y paralelismo | R15 | Legacy existente / parcial | `tests/test_telegram_express_parallel.py`; falta ledger R15. |
| LEG-31 | Entrega nativa archivos | R15 | Legacy existente / parcial | Video actual; imagen/formato nativo pendiente. |
| LEG-32 | Publicado y copiar caption/link | R16 | Legacy parcial / pendiente | Contrato Story/caption preparado parcialmente; confirmacion persistente pendiente. |
| LEG-33 | Recuperacion y casos limite | R02/R15/R16 | Parcial validado | Updater recuperable validado; recuperacion Telegram/jobs pendiente. |
| LEG-34 | Originales persistentes | R04 | Parcial validado | `vault/storage.py`; UI/migracion operativa completa pendiente. |
| LEG-35 | Firmas sin capacidad teorica | R06 | Parcial validado | `vault/signatures.py`, `vault/reuse.py`; leases y politica pendiente. |
| LEG-36 | Biblioteca, familias y colecciones | R04/R12 | Parcial validado | `vault/query.py`; UI biblioteca completa pendiente. |
| LEG-37 | Linaje e historial efectivo | R04/R06 | Parcial validado | `vault/lineage.py`, transform lineage, usages; visualizacion pendiente. |
| LEG-38 | CRM y reutilizacion | R06/R16/R17 | Parcial bajo validado | Reuse audit backend; CRM operativo pendiente. |
| LEG-39 | CRM en navegador | R12 | Pendiente | Sin web local. |
| LEG-40 | Calendario manual Instagram/Facebook | R07/R18/R19 | Parcial bajo | `build_entry_v2()` puede representar destinos manuales; UI, export y adapters pendientes. |
| LEG-41 | Links y anuncio Story | R05/R18 | Parcial bajo | Campos existen en manifest/DB, flujo manual final pendiente. |
| LEG-42 | Control web, roles, licencias y cloud | Backlog / R12+ | Pospuesto | No forma parte del nucleo local inmediato. |
| LEG-43 | CRM ampliado | R17 | Pendiente | Sin metricas/relaciones ampliadas. |
| LEG-44 | Timeline recetas y cola | R09/R14 | Pendiente | Transform logs no equivalen a jobs duraderos. |
| LEG-45 | Social Cards | Backlog | Pospuesto / legacy externo | No integrado en este roadmap branch. |
| LEG-46 | Rediseno GUI/web | R12 | Pendiente | GUI visible sigue siendo la historica. |
| LEG-47 | Launcher y panel herramientas | R00-R20 | Parcial validado | Launcher/updater validado; `Actualizaciones` incluye herramienta Manifest v2; panel herramientas completo pendiente. |
| LEG-48 | Actualizaciones, datos y backups | R00-R02 | Parcial alto validado | Updater seguro; backup/restauracion UI pendiente. |
| LEG-49 | Historial jobs, nombres y carpetas | R09 | Parcial bajo | `video_transform_logs`; job history/naming final pendiente. |
| LEG-50 | Subtitulos, barra y conversores | Backlog | Pospuesto | No implementado en este branch. |
| LEG-51 | Preview 9:16 e intro | R10 / backlog | Legacy parcial | Preview legacy existe en partes; contrato R10 pendiente. |
| LEG-52 | E2E y diagnostico | R00-R20 | Parcial validado | Smokes y suite local; matriz final/ciclos piloto pendiente. |
| LEG-53 | Photo Forge | R11 | Pendiente | No implementado. |
| LEG-54 | Carriles y colisiones | R07/R19 | Parcial validado bajo | `replace_entries_v2()` conserva otros carriles, rechaza batches fuera del carril objetivo y el writer bloquea pisadas concurrentes; politicas de colision avanzadas pendientes. |
| LEG-55 | Multimetodo e identidades Meta | R17-R19 | Pendiente | No adapter Meta ni identidades completas. |
| LEG-56 | Forge por destinos e ios-remote | R13/R14 | Pendiente | ios-remote read-only y Forge destinos no implementados. |

## Evidencia de validacion actual

Ultima suite completa observada en este branch:

```text
406 passed, 1 skipped, 7 subtests passed in 164.38s
```

Smokes controlados de runtime/launcher/UI:

```text
tests\smoke_clean_runtime.py tests\smoke_ui_visual.py tests\smoke_execute_plan.py tests\test_launcher_dependencies.py
7 passed in 31.16s
```

## Siguiente orden recomendado

1. Cerrar R06 visible: panel de inspeccion Vault/linaje/usos/candidatos en GUI.
2. R07 reader/writer manifest v2 sin activar rutas nuevas.
3. R08 planificador compartido con preview y reservas.
4. R09 jobs duraderos, porque R10-R14 dependen de ese contrato.
5. Solo despues, productores nuevos/Photo Forge/web/ios-remote/Telegram ledger.

## Nota de trazabilidad

Los MD fuente `(2)`, `(3)` y `ROADMAP_*` fueron encontrados en el checkout
principal `docs/`, no dentro del worktree aislado. Este archivo queda dentro
del branch para que el avance futuro se mida contra una matriz explicita.
