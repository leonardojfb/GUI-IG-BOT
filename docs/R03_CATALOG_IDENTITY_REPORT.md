# R03 - Catalogo estable e identidad social

Fecha: 2026-09-12

Branch: `feature/r00-reproducible-baseline`

## Objetivo

Abrir R03 con una migracion aditiva: cada fila legacy de
`virtual_accounts` conserva su `id`, pero recibe un `identity_id` estable. El
username pasa a ser un alias versionable, no la identidad primaria del historial.

## Contrato implementado

- `virtual_accounts.identity_id` se agrega sin borrar columnas legacy.
- `social_identities` conserva `identity_id`, `legacy_account_id`, plataforma,
  nombre visible y estado archivado.
- `identity_aliases` conserva usernames actuales e historicos con `is_current`.
- `CatalogService.ensure_identity_catalog()` migra cuentas existentes de forma
  idempotente.
- `CatalogService.rename_identity()` cambia el username legacy, conserva el
  mismo `identity_id` y archiva el alias anterior.
- `CatalogService.set_trial_capability()` solo permite activar Trial en
  identidades Instagram. Facebook u otras plataformas fallan antes de mutar.
- `CatalogService.preview_bulk_update()` distingue `UNSET`, `CLEAR` y
  `SET(value)`, devuelve antes/despues por ID y fija `preview_revision`.
- `CatalogService.apply_bulk_update()` aplica solo si la revision actual
  coincide con el preview; si otra ventana cambio una fila, rechaza el lote.
- `AccountSyncPlan.for_local_apply(include_remote_deletes=False)` conserva altas
  y actualizaciones pero omite bajas locales detectadas por ausencia remota.
- `sync_airtable_accounts()` mantiene el preview general y agrega una segunda
  confirmacion especifica para aplicar esas bajas remotas.
- `account_type` permanece como categoria unica operativa; las etiquetas viven
  en `account_tags` + `virtual_account_tags` como relacion N:M aditiva.
- `CatalogService.set_account_category()`, `add_account_tag()`,
  `remove_account_tag()` y `tags_for_account()` exponen esa separacion sin
  tocar distribucion, calendario ni filtros existentes.

## Compatibilidad

Los consumidores actuales pueden seguir usando `DatabaseManager.get_all_accounts()`
y `virtual_accounts.id`. La nueva capa no borra `username`, `account_type`,
`assigned_va`, `trials_active` ni historiales que referencian `account_id`.

Los modulos nuevos `catalog/__init__.py` y `catalog/service.py` se agregan al
allowlist del updater y al `$ReleaseFiles` del builder para evitar un ZIP
incompleto.

## Evidencia

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_catalog_identity.py tests/test_release_package_manifest.py tests/test_updater.py tests/test_update_staging.py tests/smoke_clean_runtime.py -q
```

Resultado: `52 passed, 7 subtests passed in 70.39s`.

Bulk revisable:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_catalog_identity.py -q
```

Resultado: `5 passed in 1.41s`.

Preview Airtable con bajas opt-in:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m py_compile airtable_sync.py gui_premium_v7.py tests\test_airtable_sync.py
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_airtable_sync.py -q
```

Resultado: `25 passed in 1.25s`.

Categoria unica + etiquetas N:M:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
py -3.14 -B -m py_compile database.py catalog\service.py tests\test_catalog_identity.py
py -3.14 -B -m pytest -c NUL --noconftest -p no:cacheprovider tests/test_catalog_identity.py -q
```

Resultado: `7 passed in 3.65s`.

## Pendientes de R03

- Validacion de cambios contra calendarios ya confirmados.
