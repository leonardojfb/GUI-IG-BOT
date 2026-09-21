# Chained Job Workflow Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `Agregar a workflow` action to every visible compatible job and execute ordered Forge, Logística, and Telegram steps through the existing durable-job runner.

**Architecture:** Add a small SQLite-backed queue layer keyed by the existing workflow IDs. Queue steps store immutable job recipes plus typed input bindings; execution snapshots are materialized as one parent `durable_job` whose ordered steps depend on their predecessor. The local web API and static frontend expose queue composition, the Telegram delivery choice, execution, and per-step status without replacing `workflow_store.py` or `job_runner.py`.

**Tech Stack:** Python 3, sqlite3, existing `durable_jobs.py`/`job_runner.py`, `http.server`, static HTML/CSS/JavaScript, pytest.

## Global Constraints

- Work only in `.worktrees/r00-reproducible-baseline`.
- Preserve unrelated dirty-worktree changes; stage and commit only feature files per task.
- Use additive SQLite tables and canonical JSON; do not mutate historical outputs or delete existing jobs.
- The visible button text must be exactly `Agregar a workflow`.
- `queue_only` prepares Telegram work without sending; `send_on_run` invokes the existing idempotent Telegram delivery path.
- A downstream step cannot run until its bound upstream output succeeds; failed dependencies become blocked.
- Do not add automatic Instagram/Facebook publication.
- Tests must use temporary/in-memory databases and controlled handlers; no real Telegram or Meta delivery is required for local verification.

## File Map

- Create `workflow_queue.py`: queue schema, step validation, ordering, typed bindings, and execution snapshots.
- Create `workflow_queue_runner.py`: materialize queue snapshots into `durable_jobs`, resolve outputs, and dispatch supported step handlers.
- Modify `local_web.py`: authenticated queue CRUD/execution routes and job/task action payloads.
- Modify `web/app.js`: render `Agregar a workflow`, queue editor, Telegram mode, execute action, and step state.
- Modify `web/styles.css`: compact workflow-step and action styling.
- Create `tests/test_workflow_queue.py`: persistence, validation, ordering, snapshot immutability.
- Create `tests/test_workflow_queue_runner.py`: dependency order, output bindings, failure blocking, resume, and Telegram modes.
- Create `tests/test_workflow_queue_e2e.py`: the three-step Forge → Logística → Telegram example.
- Modify `tests/test_web_workflows_api.py`: route coverage for adding jobs, executing workflows, and selecting Telegram mode.
- Modify `tests/test_workflow_creation_ui.py`: static UI assertions for the exact button and mode selector.

### Task 1: Persist and validate ordered workflow steps

**Files:**
- Create: `workflow_queue.py`
- Create: `tests/test_workflow_queue.py`

**Interfaces:**
- `ensure_workflow_queue_schema(connection) -> None`
- `list_queue_steps(connection, workflow_id) -> list[dict]`
- `append_queue_step(connection, workflow_id, *, job_type, recipe, input_contract, output_contract, input_binding=None, source_job_id=None) -> dict`
- `remove_queue_step(connection, workflow_id, step_id) -> dict`
- `reorder_queue_steps(connection, workflow_id, step_ids) -> list[dict]`
- `set_telegram_mode(connection, workflow_id, mode) -> dict`
- `snapshot_queue(connection, workflow_id, *, actor) -> dict`
- `get_queue_execution(connection, execution_id) -> dict`

- [ ] **Step 1: Write failing tests for schema and append order.**

