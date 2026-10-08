# Telegram account-scoped publication dedupe

## Objective

Treat publication as account-specific. Publishing an origin or exact file for account 1 must suppress that content only for account 1; the same content remains eligible for account 2 until it is marked published there.

## Persistent identity

Use the stable numeric `account_id` already present in `calendar_manifest.json` and encoded as `__ACC<id>` in Telegram filenames. Airtable `Videos publicados` gains:

- `Account ID`: the numeric account identity as text.
- `Publication key`: `<account_id>:<sha256>`, used as the webhook upsert key.

The origin token remains the normalized source-origin token. A published item is identified by either `(account_id, SHA-256)` or `(account_id, Origin token)`.

## Data flow

1. Logistics persists `account_id` in every manifest entry and the Telegram filename.
2. Telegram loads account-scoped published hashes and origins from Airtable.
3. Before creating topics or sending media, Telegram excludes a video only when its own account has the matching hash or origin.
4. The publish webhook extracts `account_id` from the Telegram video filename, stores both new fields, and upserts by `Publication key`.
5. Existing callback payloads remain valid because account identity comes from the filename, not callback data.

## Historical migration

An idempotent migration derives `Account ID` from each existing `Archivo original`, writes `Publication key`, and preserves all other fields. Records whose account cannot be derived remain unchanged and do not participate in account-scoped exclusion, avoiding false suppression on unrelated accounts. The migration produces a report and supports dry-run before apply.

## Failure behavior

- If Airtable cannot be read, Telegram sends nothing.
- If a webhook cannot identify an account, it does not create a global publication record and reports failure through the callback.
- Mixed historical/new rows are supported during deployment; only rows with an account identity are used for exclusion.

## Verification

- Regression test: same origin assigned to accounts 1 and 2, only account 1 published; account 1 is omitted and account 2 is sent.
- Exact SHA exclusion is also account-scoped.
- Webhook tests cover account extraction and composite-key upsert.
- Migration dry-run/apply/second dry-run proves idempotence.
- Deploy Railway, check health/logs, restart the open desktop checkout, and audit prepared batches per account without sending media.

## Rollback

The old Airtable fields remain intact. Rollback consists of deploying the previous webhook/client; the added fields are non-destructive. Airtable export/report and local source backups are retained before migration.
