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
- `database.py` agrega `vault_assets` y `vault_locations` de forma aditiva.
- `build_release.ps1`, `updater.py` y `docs/R00_LAUNCH_IMPORT_INVENTORY.md`
  incluyen `vault/__init__.py` y `vault/storage.py`.

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

## Pendientes de R04

- Familias, colecciones y query paginado.
- Import gestionado conectado a productores/GUI.
- Migracion asistida de bytes historicos con estimacion de espacio y progreso.
- Relocalizacion de ubicaciones externas.
- Miniaturas e inspector operativo.
