# R09 Durable Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable local job contract that survives process closure and supports versioned recipes, dependencies, checkpoints, retries, recovery, and auditable history without changing legacy producers yet.

**Architecture:** `durable_jobs.py` owns the SQLite schema and state machine. A job stores an immutable recipe snapshot and one or more persisted steps; transitions are guarded by leases and compare-and-set updates. `job_runner.py` executes injected step handlers, records checkpoints and attempts, and can recover abandoned leases after restart. Existing `video_transform_logs` remains historical output evidence and is linked through optional step metadata rather than replaced.

**Tech Stack:** Python standard library, SQLite, pytest, existing `DatabaseManager` connection, no new runtime dependency.

## Global Constraints

- Preserve the default legacy launcher and producer behavior; R09 is additive until R10 adapters are validated.
- No database writes on module import; schema creation occurs only through an explicit migration/ensure call.
- Every externally visible mutation is transactional and idempotent.
- A worker never executes a step without a valid lease owned by that worker.
- A retry never changes the immutable recipe snapshot or step input identity.
- Recovery must distinguish pending, running-with-expired-lease, succeeded, failed, cancelled, and blocked dependency states.
- Update packaging must include new modules in normal releases and exclude them from bootstrap releases.
- Tests must prove local behavior only; no claim of real FFmpeg/Instagram/Telegram execution is made by R09.

---

### Task 1: Persisted job and recipe schema

**Files:**
- Create: `durable_jobs.py`
- Test: `tests/test_durable_jobs.py`

**Interfaces:**
- `ensure_job_schema(connection) -> None`
- `create_job(connection, *, job_type: str, recipe: dict, steps: list[dict], idempotency_key: str | None = None, now: int | None = None) -> dict`
- `get_job(connection, job_id: str) -> dict | None`
- `list_jobs(connection, *, states: set[str] | None = None, limit: int = 100) -> list[dict]`

- [ ] **Step 1: Write failing tests** for schema opt-in, immutable recipe JSON, deterministic step order, and idempotency key returning the existing job.
- [ ] **Step 2: Run** `py -m pytest -q tests/test_durable_jobs.py`; expected failure because `durable_jobs` does not exist.
- [ ] **Step 3: Implement** tables `durable_jobs`, `durable_job_steps`, and `durable_job_events` with explicit states and JSON snapshots; reject empty job types, malformed recipes, duplicate step IDs, and unknown dependency IDs.
- [ ] **Step 4: Run** the focused test and verify all schema behavior passes.
- [ ] **Step 5: Commit** `feat: persist durable job recipes`.

### Task 2: State transitions, dependencies, and checkpoints

**Files:**
- Modify: `durable_jobs.py`
- Test: `tests/test_durable_jobs.py`

**Interfaces:**
- `claim_next_step(connection, *, worker_id: str, lease_seconds: int = 300, now: int | None = None) -> dict | None`
- `record_step_checkpoint(connection, *, job_id: str, step_id: str, worker_id: str, lease_token: str, checkpoint: dict, now: int | None = None) -> dict`
- `complete_step(connection, *, job_id: str, step_id: str, worker_id: str, lease_token: str, result: dict | None = None, now: int | None = None) -> dict`
- `fail_step(connection, *, job_id: str, step_id: str, worker_id: str, lease_token: str, error: dict, retryable: bool, now: int | None = None) -> dict`
- `cancel_job(connection, *, job_id: str, reason: str, now: int | None = None) -> dict`

- [ ] **Step 1: Write failing tests** for dependency blocking, lease ownership, checkpoint persistence, success propagation, retryable failure, terminal failure, and cancellation.
- [ ] **Step 2: Run** `py -m pytest -q tests/test_durable_jobs.py`; expected failure on missing transition functions.
- [ ] **Step 3: Implement** compare-and-set transitions inside `BEGIN IMMEDIATE`; only steps whose dependencies succeeded can be claimed; expired leases become claimable without losing the last checkpoint.
- [ ] **Step 4: Run** focused tests and verify a second worker cannot claim an active lease.
- [ ] **Step 5: Commit** `feat: add durable job state machine`.

### Task 3: Retry policy and restart recovery

