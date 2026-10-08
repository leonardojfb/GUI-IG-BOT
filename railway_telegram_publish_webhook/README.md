# Telegram publication webhook

This Railway service receives the Telegram **Publicado** button callback. It
must persist the source-video SHA-256 in Airtable before it marks the Telegram
message as published. If Airtable is unavailable, the button remains visible
so the operator can retry.

## Airtable setup

Use the existing Airtable base and create a table named `Videos publicados`.
Make `SHA-256` the primary single-line-text field. Add these optional
single-line-text fields for traceability:

- `Archivo original`
- `Chat ID`
- `Message ID`
- `Marcado por`

The desktop application's Airtable PAT needs read access to this table. The
Railway service has a separate PAT with read/write access; never put that
Railway PAT in `airtable_config.json`.

## Railway variables

Set these variables in the deployed Railway service:

- `AIRTABLE_PAT`: Airtable token with access to the publication table.
- `AIRTABLE_BASE_ID`: ID of the existing Airtable base.
- `AIRTABLE_PUBLISHED_TABLE`: optional; defaults to `Videos publicados`.
- Existing Telegram variables remain required: `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_WEBHOOK_BASE_URL`, and `WEBHOOK_SECRET` when configured.

## Release verification

1. Deploy the webhook and confirm `/health` returns `{"ok": true}`.
2. Send one non-production video from the desktop app and press **Publicado**.
3. Confirm exactly one `Videos publicados` row with its SHA-256 and that the
   Telegram caption changes to `✅ YA PUBLICADO`.
4. Start the same Telegram delivery again. It must report the video as omitted
   and must not upload another copy.
