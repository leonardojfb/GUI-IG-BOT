# Vault and Content CRM Operational Design

## Goal

Extend the existing Vault implementation into the operational source of truth
for content organization, production provenance, account usage, and safe
reuse. The first CRM version records operational facts only. It does not claim
or infer Instagram performance metrics.

## Starting Point

Implementation starts from the `vault-forge-history` branch, not from a new
Vault rewrite. That branch already provides:

- `vault_assets` with a stable SHA-256 identity, original path, media type,
  tags, and timestamps.
- `vault_asset_id` and `variant_signature` links from Forge transform logs.
- Vault import, search, history, and Forge input selection in the GUI.
- Forge pre-render reservation of visual variations to avoid duplicated
  variants for the same source asset.

The current operational flow to preserve is:

```text
inputs -> Tandas/videos.py -> videos_finales -> Organizador.py
-> CALENDARIO_POSTEO/calendar_manifest.json -> organizadortg.py -> Telegram
```

Existing Tandas, Video Editor, Logistics, calendar, and Telegram behavior must
continue to work for legacy folders and inputs. This work adds traceability and
operational decisions; it does not replace delivery behavior.

## Product Model

The primary CRM object is a **content root** (also called a family). A root is
the reusable content idea the operator recognizes, not one exported filename.
It groups originals, photos, overlays, Forge copies, edited videos, Tanda
outputs, and their account uses.

```text
Content root
  -> source assets: video, image, P1, P2, overlay
  -> derivative assets: Forge, edited video, Tanda output
  -> operational uses: account, day, slot, delivery state
```

An asset may be linked to one or more roots only when that is intentional. A
shared source is not copied on disk merely to appear in two roots. Its identity
and production relationships remain singular.

Paths and folders are organization aids, never the durable identity of content.
The database IDs and hashes are the identity. A moved file becomes missing or
relocated; it does not lose history.

## Scope

### Included

- Extend the existing Vault assets into a content library for videos, images,
  overlays, inputs, and generated outputs.
- Logical folders/collections and content roots for organizing material.
- Provenance links across Forge, Video Editor, Tandas, Logistics, Calendar,
  and Telegram.
- An operational CRM view by content root and a complementary view by account.
- Reuse eligibility and conflict warnings based on existing history and planned
  calendar usage.
- Manual operational states: `available`, `in_production`, `generated`,
  `in_tanda`, `scheduled`, `sent_telegram`, `published_confirmed`, `failed`,
  `discarded`, and `archived`.
- Safe migration/backfill where existing logs identify a source unambiguously.

### Explicitly Excluded

- Instagram views, likes, revenue, conversion, or any calculated performance
  ranking.
- Instagram scraping or an external analytics integration.
- Automatic proof that Telegram delivery means publication.
- Physical copying of every asset into a new Vault directory.
- Breaking legacy Tandas or Video Editor workflows by requiring a prior Vault
  import on day one.
- Replacing `calendar_manifest.json` or changing Telegram routing semantics.

## Data Design

Retain `vault_assets` and its existing Forge links. Add these focused records:

### Content roots

`content_roots`

- `id`, stable display `name`, `status`, `notes`, `tags_json`, `created_at`,
  `updated_at`, and nullable `archived_at`.
- `status` is organizational (`active` or `archived`); it is not a performance
  label such as winner or burned.

`content_root_assets`

- `content_root_id`, `vault_asset_id`, `role`, `created_at`.
- Valid roles are `original_video`, `original_image`, `overlay`, `p1`, `p2`,
  `forge_output`, `edited_output`, `tanda_output`, and `reference`.
- Unique pair `(content_root_id, vault_asset_id, role)` prevents accidental
  duplicate membership.

### Provenance

`vault_asset_links`

- `parent_asset_id`, `child_asset_id`, `relation_kind`,
  nullable `transform_log_id`, and `created_at`.
- `relation_kind` is `source`, `overlay`, `p1`, `p2`, or `derived`.
- A transform can have multiple parents: an edited video may have one video and
  many image overlays; a Tanda output has its P1 and P2 parents.

Extend `video_transform_logs` with nullable `output_vault_asset_id`. Every new
successful Forge, Video Editor, or Tandas output is registered as a Vault asset
and linked to its input assets. Forge keeps its existing input
`vault_asset_id`, reservation, and `variant_signature` behavior.

### Operational use

`content_account_uses`

- `id`, `content_root_id`, `vault_asset_id`, `account_id`, `tanda_name`,
  nullable `transform_log_id`, `calendar_entry_key`, `day`, `slot`, `state`,
  `failure_reason`, `created_at`, `updated_at`.
- `calendar_entry_key` is a stable key derived from the manifest entry. It
  makes a re-scan idempotent instead of creating a second use record.
- One manifest entry may project to several roots. The durable uniqueness is
  therefore `(calendar_entry_key, content_root_id)`; an unresolved root uses
  the same key with a null-root sentinel in the repository layer.
- `state` is one of `assigned`, `scheduled`, `sent_telegram`,
  `published_confirmed`, `failed`, or `cancelled`.

The existing manifest remains the scheduling/delivery record. The new table is
the CRM projection of that record, and is rebuilt or reconciled from it when
needed.

## Workflow

### 1. Biblioteca

The first tab opens as a practical library, not a dashboard. It provides:

