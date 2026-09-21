# Configuracion manual de modulos y perfiles opcionales Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the modular workflow editor so Forge, Logistica and Telegram are configured from complete manual forms, while user-created profiles remain optional and never become automatic defaults.

**Architecture:** Keep the existing immutable queue recipes and output contracts. Add a small SQLite-backed profile repository keyed by module and subtype, a server-side manual-step validation/composition boundary, and a vanilla-JS editor whose state is an explicit list of typed steps rather than hard-coded production blocks. Keep the existing composed-workflow and legacy calendar APIs for compatibility, but stop using built-in presets as the source of state for the new editor.

**Tech Stack:** Python 3, SQLite, existing `workflow_store.py`/`workflow_queue.py`, `LocalWebService`, vanilla JavaScript in `web/app.js`, pytest.

## Global Constraints

- New workflow steps start with no business values and no selected profile.
- A profile is loaded only after an explicit user action and loading it never adds a queue job.
- Profile scope is `(module_type, subtype)`; incompatible profiles are not selectable.
- Existing queue snapshots and existing composed workflows remain readable.
- Use the real desktop Forge, Logistica and Telegram field names and recipe builders; do not invent generic “profile” payloads.
- Keep `queue_only` as the safe default for Telegram execution.
- Every production change follows red-green-refactor: write and run a failing test before implementation.

---

### Task 1: Define manual step contracts and validation

**Files:**
- Modify: `workflow_step_recipes.py`
- Create: `workflow_manual_steps.py`
- Test: `tests/test_workflow_manual_steps.py`

**Interfaces:**
- `workflow_manual_steps.MODULE_TYPES = ("forge", "logistica", "telegram")`.
- `workflow_manual_steps.SUBTYPES` maps Forge to `("normal", "trials")`, Logistica to `("por_tandas", "por_cuentas")`, and Telegram to `("send",)`.
- `validate_manual_step(step: dict) -> dict` returns a normalized step with `module_type`, `subtype`, `recipe`, `input_contract`, and `output_contract`, or raises `ValueError` with a field-specific message.
- `build_manual_step(module_type: str, subtype: str, fields: dict) -> dict` delegates to the existing Forge/Logistica/Telegram recipe builders and returns the normalized step.

- [ ] **Step 1: Write the failing tests**

Add tests that assert:

```python
def test_manual_forge_requires_explicit_subtype_and_preserves_all_form_fields():
    step = build_manual_step("forge", "trials", {
        "video_paths": ["real.mp4"], "tanda_name": "SPAM", "copies": 2,
        "days": "7", "trial_mode": "Trials", "effects": "Custom",
        "strength": "Custom", "fx_enabled": {"mirror": False},
        "forge_strength": 0.7, "overrides": {"zoom": [1.0, 1.04]},
        "metadata_assignments": [{"source": "form"}],
    })
    assert step["subtype"] == "trials"
    assert step["recipe"]["trial_mode"] == "Trials"
    assert step["recipe"]["overrides"]["zoom"] == [1.0, 1.04]


def test_manual_logistica_has_distinct_por_tandas_and_por_cuentas_contracts():
    step = build_manual_step("logistica", "por_cuentas", {
        "tanda_name": "SPAM", "tanda_name_2": "", "category_dest": "",
        "daily_quota": 3, "days": "MAX", "fillup": False,
        "account_names": ["cuenta-real"], "caption_modes": {"SPAM": "general"},
    })
    assert step["input_contract"] == "TandaOutput"
    assert step["recipe"]["mode"] == "por_cuentas"


def test_manual_step_rejects_unknown_module_or_subtype():
    with pytest.raises(ValueError, match="subtipo"):
        build_manual_step("forge", "inventado", {})
```

- [ ] **Step 2: Run the focused tests and verify the expected red failure**

Run:

```powershell
py -m pytest tests/test_workflow_manual_steps.py -q
```

Expected: FAIL because `workflow_manual_steps.py` and the explicit subtype boundary do not exist yet.

- [ ] **Step 3: Implement the smallest contract layer**

Add the explicit module/subtype maps and delegate field normalization to `build_forge_workflow_recipe`, `build_logistica_workflow_recipe`, and `build_telegram_workflow_recipe`. Add `forge_subtype` only as normalized metadata; preserve the existing `trial_mode` recipe field so historical Forge recipes remain compatible.

- [ ] **Step 4: Run the focused tests and the existing recipe tests**

Run:

