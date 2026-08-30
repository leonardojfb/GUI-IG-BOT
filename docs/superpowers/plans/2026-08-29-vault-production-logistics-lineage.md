# Vault Production and Logistics Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record lineage from Video Editor and Tandas outputs through calendar assignment and Telegram delivery without changing legacy rendering or delivery semantics.

**Architecture:** This plan requires the Vault Library and Content Roots plan. Successful outputs use its shared Vault graph API. A small `vault_usage.py` module turns manifest entries into idempotent operational-use records; `Organizador.py` and `organizadortg.py` call it only after their existing actions succeed.

**Tech Stack:** Python 3, SQLite, JSON calendar manifest, existing FFmpeg and Telegram callers, `pytest`.

## Global Constraints

- Execute on top of the completed Vault Library and Content Roots commits from `vault-forge-history`.
- Preserve manifest version, `delivery_kind`, captions, Trial rules, and selected-account scope.
- Telegram success means `sent_telegram`, never `published_confirmed`.
- Do not infer relationships from filenames when more than one candidate exists.
- Failed renders and sends do not count as successful content use.
- Tests use temporary files and fake Telegram execution only.

---

## File Structure

- `database.py`: operational-use schema and state updates.
- `vault_usage.py`: manifest key, root resolution, reconciliation, and delivery result updates.
- `videos.py`: Tandas parent asset registration after a successful render.
- `gui_premium_v7.py`: Video Editor source/overlay/output registration.
- `Organizador.py`: reconcile entries after `replace_entries`.
- `organizadortg.py`: preserve manifest identity in jobs and persist success/failure.
- `tests/test_vault_usage.py`: reconciliation and state transitions.
- Existing editor, render, manifest, and fake Telegram tests: producer regressions.

### Task 1: Persist idempotent operational uses

**Files:**
- Modify: `database.py:112-158`, `database.py:654-728`
- Create: `vault_usage.py`
- Create: `tests/test_vault_usage.py`

**Interfaces:**
- Produces `calendar_entry_key(entry: dict) -> str`.
- Produces `upsert_content_account_use(record) -> dict`, `list_content_account_uses(account_id=None, root_id=None)`, and `cancel_scoped_content_uses(account_ids, delivery_kind, active_keys) -> int`.
- Produces `reconcile_calendar_entries(db, entries, account_ids, delivery_kind) -> dict`.
- Produces `mark_manifest_delivery(db, entry, state, failure_reason=None) -> dict`.

- [ ] **Step 1: Write the failing reconciliation test**

