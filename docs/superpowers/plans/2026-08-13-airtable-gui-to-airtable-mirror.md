# Airtable GUI-to-Airtable Mirror Implementation Plan

**Goal:** Add an explicit GUI action that mirrors all managed local accounts to Airtable, including creates, updates, and deletions after a confirmation preview.

**Architecture:** Keep the existing Airtable-to-GUI flow unchanged. Add a raw-record fetcher, a deterministic local-to-remote mirror planner, and an Airtable batch mutation executor. The GUI previews the plan and only applies it after confirmation.

**Global constraints:** The mirror controls only the nine managed account columns; malformed Airtable rows abort before mutation; Airtable credentials never enter release packages.

## Tasks

1. Add failing planner and mutation tests in `tests/test_airtable_sync.py`.
2. Implement raw Airtable record fetch, mirror planning, field conversion, and batched create/update/delete requests in `airtable_sync.py`.
3. Add the preview text and separate GUI button/confirmation/apply flow in `gui_premium_v7.py`.
4. Run focused tests, compile checks, and inspect the final diff before release integration.