```powershell
py -m pytest tests/test_workflow_manual_steps.py tests/test_workflow_step_recipes.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the contract layer**

```powershell
git add workflow_manual_steps.py workflow_step_recipes.py tests/test_workflow_manual_steps.py
git commit -m "feat(workflows): define explicit manual module steps"
```

### Task 2: Add optional profile persistence

**Files:**
- Create: `workflow_profiles.py`
- Modify: `workflow_store.py` only if schema initialization needs to be shared
- Test: `tests/test_workflow_profiles.py`

**Interfaces:**
- `ensure_profile_schema(connection) -> None` creates `workflow_profiles` with `profile_id`, `module_type`, `subtype`, `name`, `recipe_json`, `created_at`, `updated_at` and a unique `(module_type, subtype, name)` constraint.
- `list_profiles(connection, module_type=None, subtype=None) -> list[dict]` returns only compatible profiles when filters are supplied.
- `save_profile(connection, module_type, subtype, name, recipe) -> dict` inserts or versions a user profile without changing queue rows.
- `get_profile(connection, profile_id) -> dict` returns a decoded recipe.
- `delete_profile(connection, profile_id) -> dict` deletes only the selected profile.

- [ ] **Step 1: Write failing persistence tests**

Cover empty storage, save/list/load, duplicate names within one module/subtype, same name allowed across subtypes, and deletion. Assert that a saved profile never inserts into `workflow_job_queue_steps`.

- [ ] **Step 2: Run `py -m pytest tests/test_workflow_profiles.py -q` and verify red**

Expected: FAIL because the profile repository does not exist.

- [ ] **Step 3: Implement the SQLite repository**

Use JSON with sorted keys for deterministic storage. Reject empty names, unknown module/subtype pairs, and non-object recipes. Return copies decoded from JSON so callers cannot mutate stored state.

- [ ] **Step 4: Run profile tests plus workflow-store tests**

```powershell
py -m pytest tests/test_workflow_profiles.py tests/test_workflow_store.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit the repository**

```powershell
git add workflow_profiles.py tests/test_workflow_profiles.py workflow_store.py
git commit -m "feat(workflows): persist optional user profiles"
```

### Task 3: Expose manual steps and profiles through the local web API

**Files:**
- Modify: `local_web.py`
- Test: `tests/test_workflow_manual_api.py`

**Interfaces:**
- `GET /api/workflow-profiles?module_type=forge&subtype=trials` returns only compatible profiles.
- `POST /api/workflow-profiles` accepts `{module_type, subtype, name, recipe}` and returns `201` without queue mutation.
- `POST /api/workflow-profiles/delete` accepts `{profile_id}`.
- `POST /api/workflows/manual` accepts `{name, steps, actor}`; validates each step, creates/versions the workflow modules required by the existing `workflow_store`, appends the ordered queue steps, and returns the workflow plus queue snapshot.
- Existing `/api/workflows/composed` remains unchanged for legacy clients.

- [ ] **Step 1: Write failing API tests**

Use a temporary `DatabaseManager` and `LocalWebService` to assert:

1. A profile can be saved and listed by exact module/subtype.
2. A Forge profile is not returned for Logistica.
3. A manual workflow with Forge, Logistica and Telegram creates three queue steps.
4. The second step binds to the first output and the third binds to the second output.
5. Invalid steps return `400` and do not create a workflow or partial queue.

- [ ] **Step 2: Run the API tests and verify red**

```powershell
py -m pytest tests/test_workflow_manual_api.py -q
```

Expected: FAIL because the routes do not exist.

- [ ] **Step 3: Implement the routes transactionally**

Initialize the profile schema before reads/writes. For manual workflow creation, validate all steps before creating any module or queue row; use a transaction and rollback on any validation error. Use the existing queue contracts and `append_queue_step` so dependency validation remains centralized.

- [ ] **Step 4: Run API tests and existing workflow API tests**

```powershell
py -m pytest tests/test_workflow_manual_api.py tests/test_workflow_queue_api.py tests/test_workflow_presets.py -q
```

Expected: all pass, including the legacy preset endpoint.

- [ ] **Step 5: Commit the API boundary**

```powershell
git add local_web.py tests/test_workflow_manual_api.py
git commit -m "feat(web): expose manual workflows and optional profiles"
```

### Task 4: Replace hard-coded web blocks with the manual step editor

**Files:**
- Modify: `web/app.js`
- Modify: `web/styles.css` if the dynamic forms require layout rules
- Test: `tests/test_workflow_manual_ui.py`

