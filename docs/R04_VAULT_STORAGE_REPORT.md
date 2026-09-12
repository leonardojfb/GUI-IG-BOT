# R04 Vault storage report

## Alcance validado

- Se incorporo `vault/storage.py` como servicio import-safe para assets
  gestionados y referencias externas.
- `VaultStorage.import_managed()` calcula SHA-256, copia a staging temporal,
  revalida que fuente y copia mantengan el mismo hash, y promociona a
  almacenamiento direccionado por hash.
- Imports repetidos con el mismo contenido reutilizan `vault_assets.sha256` y la
  misma ubicacion gestionada; no duplican bytes.
- `VaultStorage.register_external()` conserva una ubicacion externa sin copiar
  bytes.
- `VaultStorage.verify_location()` distingue `ok`, `missing` y `hash_mismatch`
  sin borrar historial.
- `VaultStorage.relocate_location()` permite apuntar una ubicacion a una nueva
  ruta solo si los bytes coinciden con el SHA-256 del asset.
- `database.py` agrega `vault_assets` y `vault_locations` de forma aditiva.
- `VaultQuery` agrega familias (`content_families`), colecciones
  (`vault_collections`) y relaciones N:M sin mover bytes.
- `VaultQuery.search_assets()` filtra por tipo, salud, familia y coleccion con
  paginacion estable.
- `backfill_transform_log_references()` registra `source_path` y `output_path`
  historicos como ubicaciones externas cuando existen; archivos faltantes quedan
  reportados y no se copian bytes.
- `plan_external_migration()` estima ubicaciones y bytes listos para copiar;
  `migrate_external_locations()` migra solo IDs seleccionados y conserva la
  referencia externa original.
- `video_transform_logs` suma columnas opcionales `source_vault_asset_id` y
  `output_vault_asset_id`; `register_transform_output()` importa el output ya
  renderizado a Vault managed y enlaza el log.
- `build_release.ps1`, `updater.py` y `docs/R00_LAUNCH_IMPORT_INVENTORY.md`
  incluyen los modulos `vault/*` agregados en R04.

## Compatibilidad

- No se copian archivos de usuarios durante la actualizacion. El Vault solo crea
  bytes gestionados cuando un flujo llama explicitamente `import_managed()`.
- Las referencias externas siguen siendo consultables aunque el archivo origen
  desaparezca.
- El layout interno por SHA-256 no reemplaza nombres ni rutas historicas de la
  GUI.

## Evidencia

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m py_compile vault\__init__.py vault\storage.py database.py updater.py tests\test_vault_storage.py
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_vault_storage.py tests/test_release_package_manifest.py tests/test_r00_inventory.py tests/smoke_clean_runtime.py -q
```

Resultado: `15 passed in 27.17s`.

Familias, colecciones y query:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m py_compile vault\query.py vault\storage.py database.py updater.py tests\test_vault_query.py
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_vault_query.py tests/test_vault_storage.py -q
```

Resultado: `5 passed in 2.11s`.

Relocalizacion por hash:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m py_compile vault\storage.py tests\test_vault_storage.py
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_vault_storage.py tests/test_vault_query.py -q
```

Resultado: `6 passed in 2.43s`.

Backfill conservador de referencias:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m py_compile vault\backfill.py vault\storage.py database.py updater.py tests\test_vault_backfill.py
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_vault_backfill.py tests/test_vault_storage.py tests/test_vault_query.py -q
```

Resultado: `8 passed in 3.38s`.

Migracion asistida de bytes:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m py_compile vault\backfill.py vault\migration.py vault\storage.py database.py updater.py tests\test_vault_backfill.py
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_vault_backfill.py tests/test_vault_storage.py tests/test_vault_query.py -q
```

Resultado: `10 passed in 3.95s`.

Outputs de transformaciones enlazados a Vault:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m py_compile vault\integration.py vault\storage.py database.py updater.py tests\test_vault_integration.py
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_vault_integration.py tests/test_vault_storage.py tests/test_vault_query.py tests/test_vault_backfill.py tests/test_video_transform_logs.py -q
```

Resultado: `15 passed in 5.65s`.

## Pendientes de R04

- Conectar llamadas `register_transform_output()` en productores/GUI despues de
  render exitoso.
- Miniaturas e inspector operativo.