```python
def test_append_queue_step_preserves_order_and_recipe_snapshot():
    conn = db()
    first = append_queue_step(
        conn, "wf-1", job_type="forge.tanda", recipe={"tanda": "SPAM"},
        input_contract="AssetList", output_contract="TandaOutput",
    )
    second = append_queue_step(
        conn, "wf-1", job_type="logistica.tanda", recipe={"accounts": ["spam-1"]},
        input_contract="TandaOutput", output_contract="ManifestOutput",
        input_binding={"kind": "previous_output", "step_id": first["step_id"]},
    )
    assert [item["position"] for item in list_queue_steps(conn, "wf-1")] == [1, 2]
    assert second["input_binding"] == {"kind": "previous_output", "step_id": first["step_id"]}
    first["recipe"]["tanda"] = "MUTATED"
    assert list_queue_steps(conn, "wf-1")[0]["recipe"]["tanda"] == "SPAM"
```

- [ ] **Step 2: Run the focused test and verify it fails because `workflow_queue` is absent.**

Run: `py -m pytest tests/test_workflow_queue.py::test_append_queue_step_preserves_order_and_recipe_snapshot -q`

Expected: collection failure with `ModuleNotFoundError: No module named 'workflow_queue'`.

- [ ] **Step 3: Implement the additive schema and canonical JSON helpers.**

Create `workflow_job_queues` with `workflow_id` primary key, `telegram_mode` constrained to `queue_only`/`send_on_run`, and timestamps. Create `workflow_job_queue_steps` with `(workflow_id, step_id)` primary key, unique position, job type, recipe JSON, input/output contracts, binding JSON, source job ID, and created timestamp. `append_queue_step` must assign `MAX(position)+1`, reject an empty job type/recipe, reject a binding to a missing step, reject a binding to a later step, and reject incompatible contracts unless the binding kind is `asset`.

- [ ] **Step 4: Add tests for reorder, remove, invalid contracts, cycles, and Telegram mode.**

```python
def test_queue_rejects_later_or_incompatible_bindings():
    conn = db()
    with pytest.raises(ValueError, match="anterior"):
        append_queue_step(conn, "wf-1", job_type="telegram.send", recipe={}, input_contract="ManifestOutput", output_contract="TelegramOutput", input_binding={"kind": "step_output", "step_id": "missing"})
    forge = append_queue_step(conn, "wf-1", job_type="forge.tanda", recipe={}, input_contract="AssetList", output_contract="TandaOutput")
    with pytest.raises(ValueError, match="incompatible"):
        append_queue_step(conn, "wf-1", job_type="telegram.send", recipe={}, input_contract="ManifestOutput", output_contract="TelegramOutput", input_binding={"kind": "step_output", "step_id": forge["step_id"]})
```

- [ ] **Step 5: Implement `reorder_queue_steps`, `remove_queue_step`, `set_telegram_mode`, and `snapshot_queue`; snapshot must contain a deep JSON copy and a stable hash.**

- [ ] **Step 6: Run all Task 1 tests and commit the isolated persistence unit.**

Run: `py -m pytest tests/test_workflow_queue.py -q`

Expected: all queue persistence and validation tests pass.

Commit: `git add workflow_queue.py tests/test_workflow_queue.py && git commit -m "feat(workflows): persist ordered job queue steps"`

### Task 2: Materialize queue snapshots through durable jobs

**Files:**
- Create: `workflow_queue_runner.py`
- Create: `tests/test_workflow_queue_runner.py`

**Interfaces:**
- `create_queue_execution(connection, workflow_id, *, actor) -> dict`
- `run_queue_execution(connection, execution_id, *, worker_id, handlers=None, telegram_sender=None) -> dict`
- `resume_queue_execution(connection, execution_id, *, worker_id, handlers=None, telegram_sender=None) -> dict`
- `resolve_input_binding(connection, durable_job_id, binding) -> dict`
- `default_queue_handlers(connection, *, telegram_sender=None) -> dict`

- [ ] **Step 1: Write failing tests proving order and output propagation.**