**Interfaces:**
- `state.workflowSteps` is an ordered list of `{id, module_type, subtype, fields, profile_id}`.
- `renderWorkflowStep(step, index)` renders a blank module selector first and the correct complete field set only after selection.
- `addWorkflowStep()` creates an empty step with no fake name, target, profile, hours, or account.
- `readWorkflowSteps()` returns validated manual step payloads for `/api/workflows/manual`.
- `loadCompatibleProfiles(moduleType, subtype)` calls the filtered profile endpoint only after explicit module/subtype selection.

- [ ] **Step 1: Write failing UI-contract tests**

Read the actual web asset and assert that it no longer contains `workflowBlockDefaults`, `profile: "no_mirror"`, fake times, or automatic `workflowPresets` selection. Assert that it contains selectors and field keys for:

```text
forge: trial_mode, video_paths, tanda_name, copies, days, effects, strength,
       forge_strength, overrides, fx_enabled, metadata_assignments
logistica: mode, tanda_name, tanda_name_2, category_dest, daily_quota, days,
           fillup, account_names, caption_modes
telegram: account_names, date, express, reset_topics, schedule_config
```

Also assert that the UI labels the explicit actions `Agregar paso`, `Cargar perfil`, `Guardar como perfil`, and `Limpiar formulario`.

- [ ] **Step 2: Run the UI tests and verify red**

```powershell
py -m pytest tests/test_workflow_manual_ui.py -q
```

Expected: FAIL because the current editor still renders production blocks with default profile/target/times.

- [ ] **Step 3: Implement the dynamic step renderer**

Remove the default block array and the automatic preset fetch from the editor state. Render blank required inputs, explicit subtype choices, complete Forge/Logistica/Telegram sections, and a per-step remove button. Use `data-step-field` attributes so read/write logic is independent of DOM order.

- [ ] **Step 4: Implement explicit profile actions**

`Cargar perfil` opens a compatible list and copies only recipe fields into the current step. `Guardar como perfil` asks for a name and POSTs the current validated recipe. `Limpiar formulario` resets every field to blank/false and clears `profile_id`. None of these actions calls the queue endpoint.

- [ ] **Step 5: Implement manual workflow save and queue display**

Change the save action to POST `/api/workflows/manual`. Keep the existing queue section and show each step's module/subtype, input contract, output contract, and explicit previous-output binding. Preserve reorder/remove validation.

- [ ] **Step 6: Run focused UI/API regression tests**

```powershell
py -m pytest tests/test_workflow_manual_ui.py tests/test_workflow_manual_api.py tests/test_workflow_queue_ui.py tests/test_workflow_queue_e2e.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit the manual editor**

```powershell
git add web/app.js web/styles.css tests/test_workflow_manual_ui.py
git commit -m "feat(web): replace workflow templates with manual step forms"
```

### Task 5: Align desktop form capture with the modular recipe contract

**Files:**
- Modify: `gui_premium_v7.py`
- Modify: `workflow_step_recipes.py` only for fields missing from the existing forms
- Test: `tests/test_workflow_form_ui.py`

**Interfaces:**
- `_queue_current_forge()` captures the selected Forge mode and all current Forge form fields.
- `_queue_current_logistica()` and `_queue_current_logistica_accounts()` capture their complete mode-specific fields.
- `_queue_current_telegram()` captures accounts, date, express, topics, and schedule settings.
- Existing “Agregar a workflow” buttons remain compatible with workflows created by the new web editor.

- [ ] **Step 1: Add failing UI/source tests**

Assert that each traditional tab's queue action passes all relevant fields to its recipe builder, including Forge `trial_mode`, `fx_enabled`, `overrides`, Logistica mode/account/caption data, and Telegram schedule configuration. Assert that no queue action injects a built-in profile name or generic default recipe.

- [ ] **Step 2: Run the tests and verify red**

```powershell
py -m pytest tests/test_workflow_form_ui.py -q
```

Expected: FAIL for the missing Telegram schedule payload or any field not yet captured by the queue recipe.

- [ ] **Step 3: Implement only the missing field capture**

Reuse existing widget variables and helper methods. Do not duplicate the form UI in the desktop app; the desktop tabs remain the source of truth for their complete field set.

- [ ] **Step 4: Run form, recipe, and queue regressions**

```powershell
py -m pytest tests/test_workflow_form_ui.py tests/test_workflow_step_recipes.py tests/test_workflow_queue.py tests/test_workflow_queue_api.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit desktop compatibility**

```powershell
git add gui_premium_v7.py workflow_step_recipes.py tests/test_workflow_form_ui.py
git commit -m "feat(workflows): capture complete traditional form settings"
```

