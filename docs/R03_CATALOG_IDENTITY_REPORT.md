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

## Pendientes de R03

- Preview de import Airtable con bajas remotas opt-in.
- Separacion categoria unica vs etiquetas N:M.
- Validacion de cambios contra calendarios ya confirmados.
