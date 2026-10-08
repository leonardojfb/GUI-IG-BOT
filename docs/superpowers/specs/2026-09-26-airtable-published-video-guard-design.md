# Airtable guard for globally published videos

## Goal

Prevent a video that was explicitly marked **Publicado** in Telegram from being
sent again to any account, even when the same tanda is distributed again. A
render whose bytes or metadata change remains eligible as a new video.

## Scope and source of truth

Airtable is the sole persistent source of truth for this decision. The existing
account-sync table remains dedicated to accounts. A new table, `Videos
publicados`, holds one record per published content hash. No new JSON state or
SQLite table is introduced for this feature.

The table has these fields:

| Field | Purpose |
| --- | --- |
| `SHA-256` | Unique identity of the exact video bytes; primary deduplication key. |
| `Tanda` | Source tanda at the time it was marked published. |
| `Archivo original` | Filename shown for operations and audit. |
| `Cuenta que publicó` | Account associated with the Telegram delivery. |
| `Publicado el` | Airtable creation timestamp or explicit UTC timestamp. |
| `Chat ID` | Telegram chat where the action occurred. |
| `Message ID` | Telegram video message that was marked. |

## Delivery flow

1. The desktop sender calculates a SHA-256 for every planned source video
   before delivery and includes its URL-safe base64 form in the Telegram
   callback payload. This compact representation fits Telegram's callback
   limit and identifies the original source even if the delivery path needed
   temporary compression.
2. The Railway Telegram webhook receives the `Publicado` callback and upserts
   the corresponding hash in Airtable. Repeated callbacks are idempotent: they
   keep one record for the hash.
3. Only after Airtable confirms the upsert does the webhook change the Telegram
   caption to `YA PUBLICADO` and remove the publish action.
4. Before a later delivery starts, the desktop sender fetches the published
   hashes from Airtable, hashes each candidate, and excludes every matching
   candidate for every account.
5. The completion report states both sent and globally omitted counts, with
   enough filenames for the operator to identify skipped content.

## Failure policy

This is a safety control, so Airtable read or write failure is fail-closed.
The sender must not deliver a video when it cannot read the authoritative
published-hash set. The webhook must leave the Telegram message unmarked if it
cannot persist the publication. Errors must be concise and must not expose
tokens or Airtable response bodies.

## Compatibility and security

Existing Telegram messages with the legacy `pub` callback retain their current
visual-only behavior. New messages use a strictly validated `pub:<hash>`
callback emitted by the bot; Telegram supplies callback queries only for the
button embedded in its message. Airtable credentials remain server-side:
Railway owns write credentials, and the desktop application reads using its
existing locally configured Airtable credentials.

## Tests and verification

- Marking a video published creates exactly one Airtable record and updates the
  Telegram message only after success.
- A published hash is omitted for the original account and every other account.
- A renamed byte-identical file is still omitted.
- A byte- or metadata-altered render has a different hash and is deliverable.
- Duplicate callbacks and parallel send preparation do not create duplicate
  Airtable rows or send a known published hash.
- Airtable read failure blocks delivery; Airtable write failure leaves the
  message eligible and visibly unmarked.

Local tests will mock Airtable and Telegram boundaries. A release also needs a
Railway deployment check and one real test message/callback to prove the
desktop-to-Telegram-to-Airtable round trip.
