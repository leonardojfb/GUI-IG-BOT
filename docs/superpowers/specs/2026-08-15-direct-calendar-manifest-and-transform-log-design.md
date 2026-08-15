# Direct Calendar Manifest And Transform Log Design

## Goal

Replace calendar media copies with manifest entries that point to the existing
processed media. Telegram must send those paths directly. Record the effective
transformation applied to every successful output from Tandas, Video Editor,
Forge, and Forge Trials.

## Scope

- Normal and Trial distributions write one shared `calendar_manifest.json`.
- No new distribution path copies media into `CALENDARIO_POSTEO` or
  `CALENDARIO_TRIALS`.
- Telegram preview, account counts, account filtering, sending, and selected
  account cleanup use the manifest when it exists.
- Legacy calendar-folder scanning remains a read-only fallback when no manifest
  exists, so unconverted historical schedules remain sendable.
- Successful Tandas, Video Editor, Forge, and Forge Trial outputs receive a
  durable transformation log row.
- A GUI table exposes the transformation log by output, process, and source.

## Non-Goals

- Do not move, rename, or mutate source media during distribution.
- Do not delete existing legacy calendar copies automatically.
- Do not change caption, topic, account-selection, or delivery scheduling
  rules.
- Do not add a second metadata randomization after Forge. Forge output is the
  exact media Telegram sends.

## Calendar Manifest

`calendar_manifest.json` lives at the application root and is atomically
rewritten after each successful distribution. It contains a versioned object
with an `entries` list. Each entry has:

```json
{
  "id": "uuid",
  "username": "account_name",
  "account_id": 42,
  "delivery_kind": "normal",
  "day": 1,
  "slot": 2,
  "tanda": "PROMO_EVE",
  "source_path": "C:\\...\\videos_finales\\PROMO_EVE\\clip__c01.mp4",
  "telegram_filename": "clip__c01__TANDA_PROMO_EVE__ACC42__D1__S2.mp4",
  "transform_log_id": 183,
  "created_at": "2026-08-15T12:00:00Z"
}
```

`telegram_filename` is logical delivery metadata. It preserves the existing
`__TANDA_` marker used for caption lookup even though the source file is not
renamed or copied.

Normal distribution paths and Trial distribution paths add entries to the same
file. A rerun replaces only the affected account and delivery-kind schedule
records; unrelated schedules remain untouched. Invalid or missing source paths
are skipped with an explicit diagnostic and never sent.

## Telegram And Cleanup Behavior

When the manifest exists, `organizadortg` builds its video rows exclusively
from valid manifest entries. Its existing caption, topic, day, slot, selected
account, and Trial routing code consumes the same row shape as it does today.

When the manifest is absent, Telegram uses its current folder scanners. This is
the only compatibility fallback. It prevents duplicated sends when legacy
folders are still present beside a manifest.

Account video counts and the "Solo con videos" filter use manifest rows. The
selected-account cleanup removes only matching manifest records. Existing
calendar folders remain handled only by the explicit legacy cleanup behavior.

## Transformation Log

The existing local SQLite database gains a `video_transform_logs` table. Each
row is written only after its output file is created successfully:

- output path, source path, output filename, process kind, and UTC timestamp
- operation-specific details encoded as JSON
- optional Forge tanda and source identity

Forge details record actual generated values, not UI ranges: crop in pixels,
mirror, zoom, rotation in degrees, brightness, contrast, saturation, gamma,
noise, speed multiplier, trim start/end in milliseconds, and the applied
iPhone metadata.

Tandas details record the P1 and P2 inputs and render settings. Video Editor
details record every applied photo overlay including photo path, frame/time
range, position, x/y, size, and opacity. Forge Trial uses the same Forge log
format with its tanda and is distinguishable through the process kind and
Trial schedule entry.

The GUI transformation table reads this table and displays one row per output.
Selecting a row shows the full JSON detail payload in a readable form. This
keeps the common table compact while retaining every effective value.

## Implementation Boundaries

- A focused calendar-manifest module owns read, validate, replace, and cleanup
  operations. It has no Telegram or GUI dependency.
- A focused transformation-log helper owns schema migration, inserts, and
  queries through `DatabaseManager`.
- `Organizador.py`, the normal per-account GUI distribution, and Trial
  distribution call the manifest writer instead of copying media.
- `organizadortg.py` consumes manifest entries through an adapter that produces
  the current video-row contract.
- Tandas, Video Editor, and Forge report successful outputs to the shared log
  helper without changing their render behavior.

## Tests

- Normal and Trial distribution create manifest entries that retain account,
  day, slot, tanda, logical filename, and Forge output source path.
- Distribution does not create a calendar media copy and does not call the
  legacy post-copy metadata mutation.
- Manifest-backed Telegram scanning preserves normal and Trial routing,
  captions, selected-account isolation, and account counts.
- Missing media paths are not scheduled for sending.
- Manifest cleanup removes only requested account entries.
- Forge logs exact generated micro-edit values returned by the variant engine.
- Tandas and Video Editor logs contain their effective inputs/overlay values.
- Failed media processing creates no transform-log entry.
