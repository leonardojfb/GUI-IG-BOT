# Vault-backed Forge input history

## Goal

Add a Vault screen and backend history model for the active legacy GUI. The first
implementation scope is Forge only: Forge inputs must come from the Vault, and
Forge must generate only new edit combinations for each input. If the selected
effect/range space is exhausted for an input, Forge skips that input and tells
the user to expand the selected options.

This extends the existing `video_transform_logs` work instead of replacing it.
The Vault stores stable input identity and uses transform logs as the historical
evidence of which edits and outputs already exist.

## Scope

In scope:

- New Vault data model for registered input assets.
- New Vault GUI screen for importing/listing inputs and inspecting their history.
- Forge input picker changed to select Vault assets, not arbitrary loose files.
- Forge variant selection changed from blind random generation to "find an
  unused combination inside the user's selected ranges".
- Forge output logs linked back to the Vault input.
- Clear exhaustion message when no new combination exists for an input.

Out of scope for the first version:

- Making Edicion de video and Tandas require Vault inputs.
- Copying all media into a physical backup folder.
- Reusing prior outputs directly in Logistica or Telegram.
- Changing Telegram delivery or calendar behavior.

## User workflow

1. The operator opens Boveda.
2. They add source videos to the Vault. Each file is hashed and registered once.
3. They open Forge and select inputs from the Vault.
4. They select the normal Forge options: effects, strength/custom ranges, copies,
   tanda name, and Trial/normal mode.
5. Before rendering, Forge asks the Vault history for unused combinations for
   each selected input.
6. For every available combination, Forge renders an output and records the
   transform log.
7. If an input has no remaining combination in the selected range, Forge skips it
   and reports which option space needs to be expanded.

## Data model

Add a `vault_assets` table:

- `id INTEGER PRIMARY KEY AUTOINCREMENT`
- `asset_hash TEXT NOT NULL UNIQUE`
- `source_path TEXT NOT NULL`
- `display_name TEXT NOT NULL`
- `media_type TEXT NOT NULL`
- `tags_json TEXT NOT NULL DEFAULT '[]'`
- `created_at TEXT NOT NULL DEFAULT (datetime('now'))`
- `last_seen_at TEXT`

Extend `video_transform_logs` with nullable columns:

- `vault_asset_id INTEGER`
- `variant_signature TEXT`

The existing `details_json` remains the canonical full record of effective
values. `variant_signature` is a stable hash of only the values that define edit
uniqueness for Forge.

## Variant uniqueness

For Forge, a variant is unique by:

- Vault asset hash.
- Process kind: `forge` or `forge_trial`.
- Enabled effect set.
- Effective parameter values: `crop_px`, `mirror`, `zoom_pct`, `rotate_deg`,
  `brightness`, `contrast`, `saturation`, `gamma`, `noise`, `speed`,
  `trim_start_ms`, `trim_end_ms`.

Metadata iPhone remains unique through the existing `metadata_fingerprints`
system, but it should not be the only reason a variant is considered new. The
goal is to avoid repeating the same visual/edit treatment on the same input.

Normalize floating values before signature generation so tiny representation
noise does not create fake uniqueness:

- `zoom_pct`, `speed`, `brightness`, `contrast`, `saturation`, `gamma`: 4
  decimals.
- `rotate_deg`: 3 decimals.
- integer fields as integers.
- booleans as booleans.

## Combination search

Forge previously called `metadata_pool.generate_variant_params()` randomly inside
`apply_variant_and_metadata()`. The production implementation must split that
flow so Forge reserves a valid candidate before rendering:

- Add a pure helper that generates candidate params from the selected enabled
  effects, strength, and custom ranges.
- Add a helper that computes a stable `variant_signature`.
- Add a Vault/history query that returns signatures already used for a Vault
  asset and process kind.
- Enumerate the finite effective parameter space deterministically.
- Report exact `total`, `used`, and `available` capacity for each Vault input.
- Reserve signatures transactionally in SQLite before FFmpeg so two app
  processes cannot choose the same candidate.
- If the finite space is exhausted, return an exhaustion result for that input.

Custom ranges should behave as the user selected them. The implementation may
not use bounded randomized search as the final behavior. Forge must try the
next enumerated combination until no new combination exists in the selected
space, then tell the user to increase or enable options.

## Forge behavior

Forge preview should show whether each selected Vault input has enough remaining
variant capacity for the requested copies.

When processing:

- Inputs without enough available combinations are skipped before FFmpeg starts.
- Inputs with available combinations render normally.
- Partial success is allowed across multiple inputs.
- The completion message lists generated outputs and skipped inputs.
- Failed renders do not save transform logs or consume signatures.

`apply_variant_and_metadata()` should accept preselected params. If params are
provided, it must use them exactly and return them in the same format as today.

## GUI design

Add a sidebar item under Contenido:

- `Boveda`

The Boveda screen contains:

- Import button for videos.
- Table with display name, hash prefix, path, created date, and output count.
- Filter/search by name, tag, and process.
- Detail panel for the selected asset showing transform history from
  `video_transform_logs`.

Forge changes:

- Replace/add "Agregar videos" with "Seleccionar desde Boveda".
- Keep a small compatibility escape hatch only if needed during migration, but
  normal use should require Vault inputs.
- Show skipped/exhausted inputs clearly before rendering.

## Error handling

- Missing source path: mark the Vault asset as missing and skip it.
- Hash mismatch after re-scan: warn that the path changed and require
  re-import or explicit refresh.
- No available variant: skip and report which input exhausted the selected
  option space.
- DB migration failure: show a Spanish error and avoid rendering.

## Testing

Add focused tests before implementation:

- Registering the same file twice returns the same Vault asset.
- Variant signatures are stable and ignore irrelevant JSON ordering.
- Used signatures are detected from prior `video_transform_logs`.
- Forge candidate reservation never returns the same signature twice in one run.
- Exhaustion returns a clear result instead of rendering a duplicate.
- `apply_variant_and_metadata(..., params=...)` uses the provided params.
- Existing transform log tests still pass.

Recommended focused command:

```powershell
pytest tests/test_vault_assets.py tests/test_forge_variant_reservations.py tests/test_video_transform_logs.py tests/test_forge_concurrency.py -v
```

## Release constraints

This is code/state behavior only. Normal release packaging must still exclude
client-local DBs, Telegram state, calendars, videos, histories, tokens, update
config, and backup folders unless explicitly requested.