```python
def test_execution_passes_forge_output_to_logistica_and_telegram():
    conn = db()
    forge = append_queue_step(conn, "wf-1", job_type="forge.tanda", recipe={"tanda": "SPAM"}, input_contract="AssetList", output_contract="TandaOutput")
    append_queue_step(conn, "wf-1", job_type="logistica.tanda", recipe={"accounts": ["spam"]}, input_contract="TandaOutput", output_contract="ManifestOutput", input_binding={"kind": "previous_output", "step_id": forge["step_id"]})
    append_queue_step(conn, "wf-1", job_type="telegram.send", recipe={}, input_contract="ManifestOutput", output_contract="TelegramOutput", input_binding={"kind": "previous_output", "step_id": "step-0002"})
    seen = []
    execution = create_queue_execution(conn, "wf-1", actor="test")
    result = run_queue_execution(conn, execution["execution_id"], worker_id="test", handlers={
        "forge.tanda": lambda step, *_: seen.append((step["step_id"], None)) or {"tanda": "SPAM", "files": ["out-1.mp4"]},
        "logistica.tanda": lambda step, *_: seen.append((step["step_id"], step["payload"]["input"])) or {"manifest": "manifest.json", "task_ids": ["task-1"]},
        "telegram.send": lambda step, *_: seen.append((step["step_id"], step["payload"]["input"])) or {"queued": 1},
    })
    assert result["state"] == "succeeded"
    assert [item[0] for item in seen] == ["step-0001", "step-0002", "step-0003"]
    assert seen[1][1]["tanda"] == "SPAM"
    assert seen[2][1]["manifest"] == "manifest.json"
```

- [ ] **Step 2: Run the test and verify it fails because execution materialization is absent.**

Run: `py -m pytest tests/test_workflow_queue_runner.py::test_execution_passes_forge_output_to_logistica_and_telegram -q`

Expected: `ImportError` for `workflow_queue_runner`.

- [ ] **Step 3: Implement `create_queue_execution`.**

Call `snapshot_queue`, insert an execution record with `execution_id`, `workflow_id`, snapshot JSON, and state `pending`, then call existing `durable_jobs.create_job` with `job_type="workflow.queue.v1"`. Create one durable step per queue step in position order, `kind="workflow.queue_step"`, with `depends_on` set to the immediately previous step and payload containing the frozen queue step and execution ID. Store the generated durable job ID in the execution row.

- [ ] **Step 4: Implement input resolution and the runner handler.**

Before dispatch, resolve `previous_output`/`step_output` from the parent durable job's succeeded step result and inject it as `step["payload"]["input"]`. The handler registry must dispatch by the frozen queue `job_type`; a missing handler fails the step non-retryably. Use the existing `job_runner.run_until_idle` so leases, checkpoints, retries, and dependent blocking remain centralized. Update the execution state from the parent durable job state after each run.

- [ ] **Step 5: Add failure, resume, and Telegram-mode tests.**

```python
def test_failed_step_blocks_descendants_and_resume_keeps_successful_output():
    execution = create_queue_execution(conn, "wf-1", actor="test")
    first = run_queue_execution(conn, execution["execution_id"], worker_id="w1", handlers=failing_handlers)
    assert first["state"] == "failed"
    assert [step["state"] for step in get_queue_execution(conn, execution["execution_id"])["steps"]] == ["succeeded", "failed", "blocked"]
    second = resume_queue_execution(conn, execution["execution_id"], worker_id="w2", handlers=working_handlers)
    assert second["state"] == "succeeded"
    assert calls == ["forge", "logistica", "telegram"]
```

`failing_handlers` must raise a normal exception only for the Logística handler; `working_handlers` must append each executed job type to `calls` and return the typed output. `resume_queue_execution` must call `durable_jobs.retry_job_step` only for the failed step, leaving the succeeded Forge step untouched. Add tests that `queue_only` returns a queued Telegram result without calling the sender and `send_on_run` calls the sender exactly once.

- [ ] **Step 6: Run runner tests and commit the execution unit.**

Run: `py -m pytest tests/test_workflow_queue_runner.py -q`

Expected: all execution, binding, failure, resume, and Telegram mode tests pass.

