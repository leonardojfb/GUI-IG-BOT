# Airtable GUI Schema Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the GUI → Airtable mirror serialize local account values according to the live Airtable field types and select options.

**Architecture:** Read the configured table schema before building the mirror plan. A focused serializer will validate and convert each managed field, omit empty values that Airtable cannot accept, and raise a user-safe error before any POST/PATCH/DELETE if a select value is unmappable. Existing callers/tests without a schema keep the current canonical serialization for compatibility.

**Tech Stack:** Python 3, `requests`, dataclasses, `unittest`/pytest, Airtable Metadata API.

## Global Constraints

- Preserve the local SQLite account representation (`0/1`, text, empty strings).
- Never send an empty value to a `singleSelect` field.
- Convert `Trials desbloqueados` to the existing Airtable `Sí`/`No` choice names.
- Reject an unmappable value before any remote mutation.
- Do not change unrelated Airtable read/sync flows or local operational data.

---

### Task 1: Add failing schema-adaptation tests

**Files:**
- Modify: `tests/test_airtable_sync.py`
- Test: `tests/test_airtable_sync.py`

**Interfaces:**
- Consumes: current `build_airtable_mirror_plan()` and `apply_airtable_mirror_plan()`.
- Produces: regression cases proving the current payload sends `False`/empty strings into the live table shape and defining the expected adapted payload.

- [ ] **Step 1: Write the failing test**

Add a table schema fixture with `VA`, `Categoria`, `Trials desbloqueados`, `Dia`, and `Red social` as `singleSelect`, each with explicit choices. Call the planned schema-aware mirror builder with a local row containing `trials_active=0` and empty optional fields. Assert the resulting fields contain `"No"` for the trial select and omit empty select fields.

Add a second test with a local category absent from the schema choices and assert `AirtableSyncError` names the account, field, and invalid value.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_airtable_sync.py -q
```

Expected: the new tests fail because the builder has no schema parameter or still emits `False` and empty strings.

### Task 2: Implement schema-aware serialization

**Files:**
- Modify: `airtable_sync.py`
- Test: `tests/test_airtable_sync.py`

**Interfaces:**
- Consumes: `AirtableConfig`, local managed rows, remote records, and Metadata API table schema.
- Produces: `fetch_airtable_table_schema(config)` and `build_airtable_mirror_plan(local_rows, remote_records, table_schema=None)`.

- [ ] **Step 1: Add a read-only schema loader**

Expose a small `fetch_airtable_table_schema()` wrapper around the existing metadata lookup so the GUI can read the configured table's field definitions without duplicating URL/authentication logic.

- [ ] **Step 2: Add the serializer**

Build a field map from schema metadata. For select fields, extract `options.choices[*].name`; for `Trials desbloqueados`, map false/true to the matching `No`/`Sí` choice case-insensitively. Omit empty select and URL values. Preserve text values. Raise `AirtableSyncError` before returning a plan when a non-empty value is not a known choice.

- [ ] **Step 3: Pass schema through create/update planning**

Add the optional `table_schema` parameter to `build_airtable_mirror_plan()`. Apply serialization to both create fields and update fields. Keep the no-schema path compatible with existing unit tests and other callers.

- [ ] **Step 4: Run focused tests**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_airtable_sync.py -q
```

Expected: all Airtable tests pass, including the new regression cases.

### Task 3: Wire the GUI and verify the complete local path

**Files:**
- Modify: `gui_premium_v7.py`
- Test: `tests/test_airtable_sync.py`

**Interfaces:**
- Consumes: `fetch_airtable_table_schema()` and the schema-aware mirror builder.
- Produces: GUI mirror planning that validates the live Airtable schema before showing confirmation.

- [ ] **Step 1: Write the failing GUI wiring assertion**

Add a source-level test asserting `sync_gui_to_airtable()` loads the table schema and passes it to `build_airtable_mirror_plan()`.

- [ ] **Step 2: Run the wiring test to verify it fails**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_airtable_sync.py -q
```

Expected: the assertion fails because the GUI currently fetches records but not metadata.

- [ ] **Step 3: Wire schema loading before confirmation**

In the worker task, load the config, fetch the table schema, fetch records, and build the adapted plan. Any unmappable value reaches the existing error dialog before the confirmation dialog and before mutation.

- [ ] **Step 4: Run focused tests and compilation**

Run:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; python -m pytest tests/test_airtable_sync.py -q
python -m py_compile airtable_sync.py gui_premium_v7.py
git diff --check
```

Expected: focused tests pass, compilation exits 0, and diff check is clean. Real Airtable mutation remains a separate manual boundary.