### Task 6: Remove preset defaults from the new path and document compatibility

**Files:**
- Modify: `web/app.js` only if any legacy preset control remains visible in the new editor
- Modify: `gui_premium_v7.py` only if the quick-calendar control still auto-selects a preset
- Modify: `workflow_presets.py` only if the built-in list is still used as a new-editor default
- Test: `tests/test_workflow_clean_entry.py`, `tests/test_workflow_presets.py`

- [ ] **Step 1: Add failing regression assertions**

Assert that a fresh modular editor has zero steps, no selected profile, no fake target/times, and no preset selected. Assert that legacy preset API consumers still receive their historical response unless the user explicitly chooses a saved profile.

- [ ] **Step 2: Run the tests and verify the expected red failure**

```powershell
py -m pytest tests/test_workflow_clean_entry.py tests/test_workflow_presets.py -q
```

- [ ] **Step 3: Remove only automatic/default selection**

Keep compatibility data readable; remove its use as initial state in the new modular editor. Ensure the clean/manual option is selected on first open and that saving an empty form returns a field-specific message instead of silently creating a fake block.

- [ ] **Step 4: Run the complete focused gate**

```powershell
py -m pytest tests/test_workflow_clean_entry.py tests/test_workflow_manual_steps.py tests/test_workflow_profiles.py tests/test_workflow_manual_api.py tests/test_workflow_manual_ui.py tests/test_workflow_form_ui.py tests/test_workflow_step_recipes.py tests/test_workflow_queue.py tests/test_workflow_queue_runner.py tests/test_workflow_queue_api.py tests/test_workflow_queue_ui.py tests/test_workflow_queue_e2e.py tests/test_workflow_presets.py -q
py -m py_compile gui_premium_v7.py local_web.py workflow_manual_steps.py workflow_profiles.py workflow_step_recipes.py
git diff --check
```

Expected: all focused tests pass, compilation succeeds, and `git diff --check` reports no whitespace errors.

- [ ] **Step 5: Commit the default-removal regression fix**

```powershell
git add gui_premium_v7.py web/app.js workflow_presets.py tests/test_workflow_clean_entry.py tests/test_workflow_presets.py
git commit -m "fix(workflows): keep modular editor manual by default"
```

### Task 7: Verify the user journey and release inventory

**Files:**
- Modify: `docs/R00_LAUNCH_IMPORT_INVENTORY.md` if new runtime files need packaging
- Modify: `build_release.ps1`, `release-manifest.json`, `updater.py` if the new Python modules are not already allowlisted
- Create: `tests/test_manual_workflow_release_inventory.py`

- [ ] **Step 1: Write the failing inventory test**

Assert that `workflow_manual_steps.py` and `workflow_profiles.py` are present in the release allowlist and manifest, and that the web assets contain the manual editor.

- [ ] **Step 2: Run it and verify red if inventory is incomplete**

```powershell
py -m pytest tests/test_manual_workflow_release_inventory.py -q
```

- [ ] **Step 3: Update the allowlists and inventory documentation**

Add only the new runtime modules and tests required by the manual editor. Do not include temporary databases, user media, or development fixtures.

- [ ] **Step 4: Run release and user-journey checks**

```powershell
py -m pytest tests/test_manual_workflow_release_inventory.py tests/test_release_package_manifest.py tests/test_r00_inventory.py -q
py -m py_compile gui_premium_v7.py local_web.py workflow_manual_steps.py workflow_profiles.py workflow_step_recipes.py
```

Manually verify:

1. Fresh Workflows page shows no blocks or profile selected.
2. Add Forge Trials, fill fields, save a profile, clear it, and load it explicitly.
3. Add Logistica por tandas and Telegram with real form values.
4. Confirm the queue order and previous-output bindings.
5. Confirm loading a profile alone does not add a queue step.

- [ ] **Step 5: Commit release inventory updates**

```powershell
git add docs/R00_LAUNCH_IMPORT_INVENTORY.md build_release.ps1 release-manifest.json updater.py tests/test_manual_workflow_release_inventory.py
git commit -m "chore(release): include manual workflow editor modules"
```

## Final verification

After all tasks, run the focused gate from Task 6, then the broader existing workflow suite:

```powershell
py -m pytest tests/test_workflow_*.py tests/test_local_web.py -q
```

Report separately:

- manual form and profile behavior verified locally;
- queue persistence and previous-output bindings verified locally;
- real Forge/Logistica runner handlers still pending if they are not wired during this implementation;
- external Telegram delivery not claimed unless run with configured real accounts and explicit user authorization.
