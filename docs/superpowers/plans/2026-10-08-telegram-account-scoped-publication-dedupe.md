# Telegram Account-Scoped Publication Dedupe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exclude an exact video or origin only for the Instagram account where it was marked published.

**Architecture:** Airtable stores `Account ID` and a composite `Publication key`; the Railway webhook derives the account from the Telegram filename. The desktop sender downloads account-scoped publication pairs and filters each manifest video by its own `account_id`.

**Tech Stack:** Python 3, pytest, Airtable REST/Metadata APIs, Telegram Bot API, Railway CLI.

## Global Constraints

- Preserve all existing Airtable publication records and fields.
- Keep old Telegram callback payloads valid.
- Abort Telegram delivery if Airtable publication state cannot be read.
- Do not send real Telegram media during verification.
- Back up migration inputs and make migration retries idempotent.

---

### Task 1: Account-scoped Airtable reader and Telegram filter

**Files:**
- Modify: `airtable_sync.py`
- Modify: `organizadortg.py`
- Modify: `tests/test_airtable_sync.py`
- Modify: `tests/test_telegram_express_parallel.py`

**Interfaces:**
- Produces: `fetch_published_video_publications(config, requests_get=requests.get) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]`, returning account/hash and account/origin pairs.
- Consumes: manifest video keys `account_id`, `username`, `path`, and `origin_identity`.

- [x] **Step 1: Write failing Airtable and sender regressions**

```python
def test_publications_are_keyed_by_account():
    hashes, origins = fetch_published_video_publications(config, fake_get)
    assert hashes == {("1", "a" * 64)}
    assert origins == {("1", "b" * 16)}

def test_published_origin_is_omitted_only_for_matching_account(...):
    # alpha/account 1 and beta/account 2 share origin-A.
    # Airtable reports only ("1", origin-A-token).
    assert sent_usernames == ["beta"]
```

- [x] **Step 2: Run the focused tests and confirm the global implementation fails**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_airtable_sync.py tests/test_telegram_express_parallel.py -q`

Expected: FAIL because the reader returns global sets and account 2 is incorrectly omitted.

- [x] **Step 3: Implement account-scoped pair loading and filtering**

```python
published_hashes, published_origins = fetch_published_video_publications(config)
account_id = str(video.get("account_id") or "").strip()
if ((account_id, source_hash) in published_hashes
        or (origin_token and (account_id, origin_token) in published_origins)):
    omitted_published += 1
    continue
```

Rows without valid `Account ID` are ignored instead of becoming global exclusions.

- [x] **Step 4: Run the focused tests and confirm they pass**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_airtable_sync.py tests/test_telegram_express_parallel.py -q`

Expected: PASS.

### Task 2: Railway webhook account persistence

**Files:**
- Modify: `railway_telegram_publish_webhook/telegram_publish_webhook.py`
- Modify: `tests/test_telegram_publish_webhook.py`
- Modify: `railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py`

**Interfaces:**
- Produces: `account_id_from_filename(filename: str) -> str | None`.
- Writes Airtable fields `Account ID`, `Publication key`, `SHA-256`, and optional `Origin token`.

- [x] **Step 1: Write failing webhook tests**

```python
assert account_id_from_filename("clip__ACC149__D1__S1.mp4") == "149"
assert captured_fields["Account ID"] == "149"
assert captured_fields["Publication key"] == "149:" + source_hash
```

Also assert missing `__ACC<id>` does not call Airtable and returns a handled failure.

- [x] **Step 2: Run tests and confirm missing account persistence fails**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_telegram_publish_webhook.py railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py -q`

Expected: FAIL because the current upsert is global by `SHA-256`.

- [x] **Step 3: Implement extraction, composite fields, and composite upsert**

```python
def account_id_from_filename(filename):
    match = re.search(r"__ACC(\d+)(?:__|\.|$)", str(filename or ""), re.I)
    return match.group(1) if match else None

fields["Account ID"] = account_id
fields["Publication key"] = f"{account_id}:{source_hash}"
```

Change `performUpsert.fieldsToMergeOn` from `SHA-256` to `Publication key`. If account extraction fails, answer the callback with an error and do not write Airtable.

- [x] **Step 4: Run webhook tests and confirm they pass**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_telegram_publish_webhook.py railway_telegram_publish_webhook/test_telegram_publish_webhook_new_behavior.py -q`

Expected: PASS.

### Task 3: Airtable schema and historical migration

**Files:**
- Create: `migrate_published_accounts.py`
- Create: `tests/test_migrate_published_accounts.py`

**Interfaces:**
- Produces: `account_id_from_filename`, `build_updates(records)`, dry-run report, and idempotent `--apply` migration.
- Consumes: Airtable `Videos publicados` records and `Archivo original`.

- [x] **Step 1: Write failing migration tests**

```python
updates, unresolved = build_updates(records)
assert updates[0]["fields"] == {
    "Account ID": "149",
    "Publication key": "149:" + "a" * 64,
}
assert unresolved == []
```

Cover already-migrated rows and filenames without account IDs.

- [x] **Step 2: Run tests and confirm the migration module is missing**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_migrate_published_accounts.py -q`

Expected: FAIL with import/module error.

- [x] **Step 3: Implement the idempotent migration**

The script fetches all rows, derives account IDs only from persisted account identity or `__ACC<id>` in `Archivo original`, writes only changed fields in batches of ten, records unresolved rows, and writes a JSON report. It never infers historical account ownership from the current manifest. `--apply` is the only mutating mode.

- [x] **Step 4: Create Airtable text fields and run dry-run/apply/verify**

Create `Account ID` and `Publication key` through the Airtable Metadata API. Export the pre-migration records, run dry-run, run `--apply`, then run dry-run again.

Expected: second dry-run reports `planned_updates: 0`; unresolved rows are reported explicitly.

### Task 4: Integration, deployment, restart, and non-sending audit

**Files:**
- Verify all files from Tasks 1-3.

**Interfaces:**
- Consumes the deployed webhook, migrated Airtable rows, local manifest, and open desktop checkout.

- [x] **Step 1: Run the affected suite and compilation gate**

Run: `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_airtable_sync.py tests/test_telegram_express_parallel.py tests/test_telegram_publish_webhook.py tests/test_migrate_published_accounts.py tests/test_calendar_manifest.py tests/test_video_transform_logs.py -q`

Run: `python -m py_compile airtable_sync.py organizadortg.py migrate_published_accounts.py railway_telegram_publish_webhook/telegram_publish_webhook.py`

Expected: all tests and compilation pass.

- [x] **Step 2: Deploy Railway and verify health/logs**

Run: `railway up .\railway_telegram_publish_webhook --path-as-root --service telegram-publish-webhook --environment production --ci`

Expected: deployment succeeds; `/health` returns `{"ok":true}` and service logs show the webhook listening.

- [x] **Step 3: Restart the desktop application**

Stop only the verified `gui_premium_v7.py` process from this checkout, start the same checkout, and verify the new process is alive and responsive.

- [x] **Step 4: Audit the prepared manifest without sending**

Load live account-scoped publication pairs and report prepared/omitted/eligible counts per account. Prove a published origin for account 1 remains eligible for account 2. Do not call Telegram send endpoints.

- [ ] **Step 5: Commit only task-owned code and tests**

Stage explicit paths only; do not include unrelated dirty-worktree files or runtime data.
