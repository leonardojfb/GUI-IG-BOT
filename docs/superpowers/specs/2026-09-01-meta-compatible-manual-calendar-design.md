# Meta-Compatible Manual Calendar Design

## Goal

Extend the legacy GUI calendar so users can prepare Instagram Stories and
Posts, Facebook Page Posts, Facebook Marketplace Listings, and Facebook
Reels manually today. Keep the stored calendar data compatible with a future
Meta API publisher without changing the existing Instagram Reel or Trial
Telegram routes.

## Scope

- Existing normal reels remain `delivery_kind="normal"`.
- Existing Trial reels remain `delivery_kind="trial"` and use
  `publication_target="instagram_trial_reel"`.
- Every manifest entry gains a `publication_target` that identifies the social
  destination independently of `delivery_kind`.
- Stories retain the destination link and announcement text in the calendar
  entry.
- The account screen manages one shared Story link domain and optional
  account-specific full-link overrides.
- This phase only creates, displays, filters, and exports manual publishing
  work. It does not call Meta APIs or send new media automatically.

## Non-Goals

- Do not change the existing Telegram topic, caption, Trial selection, or
  normal Reel distribution behavior.
- Do not repurpose the existing `virtual_accounts.account_link` value, which
  belongs to the current account/Airtable model.
- Do not add Meta credentials, OAuth, token storage, or API calls in this
  phase.
- Do not require Marketplace-specific commercial fields until its publisher is
  implemented. Its future-required data belongs in the extensible payload.

## Data Model

### Account Link Configuration

Create a small local settings table with one row for the normalized shared
Story domain:

```
social_publishing_settings
  key: "story_link_base_url"
  value: "https://link.ejemplo"
```

Add nullable fields to `virtual_accounts`:

```
story_link_override_enabled: INTEGER NOT NULL DEFAULT 0
story_link_override: TEXT NOT NULL DEFAULT ''
```

The resolved Story link is:

1. `story_link_override` when `story_link_override_enabled` is true and its
   value is valid.
2. `<story_link_base_url>/<username>` otherwise.

The base URL is normalized to include a scheme and omit its trailing slash.
The username portion is URL-escaped when the resolved URL is generated.

Applying a base URL changes only the setting. It immediately resolves a link
for every account without duplicating the common domain across account rows.
Turning on the individual-edit checkbox preloads the account's current
resolved URL. Turning it off discards that override from resolution and uses
the shared domain again.

### Calendar Manifest

Keep manifest version 1 and add optional fields so existing entries continue
to load without migration:

```
publication_target: "instagram_reel"
caption: "..."
story_link_url: "https://link.ejemplo/nombre.de.cuenta"
story_announcement_text: "..."
platform_payload: {}
manual_status: "planned"
```

Valid publication targets are:

- `instagram_reel`
- `instagram_trial_reel`
- `instagram_story`
- `instagram_post`
- `facebook_page_post`
- `facebook_marketplace_listing`
- `facebook_reel`

New values default to `instagram_reel` for existing normal flows and
`instagram_trial_reel` for existing Trial flows. `delivery_kind` continues to
distinguish normal and Trial routing only.

`platform_payload` is a JSON object reserved for network-specific properties
that later Meta API adapters will require, such as Marketplace title, price,
condition, or delivery options. Manual calendar creation does not require
unknown future fields.

Each scheduled Story stores the resolved `story_link_url` and announcement
text directly in its manifest entry. This snapshots the intended destination
even when an operator later changes the shared base domain or an account
override.

## User Interface

### Cuentas

Add a compact "Links de historias" section to the existing account screen:

- Input for the shared domain, accepting `link.ejemplo` or a full HTTPS URL.
- `Aplicar a todas` persists the normalized base domain and refreshes the
  resolved link shown for every account.
- Per-account checkbox `Editar enlace individual`.
- A full URL input enabled only while that checkbox is checked.

The default individual URL is the current resolved shared URL. Invalid empty
or malformed individual URLs block save and leave the current saved value
unchanged.

### Logistica

Expose a publication-target selector in the distribution workflow. Existing
Reel and Trial actions preserve their current defaults. The new targets use
the same account, day, slot, media, and preview workflow, but the manifest
records the selected target.

For `instagram_story`, show the resolved Story URL and an editable
announcement-text field before confirmation. Calendarization is rejected if
the URL cannot be resolved or the announcement text is empty.

The manual schedule/preview view must visibly show target, account, date/slot,
caption, and Story link/text when applicable. It must not claim that posting
has occurred.

## Flow

1. Operator saves one shared Story domain in Cuentas.
2. The GUI resolves `<domain>/<username>` for accounts without overrides.
3. Operator optionally enables an account override and saves a full URL.
4. Operator chooses a publication target in Logistica and selects media,
   accounts, days, and slots.
5. For Stories, the GUI preloads the resolved URL and asks for the
   announcement text.
6. Confirmation writes manifest entries with the target, manual status, and
   target-specific snapshot values.
7. Existing Telegram logic continues processing normal Instagram Reels and
   Instagram Trial Reels by `delivery_kind`. It ignores manual-only targets
   until a Meta adapter is introduced.
8. A future adapter reads the same manifest row, validates target-specific
   `platform_payload`, publishes through Meta, and records its result without
   altering the original scheduling data.

## Error Handling

- An empty base domain leaves accounts without individual overrides unresolved;
  a Story cannot be calendarized for them.
- Invalid individual URLs are rejected at save time.
- Invalid or unsupported `publication_target` is rejected before writing the
  manifest.
- Missing media source continues to be filtered by the existing manifest
  loading behavior.
- Existing unsupported target values in manually edited JSON are reported in
  preview rather than sent through Telegram.

## Tests

- Unit tests for URL normalization, default URL resolution, and individual
  override behavior.
- Database migration and persistence tests for the shared domain and account
  overrides.
- Manifest tests proving backward-compatible defaults, target validation, and
  Story metadata snapshot behavior.
- Logistics tests covering an Instagram Story, Instagram Post, Facebook Page
  Post, Marketplace Listing, Facebook Reel, and Instagram Trial Reel entry.
- Regression tests proving normal and Trial Reels preserve their current
  `delivery_kind` behavior and Telegram scans ignore non-Reel targets.
- GUI source tests for the shared-domain control, individual checkbox, target
  selector, and Story announcement field.

## Acceptance Criteria

- Entering `link.ejemplo` and applying it resolves
  `https://link.ejemplo/<username>` for every non-overridden account.
- An individual override is editable only after its checkbox is enabled.
- A scheduled Story records both the exact link and announcement text.
- Users can manually calendarize all seven publication targets.
- Existing normal Reels and Trial Reels retain their current scheduling and
  Telegram behavior.
- No Meta API credentials or external publishing calls are added in this
  phase.