- An inbox for imported unclassified videos, images, and overlays.
- Collections that act like logical folders without moving source files.
- Root/family creation and assignment of assets with a visible role.
- Search and filters by type, root, collection, status, and missing path.
- An asset detail panel with its roots, immediate parents/children, and uses.

An import records a path and hash using the existing Vault behavior. It does
not copy the file. Importing a known hash returns the known asset and allows the
operator to attach it to another collection or root.

### 2. Production provenance

Forge uses the existing Vault picker and reservation behavior unchanged except
that its completed outputs are also registered as assets and attached to the
chosen roots.

Video Editor and Tandas remain usable with legacy path selection. For every
successful run, the integration resolves a known input asset when possible or
registers the selected input, then registers the output and creates explicit
asset links. If matching an old path is ambiguous, the result remains logged
but is placed in a review queue rather than guessed into a root.

### 3. Logistics and CRM uses

When Logistics creates or updates a calendar manifest entry, it creates or
reconciles a `content_account_use` with state `scheduled`. The entry identifies
the account, source asset/output, root(s), tanda, day, and slot.

When Telegram succeeds, the corresponding use changes to `sent_telegram`.
When it fails, it changes to `failed` with the reported reason. A future manual
action may mark it `published_confirmed`; no code infers that state.

### 4. CRM de contenido

The content-root view is the main operating screen. Each row answers:

- What material and usable outputs does this root contain?
- Which accounts have already used it, and how recently?
- Is it scheduled or being produced now?
- Which accounts can receive it without an active conflict?
- Does it need another variant or is it missing source material?

The account view answers the inverse question: what content is available for
this account, what was recently used, and what is already scheduled. It is a
filter/view over the same operational records, not a duplicate account history.

The Reuse action selects a root and target accounts, filters out current
calendar collisions and policy violations, previews the excluded accounts with
reasons, and sends only eligible selections to the existing Logistics flow.
It never copies outputs or silently overwrites a calendar assignment.

### 5. Technical traceability

Tracing is accessible from an asset/root/use detail drawer. It shows the
compact chain `original -> transform -> output -> Tanda -> account/day/slot ->
Telegram state`, along with technical parameters on demand. It is not the
default CRM table.

## UI Navigation

Keep the existing production and distribution entries. Add or restructure only
the content section:

```text
Contenido
  Biblioteca
  CRM de contenido
  Forge
  Edicion de video
  Tandas
Distribucion
  Logistica
  Cuentas
  Telegram
```

`Biblioteca` is the landing tab when no classified roots exist. `CRM de
contenido` becomes the landing tab once roots and operational uses exist. It
must not present invented totals such as views, published counts, risk scores,
or account performance.

## Conflict and Recovery Rules

- A source path that no longer exists is marked missing and remains visible
  with its historic relationships.
- Hash mismatch is a new identity until the operator explicitly resolves it;
  it cannot silently replace an old asset.
- A calendar entry/root pair already represented by `calendar_entry_key` is
  updated, not inserted again.
- Removing/cancelling a calendar assignment changes the CRM use to `cancelled`;
  it does not erase its audit trail.
- Failed render or Telegram delivery does not mark a root used successfully.
- Reuse checks distinguish `scheduled`, `sent_telegram`, and
  `published_confirmed`; policy enforcement remains based on the existing
  distribution rules plus active calendar entries.

## Delivery Sequence

This is intentionally three independently releasable implementation plans:

1. **Vault library and roots.** Start from `vault-forge-history`; add content
   roots, collection membership, output asset registration interfaces, and the
   Biblioteca UI. Preserve Forge and verify its anti-repetition behavior.
2. **Production and logistics lineage.** Connect Video Editor, Tandas,
   `Organizador.py`, the manifest, and `organizadortg.py` to asset links and
   operational use reconciliation. Preserve all existing render, calendar, and
   Telegram paths.
3. **Operational CRM and reuse.** Add root and account views, conflict logic,
   eligible-account preview, reuse handoff to Logistics, and compact detail
   traceability.

No phase waits for performance metrics. Analytics is a separate future design
whose input contract will be an explicit metrics import or integration.

## Testing and Verification

- Database migration tests cover fresh databases and existing Vault/Forge
  databases without data loss.
- Vault tests confirm deduplicated hash import, root membership, collections,
  and parent-child links.
- Forge tests preserve unique reservation and link generated outputs to the
  selected roots.
- Video Editor and Tandas tests use temporary files and assert every successful
  output has parent relationships without requiring production assets.
- Calendar reconciliation tests prove repeated manifest scans are idempotent,
  cancellation preserves history, and account/day/slot is exact.
- Telegram fake-execution tests assert only the selected manifest entries move
  from `scheduled` to `sent_telegram` or `failed`.
- GUI tests cover empty library, import/classification, CRM content filtering,
  account filtering, and reuse exclusions. Run them at the supported Windows
  DPI/logical resolutions.
- Before release, run the relevant focused test suites, the existing multimedia
  Logistics/Telegram E2E test, Python compile checks, and a manual GUI smoke.

## Release Constraints

Normal releases include code, schema migrations, and tests only. They exclude
`organizador.db`, media, calendars, Telegram sessions/tokens, and local account
history unless an explicit release request authorizes those data files and both
the package manifest and updater allowlists are verified.
