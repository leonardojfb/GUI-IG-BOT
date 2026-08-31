# Vault Link Integrity Fix

## Alcance

- `database.py`
- `tests/test_vault_assets.py`
- Este informe

## RED

Comando ejecutado antes de la implementacion:

```powershell
py -m pytest tests/test_vault_assets.py::test_manual_vault_asset_links_are_idempotent_but_keep_distinct_logs tests/test_vault_assets.py::test_existing_database_dedupes_nullable_vault_asset_links_before_unique_index -v
```

Resultado exacto: `2 failed in 0.87s`.

- Dos llamadas manuales con `transform_log_id=None` dejaban cuatro enlaces, en vez de los tres esperados al conservar dos trazas de log distintas.
- Una base existente con dos enlaces iguales y `NULL` conservaba ambas filas al abrirse.

## GREEN

La inicializacion elimina solamente duplicados historicos con `transform_log_id IS NULL` y crea el indice unico por expresion `idx_vault_asset_links_identity`. Los enlaces con IDs de log diferentes permanecen distintos.

Comando ejecutado:

```powershell
py -m pytest tests/test_vault_assets.py -v
```

Resultado exacto: `8 passed in 2.89s`.

Tambien se ejecuto:

```powershell
git diff --check
```

Resultado: sin errores; Git solo informo los avisos existentes de conversion LF a CRLF.
