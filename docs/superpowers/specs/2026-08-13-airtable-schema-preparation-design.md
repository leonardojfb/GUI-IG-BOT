# Airtable Schema Preparation Design

## Objective

Allow each Legacy GUI installation to prepare the required columns in an existing Airtable account table before any account sync.

## Boundaries

- Never create an Airtable table.
- Add only missing columns to the configured existing table.
- Never delete, rename, change type, or write records in Airtable.
- Preserve the one-way Airtable-to-local-GUI synchronization behavior.
- Keep the PAT local to each GUI and out of releases.

## Required columns

| Column | Airtable type |
| --- | --- |
| Username | single line text |
| 2FA | long text |
| VA | single line text |
| Categoría | single line text |
| Trials desbloqueados | checkbox |
| Día | single line text |
| Red social | single line text |
| VPN / Proxy | long text |
| Link | URL |

## User flow

`Conectar y preparar Airtable` asks for the local PAT, Base ID, and table name. It reads the base schema, finds the exact table, and creates only missing required fields. It reports added fields and incompatible existing field types without altering incompatible fields. The local config is saved only after schema preparation succeeds.

## Errors

If the table does not exist, the GUI explains that it must already exist. A missing schema scope or a network error does not save the config and never reveals the token. Retrying is safe because the operation is idempotent.
