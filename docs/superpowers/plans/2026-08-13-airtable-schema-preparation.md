# Airtable Schema Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare the agreed account columns in an existing Airtable table from the Legacy GUI connection flow.

**Architecture:** `airtable_sync.py` will own a fixed column schema and a dependency-injected Airtable metadata client. The GUI will invoke it through a worker, save the local connection only after success, and display added or incompatible field names.

**Tech Stack:** Python 3, requests, unittest, CustomTkinter.

## Global Constraints

- Never create a table, alter an existing Airtable field, or write Airtable records.
- Keep credentials out of UI previews, exceptions, commits, and release ZIPs.
- Preserve the one-way Airtable-to-local SQLite synchronization behavior.
- Add only exact missing names from the agreed nine-column schema.

---

### Task 1: Airtable schema preparation client

**Files:**
- Modify: `airtable_sync.py`
- Test: `tests/test_airtable_sync.py`

**Interfaces:**
- Produces: `prepare_airtable_account_table(config, requests_get=requests.get, requests_post=requests.post) -> AirtableSchemaPreparation`.

- [ ] Write failing tests for exact missing-field creation, wrong-type non-modification, and missing-table error.
- [ ] Run `python -m pytest tests/test_airtable_sync.py -q` and verify it fails because preparation is missing.
- [ ] Implement the minimal metadata schema GET, field POST, safe errors, and result object.
- [ ] Run `python -m pytest tests/test_airtable_sync.py -q` and verify it passes.

### Task 2: GUI connect-and-prepare flow

**Files:**
- Modify: `gui_premium_v7.py`
- Test: `tests/test_airtable_sync.py`

**Interfaces:**
- Consumes: `prepare_airtable_account_table(AirtableConfig) -> AirtableSchemaPreparation`.

- [ ] Write failing test proving the configuration flow invokes schema preparation.
- [ ] Run focused test and verify failure.
- [ ] Update the button text and run preparation in the GUI worker before saving configuration.
- [ ] Run focused test and verify success.

### Task 3: Release verification

**Files:**
- Verify: `tests/test_airtable_sync.py`, `tests/test_release_package_manifest.py`, `build_release.ps1`

- [ ] Run `python -m pytest tests/test_airtable_sync.py tests/test_release_package_manifest.py -q`.
- [ ] Run `python -m pytest -q`.
- [ ] On the later v1.0.24 normal release build, inspect that `airtable_sync.py` is included while `airtable_config.json`, databases, tokens, and account history are excluded.