Commit: `git add workflow_queue_runner.py tests/test_workflow_queue_runner.py && git commit -m "feat(workflows): execute chained job queue"`

### Task 3: Expose queue composition and execution through the authenticated API

**Files:**
- Modify: `local_web.py`
- Modify: `tests/test_web_workflows_api.py`

**Interfaces:**
- `GET /api/workflows/{workflow_id}/queue`
- `POST /api/workflows/{workflow_id}/queue/steps`
- `POST /api/workflows/{workflow_id}/queue/remove`
- `POST /api/workflows/{workflow_id}/queue/reorder`
- `POST /api/workflows/{workflow_id}/queue/settings`
- `POST /api/workflows/{workflow_id}/queue/execute`
- `GET /api/executions/{execution_id}`

- [ ] **Step 1: Add failing HTTP tests for the full queue lifecycle.**

```python
def test_web_adds_job_to_workflow_and_executes_it(tmp_path, monkeypatch):
    db = database.DatabaseManager(str(tmp_path / "db.sqlite"))
    service = LocalWebService(db, token="web-token").start()
    try:
        workflow = create_test_workflow(service, "web-token", "Workflow queue")
        status, queue = post(f"{service.base_url}/api/workflows/{workflow['workflow_id']}/queue/steps", "web-token", {"job_type": "forge.tanda", "recipe": {"tanda": "SPAM"}, "input_contract": "AssetList", "output_contract": "TandaOutput"})
        assert status == 201
        assert queue["data"]["steps"][0]["job_type"] == "forge.tanda"
        status, _ = post(f"{service.base_url}/api/workflows/{workflow['workflow_id']}/queue/settings", "web-token", {"telegram_mode": "send_on_run"})
        assert status == 200
        status, execution = post(f"{service.base_url}/api/workflows/{workflow['workflow_id']}/queue/execute", "web-token", {})
        assert status == 202
        assert execution["data"]["state"] in {"pending", "running", "succeeded"}
    finally:
        service.stop()
        db.close()
```

- [ ] **Step 2: Run the focused API test and verify the routes return 404.**

Run: `py -m pytest tests/test_web_workflows_api.py::test_web_adds_job_to_workflow_and_executes_it -q`

Expected: failure because the queue routes do not exist.

- [ ] **Step 3: Add route parsing and handlers in `LocalWebService`.**

All routes must pass the existing authorization/CSRF gates. Validate workflow IDs, job recipes, contracts, binding objects, step IDs, and Telegram mode; return 400 for invalid composition and 404 for unknown workflow/execution. Use `queue_only` as the default when a mode is omitted. Use `create_queue_execution` and `run_queue_execution` for execution rather than duplicating runner logic.

- [ ] **Step 4: Enrich visible job/task records with an action payload.**

The jobs endpoint keeps its existing durable-job fields and adds a serializable `workflow_job` object containing `job_type`, frozen recipe, input contract, output contract, and optional `source_job_id`. Task and Telegram rows expose the corresponding `logistica.tanda` or `telegram.send` recipe without exposing physical paths outside authorized API responses.

- [ ] **Step 5: Add API tests for validation, mode choice, and idempotent rerun.**

Run: `py -m pytest tests/test_web_workflows_api.py -q`

Expected: the existing web API tests plus the new queue lifecycle tests pass.

Commit: `git add local_web.py tests/test_web_workflows_api.py && git commit -m "feat(web): expose chained workflow queue API"`

### Task 4: Add the button and workflow queue editor to the web UI

**Files:**
- Modify: `web/app.js`
- Modify: `web/styles.css`
- Modify: `tests/test_workflow_creation_ui.py`

**Interfaces:**
- `queueJob(item)` sends the selected workflow's `workflow_job` to the queue endpoint.
- `renderWorkflowQueue(queue)` renders ordered steps and bindings.
- `executeWorkflow(workflowId)` starts and refreshes an execution.