~~~python
def test_reconcile_manifest_is_idempotent_and_cancels_replaced_slot(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    entry = {
        "id": "a", "account_id": 7, "username": "ana", "delivery_kind": "normal",
        "day": 1, "slot": 1, "tanda": "T1", "source_path": "C:/out/a.mp4",
        "telegram_filename": "a__TANDA_T1.mp4", "transform_log_id": None,
    }

    first = reconcile_calendar_entries(db, [entry], {7}, "normal")
    second = reconcile_calendar_entries(db, [entry], {7}, "normal")
    replacement = {**entry, "id": "b", "source_path": "C:/out/b.mp4",
                   "telegram_filename": "b__TANDA_T1.mp4"}
    reconcile_calendar_entries(db, [replacement], {7}, "normal")

    assert first["created"] == 1
    assert second["created"] == 0
    assert [row["state"] for row in db.list_content_account_uses(account_id=7)] == [
        "cancelled", "scheduled"
    ]
~~~

- [ ] **Step 2: Run the test to verify the usage layer is absent**

Run: `pytest tests/test_vault_usage.py::test_reconcile_manifest_is_idempotent_and_cancels_replaced_slot -v`

Expected: FAIL with `ModuleNotFoundError` for `vault_usage`.

- [ ] **Step 3: Add the table, repository, and reconciliation module**

Add this schema and indexes:

~~~sql
CREATE TABLE IF NOT EXISTS content_account_uses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_entry_key TEXT NOT NULL UNIQUE,
    content_root_id INTEGER,
    vault_asset_id INTEGER,
    account_id INTEGER,
    username TEXT NOT NULL,
    delivery_kind TEXT NOT NULL,
    tanda_name TEXT,
    transform_log_id INTEGER,
    day INTEGER NOT NULL,
    slot INTEGER NOT NULL,
    state TEXT NOT NULL CHECK(state IN (
        'assigned', 'scheduled', 'sent_telegram', 'published_confirmed', 'failed', 'cancelled'
    )),
    failure_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_content_uses_account_state_day
ON content_account_uses(account_id, state, day, slot);
CREATE INDEX IF NOT EXISTS idx_content_uses_root_state
ON content_account_uses(content_root_id, state);
~~~

Use a deterministic key based on scheduling fields, not the per-write manifest UUID:

~~~python
def calendar_entry_key(entry):
    fields = {
        "account_id": entry.get("account_id"),
        "delivery_kind": entry.get("delivery_kind"),
        "day": int(entry.get("day", 0)),
        "slot": int(entry.get("slot", 0)),
        "tanda": entry.get("tanda", ""),
        "source_path": os.path.abspath(entry.get("source_path", "")),
        "telegram_filename": entry.get("telegram_filename", ""),
    }
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
~~~

`reconcile_calendar_entries()` resolves a log's `output_vault_asset_id` and its roots. It upserts each active entry as `scheduled`, including one null-root record when no root is known. It marks only rows from affected account IDs and delivery kind as `cancelled` when their keys are absent. Do not delete any use record.

- [ ] **Step 4: Run usage and manifest tests**

Run: `pytest tests/test_vault_usage.py tests/test_calendar_manifest.py -v`

Expected: PASS; manifest JSON behavior remains unchanged.

- [ ] **Step 5: Commit the use projection**

~~~powershell
git add database.py vault_usage.py tests/test_vault_usage.py
git commit -m "feat(vault): project calendar entries into content uses"
~~~

### Task 2: Link Video Editor and Tandas outputs to real parents

**Files:**
- Modify: `gui_premium_v7.py:4958-5068`
- Modify: `videos.py:114-194`
- Modify: `tests/test_video_editor_transform_logs.py`
- Modify: `tests/test_render_concurrency.py`

**Interfaces:**
- Consumes `register_transform_output()` from the library plan.
- Produces `find_vault_asset_by_path(path) -> dict | None` and `ensure_vault_asset(path) -> dict`.
- Tandas calls `register_transform_output(log_id, out_path, [(p1_id, "p1"), (p2_id, "p2")])` after successful render only.

- [ ] **Step 1: Write failing editor and Tandas lineage tests**

~~~python
def test_editor_log_registers_video_and_overlay_parents(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    video, image, output = [tmp_path / value for value in ("in.mp4", "overlay.png", "out.mp4")]
    video.write_bytes(b"video"); image.write_bytes(b"image"); output.write_bytes(b"output")
    source, overlay = db.ensure_vault_asset(video), db.ensure_vault_asset(image)
    log_id = db.save_video_transform_log(
        "video_editor", video, output, {"overlays": [{"photo_path": str(image)}]}
    )

    result = db.register_transform_output(
        log_id, output, [(source["id"], "source"), (overlay["id"], "overlay")]
    )

    assert {item["relation_kind"] for item in db.list_vault_asset_links(result["id"])} == {
        "source", "overlay"
    }
~~~

Add a `process_tandas()` regression with temporary pre-registered P1/P2 files, a successful mocked `render_video_pair`, and exactly `p1`/ `p2` parent links.

- [ ] **Step 2: Run focused failing tests**

Run: `pytest tests/test_video_editor_transform_logs.py::test_editor_log_registers_video_and_overlay_parents tests/test_render_concurrency.py::test_process_tandas_logs_successful_outputs -v`

Expected: FAIL because neither producer currently registers output assets or parent links.

- [ ] **Step 3: Implement producer integration after success only**

Implement the shared helper:

~~~python
def ensure_vault_asset(self, path):
    existing = self.find_vault_asset_by_path(path)
    return existing if existing else self.upsert_vault_asset(path)
~~~

Each successful Video Editor completion resolves the source and every `overlay["photo"]`, saves its existing transform log, then registers the output. Batch completions repeat per completed job on the GUI completion path, never from background render workers.

In `videos.process_tandas()`, after `fut.result()` returns, resolve/register P1 and P2, save the existing Tandas log, then register output links. Do not create a log or asset link when FFmpeg raises.

- [ ] **Step 4: Run rendering regression tests**

Run: `pytest tests/test_video_editor_transform_logs.py tests/test_video_editor.py tests/test_render_concurrency.py -v`

Expected: PASS; thread-budget and batch behavior remains intact.

- [ ] **Step 5: Commit producer lineage**

~~~powershell
git add database.py gui_premium_v7.py videos.py tests/test_video_editor_transform_logs.py tests/test_render_concurrency.py
git commit -m "feat(vault): trace editor and tanda output lineage"
~~~

### Task 3: Reconcile Logistics and persist Telegram outcomes

**Files:**
- Modify: `Organizador.py:1060-1089`
- Modify: `organizadortg.py:758-853`, `organizadortg.py:1005-1093`
- Modify: `tests/test_calendar_manifest.py`, `tests/test_telegram_single_account_selection.py`

**Interfaces:**
- Consumes `reconcile_calendar_entries(db, entries, account_ids, delivery_kind)`.
- `scan_calendar_structure()` emits `manifest_entry` for manifest-backed videos.
- `execute_telegram_plan(..., delivery_observer=None)` invokes `delivery_observer(manifest_entry, state, failure_reason)` for selected jobs only.

- [ ] **Step 1: Write failing manifest identity and delivery tests**

~~~python
def test_manifest_scan_keeps_entry_for_delivery_state(monkeypatch, tmp_path):
    source = tmp_path / "a.mp4"
    source.write_bytes(b"a")
    entry = build_entry("ana", 7, "normal", 1, 1, "T1", str(source), "a__TANDA_T1.mp4")
    replace_entries(tmp_path / "calendar_manifest.json", [entry], {"ana"}, "normal")
    monkeypatch.setattr(organizadortg, "base_dir", str(tmp_path))

    assert organizadortg.scan_calendar_structure()[0]["manifest_entry"]["id"] == entry["id"]
~~~

Add fake observer tests that select one account, return `(True, 1)` from `_send_video_to_topic`, and observe `sent_telegram`; add a false-result case that observes `failed` with a reason.

- [ ] **Step 2: Run the tests to verify missing propagation**

Run: `pytest tests/test_calendar_manifest.py::test_manifest_scan_keeps_entry_for_delivery_state tests/test_telegram_single_account_selection.py -v`

Expected: FAIL because scan rows and send jobs currently discard manifest identity and outcome.

- [ ] **Step 3: Add reconciliation and scoped observer calls**

Immediately after `replace_entries()` returns in `distribute_tanda()`, call `reconcile_calendar_entries(db, merged_entries, affected_account_ids, "normal")` before `db.close()`. Do not call it when distribution returned early.

Keep the original manifest dictionary as `manifest_entry` in manifest scan rows and carry it into each send job. Add an optional no-op observer:

~~~python
def execute_telegram_plan(start_date, selected_accounts=None, controller=None,
                          reset_topics=False, express_mode=False, delivery_observer=None):
    delivery_observer = delivery_observer or (lambda entry, state, reason=None: None)
~~~

Call it with `sent_telegram` only after `_send_video_to_topic()` returns `ok=True`; call it once with `failed` for a false result or a caught send exception. In `TelegramBotController.start()`, create a short-lived database callback that calls `mark_manifest_delivery` and always closes its database. Never invoke it for a job excluded by `selected_accounts`.

- [ ] **Step 4: Run manifest and fake Telegram suites**

Run: `pytest tests/test_calendar_manifest.py tests/test_telegram_single_account_selection.py tests/test_telegram_trials_routing.py tests/test_telegram_caption_routing.py -v`

Expected: PASS; Trial/normal routing and captions remain unchanged.

- [ ] **Step 5: Commit Logistics and Telegram projection**

~~~powershell
git add Organizador.py organizadortg.py vault_usage.py tests/test_calendar_manifest.py tests/test_telegram_single_account_selection.py
git commit -m "feat(vault): record calendar and telegram content states"
~~~

### Task 4: Backfill only provable historical provenance

**Files:**
- Modify: `vault_usage.py`, `gui_premium_v7.py:_build_vault_frame`
- Modify: `tests/test_vault_usage.py`

**Interfaces:**
- Produces `backfill_vault_provenance(db) -> {"linked": int, "review": list[dict], "skipped": int}`.
- Produces `vault_run_provenance_backfill()` on `InstagramAutoPro`.

- [ ] **Step 1: Write the failing ambiguity test**

~~~python
def test_backfill_never_guesses_when_legacy_source_is_not_resolved(tmp_path):
    db = DatabaseManager(str(tmp_path / "organizador.db"))
    output = tmp_path / "out.mp4"
    output.write_bytes(b"out")
    db.save_video_transform_log("tandas", "C:/legacy/P1.mp4", output, {"p1_id": "P1"})

    result = backfill_vault_provenance(db)

    assert result["linked"] == 0
    assert result["review"][0]["reason"] == "source_not_resolved"
~~~

- [ ] **Step 2: Run the test to verify the backfill is absent**

Run: `pytest tests/test_vault_usage.py::test_backfill_never_guesses_when_legacy_source_is_not_resolved -v`

Expected: FAIL with `ImportError` for `backfill_vault_provenance`.

- [ ] **Step 3: Implement conservative backfill**

Walk logs in ascending ID. Register an existing output path only when it can be read and hashed. Link a source only when `find_vault_asset_by_path()` returns exactly one asset, or details contain a unique exact path for every expected parent. Append unresolved rows to `review` with transform log ID, path, and reason. Do not create roots, infer P1/P2 from filenames, or change prior account history.

The Biblioteca action asks for confirmation, runs in a GUI worker, refreshes on completion, and displays linked/skipped counts plus the first ten review items.

- [ ] **Step 4: Run lineage verification**

Run: `pytest tests/test_vault_usage.py tests/test_vault_assets.py tests/test_video_editor_transform_logs.py tests/test_render_concurrency.py tests/test_calendar_manifest.py tests/test_telegram_single_account_selection.py -v`

Expected: PASS with no live network access.

- [ ] **Step 5: Commit conservative backfill**

~~~powershell
git add vault_usage.py gui_premium_v7.py tests/test_vault_usage.py
git commit -m "feat(vault): backfill provable production provenance"
~~~

### Task 5: Verify end-to-end operational lineage

- [ ] **Step 1: Run the operational suite**

Run: `pytest tests/test_vault_usage.py tests/test_render_concurrency.py tests/test_video_editor_transform_logs.py tests/test_logistica_por_cuentas_e2e.py tests/test_telegram_single_account_selection.py tests/smoke_e2e_pipeline.py -v`

Expected: PASS; no test calls the live Telegram API.

- [ ] **Step 2: Compile runtime modules**

Run: `py -m compileall database.py vault_usage.py videos.py Organizador.py organizadortg.py gui_premium_v7.py -q`

Expected: exit code `0`.

- [ ] **Step 3: Smoke GUI behavior**

Run: `py launcher.py`

Expected: one Editor render and one Tanda render appear in Biblioteca lineage; a calendar assignment is `scheduled`; a fake successful Telegram job becomes `sent_telegram`; no screen calls it published.