**Files:**
- Modify: `durable_jobs.py`
- Test: `tests/test_durable_jobs.py`

**Interfaces:**
- `recover_expired_steps(connection, *, now: int | None = None) -> dict`
- `retry_job_step(connection, *, job_id: str, step_id: str, now: int | None = None) -> dict`
- `inspect_job_events(connection, *, job_id: str, limit: int = 500) -> list[dict]`

- [ ] **Step 1: Write failing tests** for max attempts, exponential retry schedule represented as persisted `next_attempt_at`, recovery after simulated process closure, and event ordering.
- [ ] **Step 2: Run** the focused tests and verify expected failures.
- [ ] **Step 3: Implement** retry metadata in the recipe snapshot (`max_attempts`, `backoff_seconds`), never retry non-retryable errors, and convert expired `running` steps to `retry_wait` or `failed` atomically.
- [ ] **Step 4: Run** focused tests and verify recovery is repeatable and does not duplicate events.
- [ ] **Step 5: Commit** `feat: recover and retry durable job steps`.

### Task 4: Executable runner with injected handlers

**Files:**
- Create: `job_runner.py`
- Test: `tests/test_job_runner.py`

**Interfaces:**
- `run_one_step(connection, *, worker_id: str, handlers: dict[str, callable], now: int | None = None) -> dict | None`
- `run_until_idle(connection, *, worker_id: str, handlers: dict[str, callable], max_steps: int = 100, now: int | None = None) -> dict`
- `recover_and_run(connection, *, worker_id: str, handlers: dict[str, callable], now: int | None = None) -> dict`

- [ ] **Step 1: Write failing tests** with real in-memory SQLite handlers that succeed, checkpoint then fail, retry, and resume from the checkpoint.
- [ ] **Step 2: Run** `py -m pytest -q tests/test_job_runner.py`; expected failure because the runner does not exist.
- [ ] **Step 3: Implement** handler lookup by `step.kind`, checkpoint callback support, bounded loop execution, and structured summaries; unknown handlers become terminal configuration failures.
- [ ] **Step 4: Run** runner tests plus Task 1-3 tests.
- [ ] **Step 5: Commit** `feat: execute durable job steps`.

### Task 5: Compatibility, packaging, and operational documentation

**Files:**
- Modify: `build_release.ps1`, `updater.py`, `docs/R00_LAUNCH_IMPORT_INVENTORY.md`, `docs/ROADMAP_IMPLEMENTATION_STATUS.md`
- Create: `docs/R09_DURABLE_JOBS_REPORT.md`
- Test: `tests/test_release_package_manifest.py`, `tests/test_r09_contract.py`

- [ ] **Step 1: Write failing contract tests** for import safety, normal-release inclusion, bootstrap exclusion, legacy launcher unchanged, and documented recovery states.
- [ ] **Step 2: Run** the contract tests and verify missing package/doc entries fail.
- [ ] **Step 3: Add** both modules to normal release/updater allowlists, preserve bootstrap `{updater.py, version.json}`, and document the explicit migration boundary.
- [ ] **Step 4: Run** R09 tests, all prior R00-R08 focal tests, and `py -m py_compile` for new modules.
- [ ] **Step 5: Commit** `docs: document r09 durable job compatibility`.

### Task 6: Full validation and closure gate

- [ ] **Step 1:** Run `py -m pytest -q` from the isolated worktree.
- [ ] **Step 2:** Run `git diff --check`, inspect branch/status, and confirm no operational DB/calendar files changed.
- [ ] **Step 3:** Update R09 status only after the suite is green and the branch is clean.
- [ ] **Step 4:** Request code review and resolve Critical/Important findings.
- [ ] **Step 5:** Mark R09 complete only with exact commit and test evidence; state the remaining boundary that real producer/FFmpeg integration belongs to R10.

## Self-Review

- Recipe immutability, dependencies, checkpoints, retry, lease expiry, recovery, and runner behavior each have an explicit task and test boundary.
- No task changes a legacy producer or launcher default; R10 owns those adapters.
- No task claims external-service or paid-media validation.
- The plan introduces only two runtime modules and uses the existing SQLite connection and test stack.
