# R05 captions versionados

Fecha: 2026-09-13

## Alcance implementado

- Nuevo paquete `captions/` import-safe:
  - `captions/importer.py` centraliza el parser TXT por bloques historicos y parrafos.
  - `captions/service.py` crea pools, items, versiones, bindings individuales y snapshots congelables.
- SQLite agrega tablas no destructivas:
  - `caption_pools`
  - `caption_items`
  - `caption_versions`
  - `caption_bindings`
  - `caption_migration_map`
- `CaptionService.migrate_legacy_captions()` importa:
  - `batch_tandas.captions_file_path` como pool general por tanda.
  - `normal_source_captions` como captions individuales normales.
  - `trial_source_captions` como captions individuales Trial.
- La migracion registra mapeo auditable y es idempotente; no asigna captions por orden a assets sin linaje probado.
- `DatabaseManager.set_normal_source_caption()` y `set_trial_source_caption()` siguen escribiendo sus tablas legacy y ademas crean/actualizan versiones R05 para que las pantallas actuales no mantengan una biblioteca paralela.
- `calendar_manifest.build_entry()` acepta `caption_snapshot` opcional y conserva el texto literal en `caption`.
- `gui_premium_v7.py` agrega `_caption_snapshot_manifest_payload()` y lo usa en nuevas calendarizaciones Trial y Por Cuentas.
- `Organizador.py` agrega `caption_snapshot_manifest_payload()` y lo usa en `distribute_tanda()` para Por Tandas heredado.
- `organizadortg.caption_for_calendar_row()` prefiere `caption_snapshot` + `caption` antes de recalcular desde TXT o tablas mutables.
- `build_release.ps1`, `updater.DEFAULT_UPDATEABLE_FILES` y el inventario R00 incluyen los nuevos modulos.

## Compatibilidad de actualizacion

- Importar `captions` no lee archivos, no abre SQLite y no crea carpetas.
- La migracion legacy no se ejecuta en update ni al importar; requiere llamada explicita.
- Las entradas existentes de `calendar_manifest.json` sin `caption_snapshot` siguen usando el resolver legacy.
- Los envios Telegram con snapshot usan el texto congelado, por lo que editar TXT/Vault despues no altera calendarios previos.

## Pendiente R05

- Hacer que las pantallas muestren IDs/versiones y preview de diferencias antes de guardar.
- Resolver captions durante preview/confirmacion del planificador compartido cuando R08 exista.
- Congelar snapshots en otros productores futuros cuando empiecen a escribir manifest v2/jobs.
- Agregar UI de preview/reconciliacion de migracion TXT.