- [ ] **Step 1: Add static UI tests that require the exact action text and Telegram choices.**

```python
def test_web_exposes_add_to_workflow_and_explicit_telegram_mode():
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert "Agregar a workflow" in app
    assert "queue_only" in app
    assert "send_on_run" in app
```

- [ ] **Step 2: Run the UI test and verify it fails because the new strings/actions are absent.**

Run: `py -m pytest tests/test_workflow_creation_ui.py::test_web_exposes_add_to_workflow_and_explicit_telegram_mode -q`

Expected: assertion failure.

- [ ] **Step 3: Add `Agregar a workflow` to every compatible job/task row.**

In `renderTable`, add an action cell when `state.view === "jobs"`; in `renderTasks`, add the same action for logistics/Telegram task records. Disable it with a visible status message when no workflow is selected, and never silently choose a workflow. The click handler sends the frozen `workflow_job` payload and refreshes the workflow queue.

- [ ] **Step 4: Render the ordered queue editor.**

In `renderWorkflows`, load the selected queue, show position, job type, input binding, and output contract, and add controls for remove/reorder. Add an explicit select with labels `Dejar en cola Telegram` and `Enviar automáticamente`; persist it through `/queue/settings`. Add `Ejecutar workflow` and show the returned execution ID/state.

- [ ] **Step 5: Add styling and run the UI tests.**

Run: `py -m pytest tests/test_workflow_creation_ui.py -q`

Expected: all existing and new frontend contract tests pass.

Commit: `git add web/app.js web/styles.css tests/test_workflow_creation_ui.py && git commit -m "feat(web): add workflow queue actions"`

### Task 5: Verify the complete example and package boundary

**Files:**
- Create: `tests/test_workflow_queue_e2e.py`
- Modify: `release-manifest.json` only if the existing package verifier excludes the new modules.

- [ ] **Step 1: Write the end-to-end test for Forge → Logística → Telegram.**

Use a temporary SQLite database and controlled handlers that write a distinct output marker for Forge, create a manifest object from that marker, and record Telegram delivery. Assert exact execution order, typed input propagation, `queue_only` behavior, `send_on_run` behavior, and rerun idempotency.

- [ ] **Step 2: Run the focused end-to-end test and fix only feature-scoped failures.**

Run: `py -m pytest tests/test_workflow_queue_e2e.py -q`

Expected: one passing scenario for each Telegram mode and one failure/resume scenario.

- [ ] **Step 3: Run the related regression suite.**

Run: `py -m pytest tests/test_durable_jobs.py tests/test_job_runner.py tests/test_workflow_store.py tests/test_workflow_compositions.py tests/test_web_workflows_api.py tests/test_workflow_creation_ui.py tests/test_workflow_queue.py tests/test_workflow_queue_runner.py tests/test_workflow_queue_e2e.py -q`

Expected: all selected tests pass; no existing durable-job or web-workflow regression.

- [ ] **Step 4: Run compile and package checks.**

Run: `py -m py_compile workflow_queue.py workflow_queue_runner.py local_web.py`

Then run the existing release-manifest test. If it reports missing feature modules, add only those modules to the existing code-only manifest and rerun it.

- [ ] **Step 5: Commit the verification test/package adjustment.**

Commit: `git add tests/test_workflow_queue_e2e.py release-manifest.json && git commit -m "test(workflows): verify chained job execution"`

## Self-Review Checklist

- The exact button label appears in the job, logistics-task, and Telegram-task render paths.
- The queue stores recipes and bindings, not reusable final files.
- Forge output, Logística manifest, and Telegram result have explicit contract names.
- Queue execution uses the existing durable runner and does not duplicate lease/retry/blocking logic.
- Telegram behavior is selected per workflow and frozen per execution.
- The test plan proves order, binding, invalid connections, failure blocking, resume, and both delivery modes.
- No step claims Meta publication or real external delivery from local tests.
